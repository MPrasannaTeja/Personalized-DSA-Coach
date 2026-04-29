"""
Celery tasks.

Note: Celery tasks are synchronous by default. We use asyncio.run()
to call into our async services. For production scale, consider
using celery with gevent/eventlet or a dedicated async task runner.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

from app.config import settings
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# ── Sync engine for Celery (psycopg2, not asyncpg) ───────────────────────────
_sync_engine = None


def get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        from sqlalchemy import create_engine
        _sync_engine = create_engine(
            settings.database_url_sync,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
    return _sync_engine


def get_sync_session() -> Session:
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(bind=get_sync_engine(), autocommit=False, autoflush=False)
    return SessionLocal()


# ── Task: send daily nudge to ALL active users ────────────────────────────────

@celery_app.task(
    name="app.workers.tasks.send_daily_nudge_to_all_users",
    bind=True,
    max_retries=2,
    default_retry_delay=300,  # retry after 5 min on failure
)
def send_daily_nudge_to_all_users(self):
    """
    Cron task — runs daily at configured time (default 6 PM IST).

    For each active user with notifications enabled:
    1. Pull their progress profile from DB
    2. Call the LLM to generate a personalised assignment
    3. Save assignment to daily_assignments table
    4. Send via Telegram
    """
    logger.info("Starting daily nudge task — %s", datetime.now(timezone.utc).isoformat())

    try:
        from app.db.models import User, DailyAssignment
        db = get_sync_session()

        # Fetch all users with notifications enabled and a telegram_chat_id
        users = (
            db.execute(
                select(User).where(
                    User.notifications_enabled == True,  # noqa: E712
                    User.telegram_chat_id.isnot(None),
                )
            )
            .scalars()
            .all()
        )

        logger.info("Found %d users to nudge.", len(users))

        for user in users:
            try:
                send_nudge_to_user.delay(str(user.id))
            except Exception as exc:
                logger.error("Failed to queue nudge for user %s: %s", user.id, exc)

        db.close()
        return {"status": "queued", "user_count": len(users)}

    except Exception as exc:
        logger.error("Daily nudge task failed: %s", exc)
        raise self.retry(exc=exc)


# ── Task: generate + send nudge for ONE user ─────────────────────────────────

@celery_app.task(
    name="app.workers.tasks.send_nudge_to_user",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_nudge_to_user(self, user_id: str):
    """
    Generate and deliver a personalised daily nudge for a single user.
    Runs as a sub-task so failures are isolated per-user.
    """
    try:
        result = asyncio.run(_async_send_nudge(user_id))
        logger.info("Nudge sent to user %s: %s", user_id, result)
        return result
    except Exception as exc:
        logger.error("Nudge failed for user %s: %s", user_id, exc)
        raise self.retry(exc=exc)


async def _async_send_nudge(user_id: str) -> dict:
    """
    Async implementation of the nudge pipeline:
    profile → LLM assignment → DB save → Telegram send
    """
    from app.services.progress_service import get_user_profile, save_daily_assignment
    from app.services.telegram_service import send_message, format_daily_nudge
    from app.agent.prompts.coach_prompts import (
        DAILY_ASSIGNMENT_PROMPT,
        PHASES,
    )
    from app.services.llm import get_structured_llm
    from app.db.session import AsyncSessionLocal
    import json

    # 1. Pull live profile
    profile = await get_user_profile(user_id)

    phase_idx = profile["current_phase_idx"]
    topic_idx = profile["current_topic_idx"]
    phase = PHASES[phase_idx]
    topic = phase["topics"][topic_idx]
    topic_stats = profile["topic_stats"].get(topic["id"], {})
    solved = topic_stats.get("total_solved", 0)
    clean_rate = (
        topic_stats.get("clean_solve_count", 0) / solved if solved > 0 else 0
    )
    hint_rate = (
        topic_stats.get("hint_used_count", 0) / solved if solved > 0 else 0
    )

    # Dynamic recommendation
    if clean_rate > 0.7 and hint_rate < 0.3 and solved >= 5:
        rec_difficulty = "hard"
        rec_count = 3
    elif clean_rate > 0.5 and solved >= 3:
        rec_difficulty = "medium"
        rec_count = 2
    else:
        rec_difficulty = "easy"
        rec_count = 1

    student_context = json.dumps({
        "username": profile["username"],
        "streak": profile["streak"],
        "total_problems": profile["total_problems_solved"],
        "current_phase": phase["title"],
        "current_topic": topic["name"],
        "topic_patterns": topic["patterns"],
        "problems_solved_this_topic": solved,
        "min_required": topic["min_problems"],
        "clean_solve_rate": round(clean_rate, 2),
        "recommended_difficulty": rec_difficulty,
        "recommended_count": rec_count,
        "last_solved": profile.get("last_solved_date"),
    }, indent=2)

    # 2. Generate assignment via LLM
    llm = get_structured_llm()
    chain = DAILY_ASSIGNMENT_PROMPT | llm

    response = await chain.ainvoke({
        "student_context": student_context,
        "count": rec_count,
    })

    raw = response.content.strip().replace("```json", "").replace("```", "")
    try:
        assignment_data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON for daily assignment: %s", raw)
        assignment_data = {
            "motivational_message": "Keep going. Every problem counts.",
            "problem_assignment": f"Do {rec_count} {rec_difficulty} problem(s) from your current topic: {topic['name']}.",
            "recommended_difficulty": rec_difficulty,
            "recommended_count": rec_count,
        }

    motivational_message = assignment_data.get("motivational_message", "")
    problem_assignment = assignment_data.get("problem_assignment", "")

    # 3. Save to DB
    async with AsyncSessionLocal() as db:
        await save_daily_assignment(
            db=db,
            user_id=user_id,
            phase_idx=phase_idx,
            topic_id=topic["id"],
            motivational_message=motivational_message,
            problem_assignment=problem_assignment,
            recommended_difficulty=rec_difficulty,
            recommended_count=rec_count,
        )
        await db.commit()

    # 4. Send Telegram message
    chat_id = profile.get("telegram_chat_id") or settings.telegram_default_chat_id
    if not chat_id:
        logger.warning("No telegram_chat_id for user %s, skipping send.", user_id)
        return {"status": "skipped", "reason": "no telegram_chat_id"}

    message_text = format_daily_nudge(
        username=profile["username"],
        streak=profile["streak"],
        motivational_message=motivational_message,
        problem_assignment=problem_assignment,
        recommended_difficulty=rec_difficulty,
        recommended_count=rec_count,
    )

    sent = await send_message(chat_id=chat_id, text=message_text)

    return {
        "status": "sent" if sent else "telegram_failed",
        "user_id": user_id,
        "recommended_difficulty": rec_difficulty,
        "recommended_count": rec_count,
    }


# ── Task: sync unsync'd notes to ChromaDB ─────────────────────────────────────

@celery_app.task(name="app.workers.tasks.sync_notes_to_chroma")
def sync_notes_to_chroma():
    """
    Retry any PatternNotes that failed to sync to ChromaDB.
    Run this as a periodic task (e.g. every hour) to catch failures.
    """
    try:
        result = asyncio.run(_async_sync_notes())
        return result
    except Exception as exc:
        logger.error("sync_notes_to_chroma failed: %s", exc)
        raise


async def _async_sync_notes() -> dict:
    from app.db.models import PatternNote
    from app.db.session import AsyncSessionLocal
    from app.services.vector_store import upsert_pattern_note
    from sqlalchemy import select, update

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(PatternNote).where(PatternNote.synced_to_chroma == False).limit(50)  # noqa: E712
        )
        notes = result.scalars().all()

        synced = 0
        for note in notes:
            try:
                await upsert_pattern_note(
                    doc_id=note.id,
                    user_id=note.user_id,
                    topic_id=note.topic_id,
                    pattern_name=note.pattern_name,
                    note_text=note.note_text,
                )
                note.synced_to_chroma = True
                note.chroma_doc_id = note.id
                synced += 1
            except Exception as exc:
                logger.warning("Failed to sync note %s: %s", note.id, exc)

        await db.commit()
        return {"synced": synced, "total_pending": len(notes)}
