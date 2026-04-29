"""
Async SQLAlchemy engine + session factory.

Usage
-----
    from app.db.session import get_async_session

    async def endpoint(db: AsyncSession = Depends(get_async_session)):
        ...
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

# ── Engine ────────────────────────────────────────────────────────────────────
# pool_pre_ping detects stale connections after Postgres restarts
engine = create_async_engine(
    settings.database_url,
    echo=not settings.is_production,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

# ── Session factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # keep objects usable after commit inside async context
    autocommit=False,
    autoflush=False,
)


# ── FastAPI dependency ────────────────────────────────────────────────────────
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a transactional session; roll back on error, always close."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
