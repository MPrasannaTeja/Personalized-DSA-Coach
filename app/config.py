"""
Centralised application configuration loaded from environment / .env file.
All other modules import `settings` from here — never read os.environ directly.
"""

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM (Ollama — local, no API key needed) ──────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama2"     # override in .env if you have a different model

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str           # async (asyncpg)
    database_url_sync: str      # sync (psycopg2) — used by Alembic + Celery

    # ── Redis / Celery ────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # ── ChromaDB ──────────────────────────────────────────────────────────────
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_collection_name: str = "dsa_pattern_notes"

    # ── Telegram ──────────────────────────────────────────────────────────────
    telegram_bot_token: str
    telegram_default_chat_id: str = ""

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: str = "development"
    app_secret_key: str
    api_v1_prefix: str = "/api/v1"
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    log_level: str = "INFO"

    # ── Celery Beat ───────────────────────────────────────────────────────────
    daily_nudge_hour: int = 18
    daily_nudge_minute: int = 0
    daily_nudge_timezone: str = "Asia/Kolkata"

    # ── Derived helpers ───────────────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


# Module-level singleton — import this everywhere
settings = get_settings()
