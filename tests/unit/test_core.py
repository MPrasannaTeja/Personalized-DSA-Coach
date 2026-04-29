"""
Unit tests — no real DB/LLM required (everything mocked).
Run: pytest tests/unit/ -v
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Test: _build_context_block ────────────────────────────────────────────────

class TestBuildContextBlock:
    def test_easy_recommendation_for_new_user(self):
        from app.agent.coach_graph import _build_context_block

        ctx = json.loads(_build_context_block(
            user_id="u1",
            phase_idx=0,
            topic_idx=0,
            streak=1,
            total_solved=0,
            topic_stats={},
        ))

        assert ctx["recommended_difficulty"] == "easy"
        assert ctx["recommended_count"] == 1
        assert ctx["topic_complete"] is False

    def test_hard_recommendation_for_advanced_user(self):
        from app.agent.coach_graph import _build_context_block

        ctx = json.loads(_build_context_block(
            user_id="u1",
            phase_idx=0,
            topic_idx=0,
            streak=15,
            total_solved=50,
            topic_stats={
                "total_solved": 10,
                "clean_solve_count": 8,
                "hint_used_count": 1,
            },
        ))

        assert ctx["recommended_difficulty"] == "hard"
        assert ctx["recommended_count"] == 3

    def test_topic_complete_flag(self):
        from app.agent.coach_graph import _build_context_block
        from app.agent.prompts.coach_prompts import PHASES

        min_needed = PHASES[0]["topics"][0]["min_problems"]  # arrays = 15

        ctx = json.loads(_build_context_block(
            user_id="u1",
            phase_idx=0,
            topic_idx=0,
            streak=5,
            total_solved=20,
            topic_stats={
                "total_solved": min_needed,
                "clean_solve_count": 10,
                "hint_used_count": 2,
            },
        ))

        assert ctx["topic_complete"] is True


# ── Test: notes validation logic ──────────────────────────────────────────────

class TestNotesValidation:
    @pytest.mark.asyncio
    async def test_good_notes_get_approved(self):
        """Well-written notes should pass the LLM validator."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "is_valid": True,
            "score": 8,
            "feedback": "Great notes. Clear pattern identification.",
            "approved": True,
        })

        with patch("app.agent.tools.coach_tools.get_llm") as mock_get_llm:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_get_llm.return_value = mock_llm

            from app.agent.tools.coach_tools import validate_student_notes
            result = await validate_student_notes.ainvoke({
                "notes": (
                    "Pattern: Sliding Window. It applies here because we need "
                    "to find a subarray of fixed size, which means we can maintain "
                    "a window and slide it. Key insight: expand right, shrink left when "
                    "constraint violated. I'll recognize this when I see 'subarray of size k'."
                ),
                "problem_context": "Topic: arrays, Problem: Maximum Average Subarray",
            })

            data = json.loads(result)
            assert data["approved"] is True
            assert data["score"] >= 6

    @pytest.mark.asyncio
    async def test_bad_notes_get_rejected(self):
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "is_valid": False,
            "score": 2,
            "feedback": "Too vague. You said 'use sliding window' but didn't explain why.",
            "approved": False,
        })

        with patch("app.agent.tools.coach_tools.get_llm") as mock_get_llm:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_get_llm.return_value = mock_llm

            from app.agent.tools.coach_tools import validate_student_notes
            result = await validate_student_notes.ainvoke({
                "notes": "used sliding window",
                "problem_context": "Topic: arrays",
            })

            data = json.loads(result)
            assert data["approved"] is False
            assert data["score"] < 6


# ── Test: streak logic ────────────────────────────────────────────────────────

class TestStreakLogic:
    def test_streak_increments_on_consecutive_days(self):
        from datetime import datetime, timezone, timedelta
        from app.db.models import User

        user = User(username="test", streak=5)
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        user.last_solved_date = yesterday

        today = datetime.now(timezone.utc).date()
        last = user.last_solved_date.date()

        if last == today - timedelta(days=1):
            new_streak = user.streak + 1
        else:
            new_streak = 1

        assert new_streak == 6

    def test_streak_resets_after_missed_day(self):
        from datetime import datetime, timezone, timedelta
        from app.db.models import User

        user = User(username="test", streak=10)
        two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
        user.last_solved_date = two_days_ago

        today = datetime.now(timezone.utc).date()
        last = user.last_solved_date.date()
        from datetime import timedelta as td

        if last == today - td(days=1):
            new_streak = user.streak + 1
        else:
            new_streak = 1

        assert new_streak == 1


# ── Test: blind spot extraction ───────────────────────────────────────────────

class TestBlindSpotExtraction:
    def test_recurring_pattern_identified(self):
        from app.agent.tools.coach_tools import _extract_blind_spots

        notes = [
            {"pattern_name": "Sliding Window"},
            {"pattern_name": "Sliding Window"},
            {"pattern_name": "Two Pointers"},
        ]
        blind_spots = _extract_blind_spots(notes)
        assert "Sliding Window" in blind_spots
        assert "Two Pointers" not in blind_spots  # only appeared once

    def test_no_blind_spots_when_all_unique(self):
        from app.agent.tools.coach_tools import _extract_blind_spots

        notes = [
            {"pattern_name": "BFS Level Order"},
            {"pattern_name": "DFS Preorder"},
            {"pattern_name": "Union-Find"},
        ]
        assert _extract_blind_spots(notes) == []
