"""
DSA Coach Backend — FastAPI entry point.

Run locally:
    uvicorn app.main:app --reload --port 8000

Production:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    On startup:
    - Run DB migrations (dev convenience; in prod, run alembic upgrade head separately)
    - Warm up the LangGraph agent (loads model weights into memory)
    - Verify ChromaDB is reachable

    On shutdown:
    - Dispose DB engine connections
    """
    logger.info("🚀 DSA Coach starting up...")

    # 1. DB — create tables if they don't exist (dev only; use Alembic in prod)
    if not settings.is_production:
        from app.db.models import Base
        from app.db.session import engine
        from sqlalchemy import text
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ DB tables ensured.")

    # 2. Warm up the LangGraph graph (compiles the graph)
    from app.agent.coach_graph import get_coach_graph
    get_coach_graph()
    logger.info("✅ LangGraph coach graph compiled.")

    # 3. Verify ChromaDB reachable (non-blocking)
    try:
        import chromadb
        client = await chromadb.AsyncHttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
        )
        await client.heartbeat()
        logger.info("✅ ChromaDB reachable.")
    except Exception as exc:
        logger.warning("⚠️  ChromaDB not reachable at startup: %s", exc)

    yield  # ── application runs here ──────────────────────────────────────

    logger.info("🛑 DSA Coach shutting down...")
    from app.db.session import engine
    await engine.dispose()
    logger.info("✅ DB connections closed.")


# ── App factory ───────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title="DSA Coach Agent API",
        description=(
            "Agentic backend for the DSA Coach system. "
            "Powered by LangGraph + Claude + ChromaDB + PostgreSQL."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Global exception handler ──────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s %s: %s", request.method, request.url, exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal error occurred. Please try again."},
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    from app.api.routes.chat import router as chat_router
    from app.api.routes.routes import (
        hints_router,
        notes_router,
        nudge_router,
        problems_router,
        progress_router,
        users_router,
    )

    prefix = settings.api_v1_prefix

    app.include_router(chat_router,     prefix=prefix)
    app.include_router(users_router,    prefix=prefix)
    app.include_router(progress_router, prefix=prefix)
    app.include_router(problems_router, prefix=prefix)
    app.include_router(notes_router,    prefix=prefix)
    app.include_router(hints_router,    prefix=prefix)
    app.include_router(nudge_router,    prefix=prefix)

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/health", tags=["Meta"])
    async def health():
        return {"status": "ok", "env": settings.app_env}

    @app.get("/", tags=["Meta"])
    async def root():
        return {
            "service": "DSA Coach Agent API",
            "version": "0.1.0",
            "docs": "/docs",
        }

    return app


app = create_app()
