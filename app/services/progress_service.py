"""
Progress service — all database operations for user progress tracking.

These functions are called both by FastAPI endpoints (via async sessions)
and by Celery workers (via sync sessions through a different engine).
The async versions are the primary path.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DailyAssignment, PatternNote, SolvedProblem, TopicProgress, User
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


# ── User helpers ──────────────────────────────────────────────────────────────

async def get_or_create_user(
    db: AsyncSession,
    username: str,
    telegram_chat_id: str | None = None,
    email: str | None = None,
) -> User:
    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            username=username,
            telegram_chat_id=telegram_chat_id,
            email=email,
        )
        db.add(user)
        await db.flush()
        logger.info("Created new user: %s", username)

    return user


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


# ── Progress summary ──────────────────────────────────────────────────────────

async def get_user_profile(user_id: str) -> dict[str, Any]:
    """
    Build a full progress profile dict for use in agent context and daily assignments.
    Uses its own session (safe to call from tools).
    """
    async with AsyncSessionLocal() as db:
        user = await get_user_by_id(db, user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Fetch all topic progress rows
        tp_result = await db.execute(
            select(TopicProgress).where(TopicProgress.user_id == user_id)
        )
        topic_rows = tp_result.scalars().all()

        # Fetch recent 10 solved problems
        sp_result = await db.execute(
            select(SolvedProblem)
            .where(SolvedProblem.user_id == user_id)
            .order_by(SolvedProblem.solved_at.desc())
            .limit(10)
        )
        recent_problems = sp_result.scalars().all()

        topic_stats = {
            row.topic_id: {
                "total_solved": row.total_solved,
                "solved_easy": row.solved_easy,
                "solved_medium": row.solved_medium,
                "solved_hard": row.solved_hard,
                "hint_used_count": row.hint_used_count,
                "clean_solve_count": row.clean_solve_count,
                "is_completed": row.is_completed,
            }
            for row in topic_rows
        }

        return {
            "user_id": user_id,
            "username": user.username,
            "current_phase_idx": user.current_phase_idx,
            "current_topic_idx": user.current_topic_idx,
            "streak": user.streak,
            "total_problems_solved": user.total_problems_solved,
            "start_date": user.start_date.isoformat() if user.start_date else None,
            "last_solved_date": user.last_solved_date.isoformat() if user.last_solved_date else None,
            "telegram_chat_id": user.telegram_chat_id,
            "notifications_enabled": user.notifications_enabled,
            "topic_stats": topic_stats,
            "recent_problems": [
                {
                    "problem_name": p.problem_name,
                    "difficulty": p.difficulty,
                    "used_hint": p.used_hint,
                    "clean_solve": p.clean_solve,
                    "solved_at": p.solved_at.isoformat(),
                }
                for p in recent_problems
            ],
        }


# ── Record a solved problem ───────────────────────────────────────────────────

async def record_problem_solved(
    user_id: str,
    topic_id: str,
    problem_name: str,
    difficulty: str,
    used_hint: bool,
    clean_solve: bool,
    notes_submitted: bool,
    time_taken_minutes: int = 0,
    patterns_used: str = "",
) -> dict[str, Any]:
    """Persist a solved problem and update all counters atomically."""
    async with AsyncSessionLocal() as db:
        async with db.begin():
            user = await get_user_by_id(db, user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")

            # ── Solved problem record ────────────────────────────────────
            problem = SolvedProblem(
                user_id=user_id,
                topic_id=topic_id,
                problem_name=problem_name,
                difficulty=difficulty,
                used_hint=used_hint,
                clean_solve=clean_solve,
                notes_submitted=notes_submitted,
                time_taken_minutes=time_taken_minutes or None,
                patterns_used=patterns_used or None,
            )
            db.add(problem)

            # ── Topic progress upsert ────────────────────────────────────
            tp_result = await db.execute(
                select(TopicProgress)
                .where(TopicProgress.user_id == user_id, TopicProgress.topic_id == topic_id)
            )
            tp = tp_result.scalar_one_or_none()
            if tp is None:
                from app.agent.prompts.coach_prompts import PHASES
                topic_name = topic_id
                phase_idx = user.current_phase_idx
                for phase in PHASES:
                    for t in phase["topics"]:
                        if t["id"] == topic_id:
                            topic_name = t["name"]
                            phase_idx = phase["id"] - 1
                tp = TopicProgress(
                    user_id=user_id,
                    topic_id=topic_id,
                    topic_name=topic_name,
                    phase_idx=phase_idx,
                )
                db.add(tp)

            # Update counters
            tp.total_solved += 1
            if difficulty == "easy":
                tp.solved_easy += 1
            elif difficulty == "medium":
                tp.solved_medium += 1
            elif difficulty == "hard":
                tp.solved_hard += 1
            if used_hint:
                tp.hint_used_count += 1
            if clean_solve:
                tp.clean_solve_count += 1

            # Check topic completion
            from app.agent.prompts.coach_prompts import PHASES
            for phase in PHASES:
                for t in phase["topics"]:
                    if t["id"] == topic_id and tp.total_solved >= t["min_problems"]:
                        tp.is_completed = True
                        if not tp.completed_at:
                            tp.completed_at = datetime.now(timezone.utc)

            # ── User-level counters + streak ─────────────────────────────
            user.total_problems_solved += 1
            today = datetime.now(timezone.utc).date()
            if user.last_solved_date:
                last_date = user.last_solved_date.date()
                from datetime import timedelta
                if last_date == today:
                    pass  # same day, no streak change
                elif last_date == today - timedelta(days=1):
                    user.streak += 1
                else:
                    user.streak = 1  # broke the streak
            else:
                user.streak = 1
            user.last_solved_date = datetime.now(timezone.utc)

        return {
            "success": True,
            "problem_name": problem_name,
            "streak": user.streak,
            "total_problems": user.total_problems_solved,
            "topic_total": tp.total_solved,
            "topic_completed": tp.is_completed,
        }


# ── Advance topic ─────────────────────────────────────────────────────────────

async def try_advance_topic(user_id: str) -> dict[str, Any]:
    """
    Advance the user to the next topic if current topic is complete.
    Returns the new topic/phase info.
    """
    from app.agent.prompts.coach_prompts import PHASES

    async with AsyncSessionLocal() as db:
        async with db.begin():
            user = await get_user_by_id(db, user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")

            phase = PHASES[user.current_phase_idx]
            if user.current_topic_idx < len(phase["topics"]) - 1:
                user.current_topic_idx += 1
            elif user.current_phase_idx < len(PHASES) - 1:
                user.current_phase_idx += 1
                user.current_topic_idx = 0
            else:
                return {"message": "Congratulations! You've completed all phases.", "advanced": False}

            new_phase = PHASES[user.current_phase_idx]
            new_topic = new_phase["topics"][user.current_topic_idx]
            return {
                "advanced": True,
                "new_phase_idx": user.current_phase_idx,
                "new_topic_idx": user.current_topic_idx,
                "new_phase": new_phase["title"],
                "new_topic": new_topic["name"],
                "new_patterns": new_topic["patterns"],
            }


# ── Save pattern note ─────────────────────────────────────────────────────────

async def save_pattern_note(
    db: AsyncSession,
    user_id: str,
    topic_id: str,
    pattern_name: str,
    note_text: str,
    solved_problem_id: str | None = None,
) -> PatternNote:
    """Persist a note to Postgres and queue ChromaDB upsert."""
    note = PatternNote(
        user_id=user_id,
        topic_id=topic_id,
        pattern_name=pattern_name,
        note_text=note_text,
        solved_problem_id=solved_problem_id,
    )
    db.add(note)
    await db.flush()  # get the generated id

    # Fire-and-forget upsert to ChromaDB
    try:
        from app.services.vector_store import upsert_pattern_note
        await upsert_pattern_note(
            doc_id=note.id,
            user_id=user_id,
            topic_id=topic_id,
            pattern_name=pattern_name,
            note_text=note_text,
        )
        note.synced_to_chroma = True
        note.chroma_doc_id = note.id
    except Exception as exc:
        logger.warning("ChromaDB upsert failed (will retry later): %s", exc)

    return note


# ── Save daily assignment ─────────────────────────────────────────────────────

async def save_daily_assignment(
    db: AsyncSession,
    user_id: str,
    phase_idx: int,
    topic_id: str,
    motivational_message: str,
    problem_assignment: str,
    recommended_difficulty: str,
    recommended_count: int,
) -> DailyAssignment:
    assignment = DailyAssignment(
        user_id=user_id,
        phase_idx=phase_idx,
        topic_id=topic_id,
        motivational_message=motivational_message,
        problem_assignment=problem_assignment,
        recommended_difficulty=recommended_difficulty,
        recommended_count=recommended_count,
    )
    db.add(assignment)
    await db.flush()
    return assignment
