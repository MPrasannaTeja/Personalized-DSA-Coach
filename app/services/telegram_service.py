"""
Telegram notification service.

Used by both the Celery daily-nudge task and the FastAPI app
(e.g. immediate confirmation messages).
"""

import logging
from typing import Optional

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from app.config import settings

logger = logging.getLogger(__name__)

_bot: Optional[Bot] = None


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(token=settings.telegram_bot_token)
    return _bot


async def send_message(chat_id: str, text: str, parse_mode: str = ParseMode.MARKDOWN) -> bool:
    """
    Send a Telegram message to a specific chat_id.
    Returns True on success, False on failure (non-raising).
    """
    try:
        bot = get_bot()
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
        )
        logger.info("Telegram message sent to %s", chat_id)
        return True
    except TelegramError as exc:
        logger.error("Telegram send failed for chat_id=%s: %s", chat_id, exc)
        return False


def format_daily_nudge(
    username: str,
    streak: int,
    motivational_message: str,
    problem_assignment: str,
    recommended_difficulty: str,
    recommended_count: int,
) -> str:
    """Format the daily nudge message for Telegram (Markdown)."""
    streak_emoji = "🔥" * min(streak, 5)
    diff_emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(recommended_difficulty, "⚪")

    return (
        f"*📚 DSA Coach — Daily Assignment*\n\n"
        f"Hey *{username}*! {streak_emoji} {streak}-day streak\n\n"
        f"_{motivational_message}_\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"*Today's Problems* {diff_emoji}\n"
        f"Difficulty: *{recommended_difficulty.capitalize()}* | Count: *{recommended_count}*\n\n"
        f"{problem_assignment}\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"_Open the coach to log your solutions and get hints._"
    )
