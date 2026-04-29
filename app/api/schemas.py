"""
Pydantic v2 schemas for API request/response validation.
"""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: Literal["human", "assistant"]
    content: str


class ChatRequest(BaseModel):
    user_id: str = Field(..., description="User UUID")
    message: str = Field(..., min_length=1, max_length=4000)
    # Optional: caller can pass pre-built context to avoid extra DB round-trip
    context_override: Optional[dict[str, Any]] = None


class ChatResponse(BaseModel):
    reply: str
    tool_calls_made: list[str] = []
    context_snapshot: Optional[dict[str, Any]] = None


# ── User ──────────────────────────────────────────────────────────────────────

class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=128)
    telegram_chat_id: Optional[str] = None
    email: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    username: str
    telegram_chat_id: Optional[str]
    current_phase_idx: int
    current_topic_idx: int
    streak: int
    total_problems_solved: int
    start_date: Optional[datetime]

    model_config = {"from_attributes": True}


# ── Problem logging ───────────────────────────────────────────────────────────

class LogProblemRequest(BaseModel):
    user_id: str
    topic_id: str
    problem_name: str = Field(..., min_length=1, max_length=256)
    difficulty: Literal["easy", "medium", "hard"]
    used_hint: bool = False
    time_taken_minutes: Optional[int] = Field(None, ge=0, le=600)
    patterns_used: Optional[str] = None  # comma-separated

    @field_validator("patterns_used")
    @classmethod
    def clean_patterns(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return ",".join(p.strip() for p in v.split(",") if p.strip())
        return v


class LogProblemResponse(BaseModel):
    success: bool
    streak: int
    total_problems: int
    topic_total: int
    topic_completed: bool
    message: str


# ── Notes ─────────────────────────────────────────────────────────────────────

class SubmitNotesRequest(BaseModel):
    user_id: str
    topic_id: str
    pattern_name: str = Field(..., min_length=2, max_length=128)
    note_text: str = Field(..., min_length=30, max_length=5000)
    solved_problem_id: Optional[str] = None
    problem_context: Optional[str] = None  # for validation prompt


class NotesValidationResponse(BaseModel):
    approved: bool
    score: int
    feedback: str
    note_id: Optional[str] = None


# ── Hint ──────────────────────────────────────────────────────────────────────

class HintRequest(BaseModel):
    user_id: str
    topic_id: str
    problem_description: str = Field(..., min_length=10, max_length=2000)
    pattern_guess: Optional[str] = None   # user's pattern attempt
    hint_level: Literal["pattern_name", "clue", "full"] = "clue"


class HintResponse(BaseModel):
    hint_text: str
    past_struggles_referenced: list[str] = []
    blind_spots_identified: list[str] = []


# ── Progress ──────────────────────────────────────────────────────────────────

class ProgressResponse(BaseModel):
    user_id: str
    username: str
    current_phase_idx: int
    current_topic_idx: int
    streak: int
    total_problems_solved: int
    topic_stats: dict[str, Any]
    recent_problems: list[dict[str, Any]]


# ── Daily assignment ──────────────────────────────────────────────────────────

class TriggerNudgeRequest(BaseModel):
    user_id: str
    force: bool = False  # bypass already-sent-today check


class TriggerNudgeResponse(BaseModel):
    status: str
    message: str
