from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from .db import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    # The Chess.com account this app user syncs games from. Nullable because
    # existing accounts predate this field — sync is blocked with a clear
    # error until it's set (see routers/games.py).
    chesscom_username = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class Game(Base):
    __tablename__ = "games"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    # NOT globally unique: two different app users can each track the same
    # (or overlapping) Chess.com account and both need their own row for the
    # same game URL. Uniqueness is enforced per-user at the query level in
    # routers/games.py instead.
    chess_com_url = Column(String, index=True)
    pgn = Column(Text)

    event = Column(String, nullable=True)
    date = Column(String, nullable=True)
    white = Column(String)
    black = Column(String)
    result = Column(String)

    player_color = Column(String)
    opponent = Column(String)
    player_outcome = Column(String)
    opening = Column(String, default="Unknown Opening")
    # Chess.com's own classification: "bullet" | "blitz" | "rapid" | "daily".
    # Nullable because existing rows predate this field — backfilled via a
    # one-off re-fetch rather than left to the normal incremental sync,
    # which only ever looks at the current month.
    time_class = Column(String, nullable=True)
    # "chesscom" (default, backfilled for existing rows) | "sparring" — a
    # live practice game played against Maia in this app, not fetched from
    # Chess.com. Same table/shape either way so sparring games show up in
    # the dashboard, puzzles, and stats exactly like any synced game.
    source = Column(String, nullable=False, default="chesscom")

    played_at = Column(DateTime, default=datetime.now)
    fetched_at = Column(DateTime, default=datetime.now)

    coach_analysis = Column(Text, nullable=True)

    user = relationship("User", backref="games")
    moves = relationship("MoveRecord", back_populates="game", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="game", cascade="all, delete-orphan")


class Conversation(Base):
    """A single named thread in the global (not game-scoped) coach chat —
    per-game chat stays scoped by game_id alone, unchanged, since a game
    already provides a natural single-thread boundary of its own."""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)

    user = relationship("User", backref="conversations")
    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan")


class MoveRecord(Base):
    __tablename__ = "move_records"

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.id"))
    ply = Column(Integer)
    
    label = Column(String)
    san = Column(String)
    side = Column(String)
    is_player_move = Column(Boolean)
    
    eval_before = Column(Integer)
    eval_after = Column(Integer)
    cp_loss = Column(Integer, nullable=True)
    classification = Column(String, nullable=True)
    best_move = Column(String, nullable=True)
    # Blunder-puzzle review tracking (only meaningful for flagged player
    # moves). NULL puzzle_reviewed_at = still in the queue.
    puzzle_reviewed_at = Column(DateTime, nullable=True)
    puzzle_correct = Column(Boolean, nullable=True)
    # Short, move-specific "what went wrong here" writeup — generated once
    # on first puzzle view and cached, distinct from Game.coach_analysis
    # (which covers the whole game's single biggest turning point, not
    # necessarily this exact flagged move).
    explanation = Column(Text, nullable=True)

    game = relationship("Game", back_populates="moves")

class InsightsRule(Base):
    """A single, concise takeaway auto-generated after a lost game's
    analysis — the "learns you over time" memory: every future coach chat
    (per-game and global) gets the accumulated list injected as context, so
    the coach can flag when you're about to repeat a mistake it already
    knows about instead of treating every game as a first meeting."""
    __tablename__ = "insights_rules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User", backref="insights_rules")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True, index=True)
    role = Column(String)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    user = relationship("User", backref="chat_messages")
    game = relationship("Game", back_populates="chat_messages")
    conversation = relationship("Conversation", back_populates="messages")