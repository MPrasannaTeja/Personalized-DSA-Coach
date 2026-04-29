"""
Integration tests — spins up the FastAPI app with a real test DB.

Prerequisites:
    - A running Postgres (can use docker-compose)
    - TEST_DATABASE_URL env var pointing to a test DB

Run: pytest tests/integration/ -v
"""

import json
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client():
    """Create test client with mocked external services."""
    # Patch heavy external deps so tests run without real infra
    with (
        patch("app.services.vector_store._get_collection", new_callable=AsyncMock),
        patch("app.services.llm.get_llm") as mock_llm_factory,
        patch("app.services.llm.get_structured_llm") as mock_structured_llm_factory,
    ):
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Test response", tool_calls=[]))
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_llm_factory.return_value = mock_llm
        mock_structured_llm_factory.return_value = mock_llm

        from app.main import app
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac


# ── Health check ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ── User creation ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="Requires TEST_DATABASE_URL"
)
async def test_create_user(client):
    response = await client.post(
        "/api/v1/users",
        json={
            "username": "test_student_001",
            "telegram_chat_id": "999888777",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "test_student_001"
    assert data["streak"] == 0
    assert data["current_phase_idx"] == 0
    return data["id"]


# ── Chat endpoint ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_returns_404_for_unknown_user(client):
    response = await client.post(
        "/api/v1/chat",
        json={
            "user_id": "00000000-0000-0000-0000-000000000000",
            "message": "Hello coach!",
        },
    )
    assert response.status_code == 404


# ── Notes validation ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_notes_validation_rejected_when_too_short(client):
    """Notes under 30 chars should be rejected by Pydantic before hitting LLM."""
    response = await client.post(
        "/api/v1/notes/submit",
        json={
            "user_id": "00000000-0000-0000-0000-000000000000",
            "topic_id": "arrays",
            "pattern_name": "Sliding Window",
            "note_text": "too short",  # will fail Pydantic min_length=30
        },
    )
    assert response.status_code == 422  # Pydantic validation error


# ── Schemas ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_log_problem_schema_validation(client):
    """Invalid difficulty should be rejected by Pydantic."""
    response = await client.post(
        "/api/v1/problems/log",
        json={
            "user_id": "00000000-0000-0000-0000-000000000000",
            "topic_id": "arrays",
            "problem_name": "Two Sum",
            "difficulty": "INVALID",  # not in Literal["easy","medium","hard"]
        },
    )
    assert response.status_code == 422
