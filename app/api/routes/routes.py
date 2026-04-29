"""
All non-chat API routes:
  /users          — CRUD
  /progress       — read progress
  /problems       — log solved problems
  /notes          — submit + validate pattern notes
  /hints          — RAG-powered hint endpoint
  /nudge          — manually trigger daily assignment
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas import (
    HintRequest,
    HintResponse,
    LogProblemRequest,
    LogProblemResponse,
    NotesValidationResponse,
    ProgressResponse,
    SubmitNotesRequest,
    TriggerNudgeRequest,
    TriggerNudgeResponse,
    UserCreateRequest,
    UserResponse,
)
from app.db.session import AsyncSession, get_async_session
from app.services import progress_service, vector_store

logger = logging.getLogger(__name__)

# ── Users ─────────────────────────────────────────────────────────────────────
users_router = APIRouter(prefix="/users", tags=["Users"])


@users_router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreateRequest,
    db: AsyncSession = Depends(get_async_session),
) -> UserResponse:
    user = await progress_service.get_or_create_user(
        db=db,
        username=body.username,
        telegram_chat_id=body.telegram_chat_id,
        email=body.email,
    )
    return UserResponse.model_validate(user)


@users_router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_async_session),
) -> UserResponse:
    user = await progress_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


# ── Progress ──────────────────────────────────────────────────────────────────
progress_router = APIRouter(prefix="/progress", tags=["Progress"])


@progress_router.get("/{user_id}", response_model=ProgressResponse)
async def get_progress(user_id: str) -> ProgressResponse:
    try:
        profile = await progress_service.get_user_profile(user_id)
        return ProgressResponse(**profile)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@progress_router.post("/{user_id}/advance-topic")
async def advance_topic(user_id: str) -> dict:
    try:
        return await progress_service.try_advance_topic(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── Problems ──────────────────────────────────────────────────────────────────
problems_router = APIRouter(prefix="/problems", tags=["Problems"])


@problems_router.post("/log", response_model=LogProblemResponse)
async def log_problem(body: LogProblemRequest) -> LogProblemResponse:
    try:
        result = await progress_service.record_problem_solved(
            user_id=body.user_id,
            topic_id=body.topic_id,
            problem_name=body.problem_name,
            difficulty=body.difficulty,
            used_hint=body.used_hint,
            clean_solve=not body.used_hint,
            notes_submitted=False,
            time_taken_minutes=body.time_taken_minutes or 0,
            patterns_used=body.patterns_used or "",
        )
        return LogProblemResponse(
            success=result["success"],
            streak=result["streak"],
            total_problems=result["total_problems"],
            topic_total=result["topic_total"],
            topic_completed=result["topic_completed"],
            message=(
                f"🔥 {result['streak']}-day streak! "
                f"{result['topic_total']} problems solved in this topic."
                + (" Topic complete — ready to advance!" if result["topic_completed"] else "")
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── Notes ─────────────────────────────────────────────────────────────────────
notes_router = APIRouter(prefix="/notes", tags=["Notes"])


@notes_router.post("/submit", response_model=NotesValidationResponse)
async def submit_notes(
    body: SubmitNotesRequest,
    db: AsyncSession = Depends(get_async_session),
) -> NotesValidationResponse:
    """
    Validate the student's pattern notes via LLM, then persist if approved.
    The 'Strict Coach' guardrail lives here.
    """
    from app.agent.tools.coach_tools import validate_student_notes

    # Run LLM validation
    problem_context = body.problem_context or f"Topic: {body.topic_id}, Pattern: {body.pattern_name}"
    raw_result = await validate_student_notes.ainvoke({
        "notes": body.note_text,
        "problem_context": problem_context,
    })

    try:
        validation = json.loads(raw_result)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Validation service returned invalid response")

    note_id = None
    if validation.get("approved"):
        # Save to Postgres + ChromaDB only if approved
        note = await progress_service.save_pattern_note(
            db=db,
            user_id=body.user_id,
            topic_id=body.topic_id,
            pattern_name=body.pattern_name,
            note_text=body.note_text,
            solved_problem_id=body.solved_problem_id,
        )
        note_id = note.id

    return NotesValidationResponse(
        approved=validation.get("approved", False),
        score=validation.get("score", 0),
        feedback=validation.get("feedback", ""),
        note_id=note_id,
    )


# ── Hints ─────────────────────────────────────────────────────────────────────
hints_router = APIRouter(prefix="/hints", tags=["Hints"])


@hints_router.post("", response_model=HintResponse)
async def get_hint(body: HintRequest) -> HintResponse:
    """
    RAG-powered hint endpoint.

    1. Queries ChromaDB for past problems this user struggled with
       that are similar to the current one.
    2. Routes through the chat agent with a structured hint-mode prompt.
    """
    from app.agent.tools.coach_tools import query_past_struggles
    from app.services.llm import get_llm
    from langchain_core.messages import HumanMessage, SystemMessage

    # Fetch past struggles
    raw_struggles = await query_past_struggles.ainvoke({
        "user_id": body.user_id,
        "current_topic": body.topic_id,
        "hint_query": body.problem_description,
    })
    struggles_data = json.loads(raw_struggles)
    past_notes = struggles_data.get("past_struggles", [])
    blind_spots = struggles_data.get("blind_spots", [])

    # Build hint-specific prompt
    rag_block = ""
    if past_notes:
        rag_block = "\n\nThis student's past struggles with similar problems:\n"
        for note in past_notes[:3]:
            rag_block += f"- {note['document'][:200]}...\n"
        if blind_spots:
            rag_block += f"\nRecurring blind spots: {', '.join(blind_spots)}\n"

    hint_level_instructions = {
        "pattern_name": "Give ONLY the pattern name. One sentence maximum. No code.",
        "clue": "Give the pattern name + ONE concrete clue about how to apply it. No code.",
        "full": "Give the full approach including pseudocode. Then ask the student to write their notes.",
    }

    system = (
        "You are a strict DSA coach giving a targeted hint. "
        f"{hint_level_instructions[body.hint_level]}"
        f"{rag_block}"
    )

    user_msg = (
        f"Problem: {body.problem_description}\n"
        + (f"Student's pattern guess: {body.pattern_guess}" if body.pattern_guess else "")
    )

    llm = get_llm()
    response = await llm.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=user_msg),
    ])

    return HintResponse(
        hint_text=str(response.content),
        past_struggles_referenced=[n["problem_name"] for n in past_notes if n.get("problem_name")],
        blind_spots_identified=blind_spots,
    )


# ── Nudge ─────────────────────────────────────────────────────────────────────
nudge_router = APIRouter(prefix="/nudge", tags=["Notifications"])


@nudge_router.post("/trigger", response_model=TriggerNudgeResponse)
async def trigger_nudge(body: TriggerNudgeRequest) -> TriggerNudgeResponse:
    """
    Manually trigger the daily nudge for a specific user.
    Useful for testing or user-initiated refresh.
    """
    from app.workers.tasks import send_nudge_to_user

    task = send_nudge_to_user.delay(body.user_id)
    return TriggerNudgeResponse(
        status="queued",
        message=f"Daily nudge queued for user {body.user_id}. Task ID: {task.id}",
    )
