from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    chesscom_username = Column(String(64), nullable=True)
    chesscom_username_norm = Column(String(64), unique=True, nullable=True, index=True)
    token_version = Column(Integer, nullable=False, default=1)
    timezone = Column(String(64), nullable=False, default="UTC")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    games = relationship("Game", back_populates="user", cascade="all, delete-orphan")
    puzzle_states = relationship("PuzzleReviewState", back_populates="user", cascade="all, delete-orphan")
    skill_states = relationship("SkillState", back_populates="user", cascade="all, delete-orphan")
    daily_plans = relationship("DailyPlan", back_populates="user", cascade="all, delete-orphan")


class Game(Base):
    __tablename__ = "games"
    __table_args__ = (
        UniqueConstraint("user_id", "chess_com_url", name="uq_games_user_chesscom_url"),
        Index("ix_games_user_played_at", "user_id", "played_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    chess_com_url = Column(String(512), nullable=True, index=True)
    pgn = Column(Text, nullable=True)
    event = Column(String(256), nullable=True)
    date = Column(String(32), nullable=True)
    white = Column(String(128), nullable=True)
    black = Column(String(128), nullable=True)
    result = Column(String(16), nullable=True)
    player_color = Column(String(16), nullable=True)
    opponent = Column(String(128), nullable=True)
    player_outcome = Column(String(16), nullable=True)
    opening = Column(String(256), nullable=False, default="Unknown Opening")
    time_class = Column(String(16), nullable=True)
    source = Column(String(32), nullable=False, default="chesscom")
    played_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    fetched_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    coach_analysis = Column(Text, nullable=True)
    analysis_version = Column(String(64), nullable=True)

    user = relationship("User", back_populates="games")
    moves = relationship("MoveRecord", back_populates="game", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="game", cascade="all, delete-orphan")
    analysis_runs = relationship("AnalysisRun", back_populates="game", cascade="all, delete-orphan")


class MoveRecord(Base):
    __tablename__ = "move_records"
    __table_args__ = (
        UniqueConstraint("game_id", "ply", name="uq_move_records_game_ply"),
        CheckConstraint("ply >= 0", name="ck_move_records_ply_nonnegative"),
        Index("ix_move_records_game_player_class", "game_id", "is_player_move", "classification"),
    )

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True)
    ply = Column(Integer, nullable=False)
    label = Column(String(64), nullable=False)
    san = Column(String(32), nullable=False)
    side = Column(String(8), nullable=False)
    is_player_move = Column(Boolean, nullable=False)
    eval_before = Column(Integer, nullable=True)
    eval_after = Column(Integer, nullable=True)
    cp_loss = Column(Integer, nullable=True)
    classification = Column(String(24), nullable=True)
    best_move = Column(String(32), nullable=True)
    puzzle_reviewed_at = Column(DateTime(timezone=True), nullable=True)
    puzzle_correct = Column(Boolean, nullable=True)
    explanation = Column(Text, nullable=True)
    analysis_run_id = Column(Integer, ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True)

    game = relationship("Game", back_populates="moves")
    puzzle_state = relationship("PuzzleReviewState", back_populates="move", uselist=False, cascade="all, delete-orphan")


class AnalysisRun(Base):
    """Immutable provenance for a completed engine analysis pass."""

    __tablename__ = "analysis_runs"
    __table_args__ = (Index("ix_analysis_runs_game_created", "game_id", "created_at"),)

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True)
    profile_version = Column(String(64), nullable=False)
    engine_name = Column(String(64), nullable=False)
    engine_options = Column(Text, nullable=False, default="{}")
    analysis_seconds = Column(Float, nullable=False)
    status = Column(String(24), nullable=False, default="complete")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    game = relationship("Game", back_populates="analysis_runs")


class PuzzleReviewState(Base):
    """Current spaced-repetition state for one player mistake position."""

    __tablename__ = "puzzle_review_states"
    __table_args__ = (
        UniqueConstraint("user_id", "move_id", name="uq_puzzle_state_user_move"),
        Index("ix_puzzle_states_user_due", "user_id", "due_at"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    move_id = Column(Integer, ForeignKey("move_records.id", ondelete="CASCADE"), nullable=False, index=True)
    due_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    interval_days = Column(Integer, nullable=False, default=0)
    ease_factor = Column(Float, nullable=False, default=2.3)
    repetitions = Column(Integer, nullable=False, default=0)
    lapses = Column(Integer, nullable=False, default=0)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    last_result = Column(String(16), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="puzzle_states")
    move = relationship("MoveRecord", back_populates="puzzle_state")
    attempts = relationship("PuzzleAttempt", back_populates="review_state", cascade="all, delete-orphan")


class PuzzleAttempt(Base):
    """Append-only, server-scored puzzle attempt history."""

    __tablename__ = "puzzle_attempts"
    __table_args__ = (
        UniqueConstraint("review_state_id", "idempotency_key", name="uq_puzzle_attempt_idempotency"),
        Index("ix_puzzle_attempts_state_created", "review_state_id", "created_at"),
    )

    id = Column(Integer, primary_key=True)
    review_state_id = Column(Integer, ForeignKey("puzzle_review_states.id", ondelete="CASCADE"), nullable=False)
    result = Column(String(16), nullable=False)
    attempts_before_result = Column(Integer, nullable=False, default=0)
    response_seconds = Column(Integer, nullable=True)
    idempotency_key = Column(String(96), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    review_state = relationship("PuzzleReviewState", back_populates="attempts")


class SkillEvidence(Base):
    """Rebuildable evidence ledger; the profile is derived, not an LLM guess."""

    __tablename__ = "skill_evidence"
    __table_args__ = (
        UniqueConstraint("user_id", "source_type", "source_id", "skill_key", name="uq_skill_evidence_source"),
        Index("ix_skill_evidence_user_key", "user_id", "skill_key"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type = Column(String(32), nullable=False)
    source_id = Column(String(96), nullable=False)
    skill_key = Column(String(128), nullable=False)
    context = Column(String(32), nullable=False, default="organic")
    outcome = Column(String(24), nullable=False)
    weight = Column(Float, nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    metadata_json = Column(Text, nullable=False, default="{}")


class SkillState(Base):
    __tablename__ = "skill_states"
    __table_args__ = (
        UniqueConstraint("user_id", "skill_key", name="uq_skill_states_user_key"),
        Index("ix_skill_states_user_priority", "user_id", "priority"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_key = Column(String(128), nullable=False)
    mastery = Column(Float, nullable=False, default=0.5)
    confidence = Column(Float, nullable=False, default=0.0)
    evidence_count = Column(Integer, nullable=False, default=0)
    priority = Column(Float, nullable=False, default=0.0)
    last_evidence_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="skill_states")


class DailyPlan(Base):
    __tablename__ = "daily_plans"
    __table_args__ = (UniqueConstraint("user_id", "plan_date", name="uq_daily_plan_user_date"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_date = Column(String(10), nullable=False)
    timezone = Column(String(64), nullable=False)
    generated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    snapshot_json = Column(Text, nullable=False, default="{}")

    user = relationship("User", back_populates="daily_plans")
    items = relationship("DailyPlanItem", back_populates="plan", cascade="all, delete-orphan")


class DailyPlanItem(Base):
    __tablename__ = "daily_plan_items"
    __table_args__ = (UniqueConstraint("plan_id", "ordinal", name="uq_daily_plan_item_ordinal"),)

    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey("daily_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    ordinal = Column(Integer, nullable=False)
    kind = Column(String(32), nullable=False)
    reference_id = Column(String(96), nullable=True)
    title = Column(String(256), nullable=False)
    rationale = Column(Text, nullable=False)
    target_minutes = Column(Integer, nullable=False, default=10)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    plan = relationship("DailyPlan", back_populates="items")


class SyncJob(Base):
    """Durable audit/status record for sync requests (runner remains single-process)."""

    __tablename__ = "sync_jobs"
    __table_args__ = (Index("ix_sync_jobs_user_created", "user_id", "created_at"),)

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(16), nullable=False, default="queued")
    processed = Column(Integer, nullable=False, default=0)
    total = Column(Integer, nullable=False, default=0)
    new_games = Column(Integer, nullable=False, default=0)
    error = Column(Text, nullable=True)
    summary_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(256), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    user = relationship("User", backref="conversations")
    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan")


class InsightsRule(Base):
    __tablename__ = "insights_rules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="SET NULL"), nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    user = relationship("User", backref="insights_rules")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True)
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    user = relationship("User", backref="chat_messages")
    game = relationship("Game", back_populates="chat_messages")
    conversation = relationship("Conversation", back_populates="messages")
