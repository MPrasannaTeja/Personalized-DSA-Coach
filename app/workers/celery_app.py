"""
Celery application + beat schedule.

Workers
-------
Run the worker:
    celery -A app.workers.celery_app worker --loglevel=info

Run the scheduler (beat):
    celery -A app.workers.celery_app beat --loglevel=info

Or both together (dev only):
    celery -A app.workers.celery_app worker --beat --loglevel=info
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

from celery import Celery
from celery.schedules import crontab

from app.config import settings

logger = logging.getLogger(__name__)

# ── Celery app ────────────────────────────────────────────────────────────────
celery_app = Celery(
    "dsa_coach",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=settings.daily_nudge_timezone,
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,           # only ack after task completes (safer)
    worker_prefetch_multiplier=1,  # one task at a time per worker
    result_expires=86400,          # keep results 24h
)

# ── Beat schedule ─────────────────────────────────────────────────────────────
celery_app.conf.beat_schedule = {
    "daily-dsa-nudge": {
        "task": "app.workers.tasks.send_daily_nudge_to_all_users",
        "schedule": crontab(
            hour=settings.daily_nudge_hour,
            minute=settings.daily_nudge_minute,
        ),
        "options": {"expires": 3600},  # drop if not executed within 1 hour
    },
}
