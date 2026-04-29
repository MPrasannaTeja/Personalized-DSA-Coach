"""
LangChain tools available to the DSA Coach agent.

Each tool is a discrete capability the agent can decide to invoke:
  - validate_notes        : verify that the student wrote meaningful notes
  - get_student_profile   : pull live DB stats for the current user
  - query_past_struggles  : RAG lookup of similar past problems
  - log_problem_solved    : mark a problem as done in the DB
  - advance_topic         : move the student to the next topic/phase

Tools are designed to be stateless — all side-effects go through services.
"""

import json
import logging
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# ── Notes Validation Tool ─────────────────────────────────────────────────────

@tool
async def validate_student_notes(notes: str, problem_context: str) -> str:
    """
    Validate whether the student's pattern notes are substantive enough
    to mark a problem as 'clean' (i.e. properly understood).

    Args:
        notes: The raw text the student wrote about the pattern.
        problem_context: Brief description of the problem (name + topic).

    Returns:
        JSON string with keys: is_valid, score (1-10), feedback, approved.
    """
    # Import here to avoid circular imports
    from app.agent.prompts.coach_prompts import NOTES_VALIDATION_PROMPT
    from app.services.llm import get_llm

    llm = get_llm()
    chain = NOTES_VALIDATION_PROMPT | llm

    response = await chain.ainvoke({
        "notes": notes,
        "problem_context": problem_context,
    })

    raw = response.content.strip()
    # Ensure we always return parseable JSON
    try:
        parsed = json.loads(raw)
        return json.dumps(parsed)
    except json.JSONDecodeError:
        logger.warning("Notes validation LLM returned non-JSON: %s", raw)
        return json.dumps({
            "is_valid": False,
            "score": 0,
            "feedback": "Could not parse validation response. Please try again.",
            "approved": False,
        })


# ── Student Profile Tool ──────────────────────────────────────────────────────

@tool
async def get_student_profile(user_id: str) -> str:
    """
    Fetch the student's live progress profile from the database.

    Args:
        user_id: The user's UUID.

    Returns:
        JSON string with phase, topic, streak, solve rates, and recent problems.
    """
    from app.services.progress_service import get_user_profile

    try:
        profile = await get_user_profile(user_id)
        return json.dumps(profile, default=str)
    except Exception as exc:
        logger.error("get_student_profile failed: %s", exc)
        return json.dumps({"error": str(exc)})


# ── RAG Past Struggles Tool ───────────────────────────────────────────────────

@tool
async def query_past_struggles(user_id: str, current_topic: str, hint_query: str) -> str:
    """
    Search the vector store for problems this student struggled with
    that are semantically similar to the current problem/hint request.

    Args:
        user_id: The user's UUID.
        current_topic: Topic ID (e.g. "trees", "dp1").
        hint_query: Natural language description of the current problem or concept.

    Returns:
        JSON string with a list of relevant past notes and blind spots identified.
    """
    from app.services.vector_store import query_similar_notes

    try:
        results = await query_similar_notes(
            user_id=user_id,
            query_text=hint_query,
            topic_id=current_topic,
            n_results=4,
        )
        summary = {
            "past_struggles": results,
            "blind_spots": _extract_blind_spots(results),
        }
        return json.dumps(summary)
    except Exception as exc:
        logger.error("query_past_struggles failed: %s", exc)
        return json.dumps({"past_struggles": [], "blind_spots": []})


def _extract_blind_spots(notes: list[dict[str, Any]]) -> list[str]:
    """Identify recurring patterns from past struggles."""
    from collections import Counter
    pattern_counts: Counter = Counter()
    for note in notes:
        if note.get("pattern_name"):
            pattern_counts[note["pattern_name"]] += 1
    # Patterns that appear 2+ times = a blind spot
    return [p for p, count in pattern_counts.items() if count >= 2]


# ── Log Problem Tool ──────────────────────────────────────────────────────────

@tool
async def log_problem_solved(
    user_id: str,
    topic_id: str,
    problem_name: str,
    difficulty: str,
    used_hint: bool,
    notes_approved: bool,
    time_taken_minutes: int = 0,
    patterns_used: str = "",
) -> str:
    """
    Record a solved problem in the database and update the user's progress counters.

    Args:
        user_id: The user's UUID.
        topic_id: Topic ID (e.g. "arrays", "dp2").
        problem_name: LeetCode problem name/number.
        difficulty: "easy", "medium", or "hard".
        used_hint: Whether the student used a hint.
        notes_approved: Whether their pattern notes passed validation.
        time_taken_minutes: Optional time taken.
        patterns_used: Comma-separated pattern names used.

    Returns:
        JSON with updated streak and total problem count.
    """
    from app.services.progress_service import record_problem_solved

    try:
        result = await record_problem_solved(
            user_id=user_id,
            topic_id=topic_id,
            problem_name=problem_name,
            difficulty=difficulty,
            used_hint=used_hint,
            clean_solve=notes_approved and not used_hint,
            notes_submitted=notes_approved,
            time_taken_minutes=time_taken_minutes,
            patterns_used=patterns_used,
        )
        return json.dumps(result)
    except Exception as exc:
        logger.error("log_problem_solved failed: %s", exc)
        return json.dumps({"error": str(exc)})


# ── Advance Topic Tool ────────────────────────────────────────────────────────

@tool
async def advance_topic(user_id: str) -> str:
    """
    Move the student to the next topic (or phase) when they've completed
    the minimum problem threshold for the current topic.

    Args:
        user_id: The user's UUID.

    Returns:
        JSON with new phase_idx, topic_idx, and new topic name.
    """
    from app.services.progress_service import try_advance_topic

    try:
        result = await try_advance_topic(user_id)
        return json.dumps(result)
    except Exception as exc:
        logger.error("advance_topic failed: %s", exc)
        return json.dumps({"error": str(exc)})


# ── Tool registry ─────────────────────────────────────────────────────────────
ALL_TOOLS = [
    validate_student_notes,
    get_student_profile,
    query_past_struggles,
    log_problem_solved,
    advance_topic,
]
