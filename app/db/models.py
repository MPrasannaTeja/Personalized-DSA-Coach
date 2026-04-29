"""
SQLAlchemy ORM models for the DSA Coach system.

Tables
------
users               — one row per learner
topic_progress      — per-user, per-topic tracking
solved_problems     — individual problem log entries
pattern_notes       — raw notes (also mirrored to ChromaDB)
daily_assignments   — what the agent assigned on each day
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ── Base ─────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """Shared declarative base."""
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Users ─────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(256), unique=True, nullable=True)

    # ── Progress meta ──────────────────────────────────────────────────────
    current_phase_idx: Mapped[int] = mapped_column(Integer, default=0)
    current_topic_idx: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    last_solved_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    total_problems_solved: Mapped[int] = mapped_column(Integer, default=0)
    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # ── Notification preferences ───────────────────────────────────────────
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # ── Timestamps ────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relationships ─────────────────────────────────────────────────────
    topic_progress: Mapped[list["TopicProgress"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    solved_problems: Mapped[list["SolvedProblem"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", order_by="SolvedProblem.solved_at"
    )
    pattern_notes: Mapped[list["PatternNote"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    daily_assignments: Mapped[list["DailyAssignment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


# ── TopicProgress ─────────────────────────────────────────────────────────────

class TopicProgress(Base):
    __tablename__ = "topic_progress"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    topic_id: Mapped[str] = mapped_column(String(64), nullable=False)   # e.g. "arrays", "dp1"
    topic_name: Mapped[str] = mapped_column(String(128), nullable=False)
    phase_idx: Mapped[int] = mapped_column(Integer, nullable=False)

    # ── Counters ──────────────────────────────────────────────────────────
    solved_easy: Mapped[int] = mapped_column(Integer, default=0)
    solved_medium: Mapped[int] = mapped_column(Integer, default=0)
    solved_hard: Mapped[int] = mapped_column(Integer, default=0)
    hint_used_count: Mapped[int] = mapped_column(Integer, default=0)
    clean_solve_count: Mapped[int] = mapped_column(Integer, default=0)
    total_solved: Mapped[int] = mapped_column(Integer, default=0)

    # ── State ─────────────────────────────────────────────────────────────
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="topic_progress")


# ── SolvedProblem ─────────────────────────────────────────────────────────────

class SolvedProblem(Base):
    __tablename__ = "solved_problems"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    topic_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # ── Problem metadata ──────────────────────────────────────────────────
    leetcode_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    problem_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False)   # easy | medium | hard
    patterns_used: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # comma-separated

    # ── Solve quality ─────────────────────────────────────────────────────
    used_hint: Mapped[bool] = mapped_column(Boolean, default=False)
    clean_solve: Mapped[bool] = mapped_column(Boolean, default=True)
    notes_submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    time_taken_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    solved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="solved_problems")


# ── PatternNote ───────────────────────────────────────────────────────────────

class PatternNote(Base):
    __tablename__ = "pattern_notes"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    solved_problem_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("solved_problems.id", ondelete="SET NULL"), nullable=True
    )

    topic_id: Mapped[str] = mapped_column(String(64), nullable=False)
    pattern_name: Mapped[str] = mapped_column(String(128), nullable=False)
    note_text: Mapped[str] = mapped_column(Text, nullable=False)

    # ── ChromaDB sync ─────────────────────────────────────────────────────
    chroma_doc_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    synced_to_chroma: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="pattern_notes")


# ── DailyAssignment ───────────────────────────────────────────────────────────

class DailyAssignment(Base):
    __tablename__ = "daily_assignments"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    assignment_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    phase_idx: Mapped[int] = mapped_column(Integer, nullable=False)
    topic_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # ── Agent-generated content ───────────────────────────────────────────
    motivational_message: Mapped[str] = mapped_column(Text, nullable=False)
    problem_assignment: Mapped[str] = mapped_column(Text, nullable=False)   # full agent text
    recommended_difficulty: Mapped[str] = mapped_column(String(16), nullable=False)
    recommended_count: Mapped[int] = mapped_column(Integer, default=2)

    # ── Delivery ──────────────────────────────────────────────────────────
    telegram_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="daily_assignments")
