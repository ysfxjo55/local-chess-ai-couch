import sqlite3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .db import Base, engine, SQLALCHEMY_DATABASE_URL
from . import models  # noqa: F401 — registers models with Base.metadata
from .config import settings
from .routers.auth import router as auth_router
from .routers.games import router as games_router
from .routers.stats import router as stats_router
from .routers.coach import router as coach_router
from .routers.puzzles import router as puzzles_router
from .routers.sparring import router as sparring_router


def _migrate_db():
    """Add users table + user_id columns to existing tables if missing."""
    # Extract the file path from the SQLite URL
    # "sqlite:///./app.db" -> "./app.db"
    db_path = SQLALCHEMY_DATABASE_URL.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Check if users table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if cur.fetchone() is None:
        cur.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    # Add user_id to games if missing
    cur.execute("PRAGMA table_info(games)")
    games_cols = {row[1] for row in cur.fetchall()}
    if "user_id" not in games_cols:
        cur.execute("ALTER TABLE games ADD COLUMN user_id INTEGER REFERENCES users(id)")
        # Backfill existing rows with user_id=1
        cur.execute("UPDATE games SET user_id = 1 WHERE user_id IS NULL")

    # Add user_id to chat_messages if missing
    cur.execute("PRAGMA table_info(chat_messages)")
    chat_cols = {row[1] for row in cur.fetchall()}
    if "user_id" not in chat_cols:
        cur.execute("ALTER TABLE chat_messages ADD COLUMN user_id INTEGER REFERENCES users(id)")
        cur.execute("UPDATE chat_messages SET user_id = 1 WHERE user_id IS NULL")

    # Conversations table (ChatGPT-style multi-session global chat)
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'")
    if cur.fetchone() is None:
        cur.execute("""
            CREATE TABLE conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    cur.execute("PRAGMA table_info(chat_messages)")
    chat_cols = {row[1] for row in cur.fetchall()}
    if "conversation_id" not in chat_cols:
        cur.execute("ALTER TABLE chat_messages ADD COLUMN conversation_id INTEGER REFERENCES conversations(id)")

        # Fold each user's existing global (game_id IS NULL) messages into
        # one "Previous conversation" thread per user, so nothing already
        # written gets orphaned by this migration.
        cur.execute(
            "SELECT DISTINCT user_id FROM chat_messages WHERE game_id IS NULL AND user_id IS NOT NULL"
        )
        user_ids = [row[0] for row in cur.fetchall()]
        for uid in user_ids:
            cur.execute(
                "INSERT INTO conversations (user_id, title) VALUES (?, ?)",
                (uid, "Previous conversation"),
            )
            new_conv_id = cur.lastrowid
            cur.execute(
                "UPDATE chat_messages SET conversation_id = ? "
                "WHERE user_id = ? AND game_id IS NULL AND conversation_id IS NULL",
                (new_conv_id, uid),
            )

    # Per-user Chess.com username (sync used to be hardcoded to one global
    # account for every app user — this is the fix). Backfill the original
    # account (id=1, the one that predates multi-user auth entirely) with
    # whatever CHESSCOM_USERNAME was in .env, so it keeps working with zero
    # manual step; every other/newer account is prompted in the UI instead.
    cur.execute("PRAGMA table_info(users)")
    user_cols = {row[1] for row in cur.fetchall()}
    if "chesscom_username" not in user_cols:
        cur.execute("ALTER TABLE users ADD COLUMN chesscom_username TEXT")
        if settings.CHESSCOM_USERNAME:
            cur.execute(
                "UPDATE users SET chesscom_username = ? WHERE id = 1 AND chesscom_username IS NULL",
                (settings.CHESSCOM_USERNAME,),
            )

    # games.chess_com_url used to be globally UNIQUE, which meant two
    # different app users could never each hold their own copy of the same
    # Chess.com game — whichever user synced first silently "claimed" it for
    # everyone. Uniqueness is now enforced per-user in application code
    # instead (routers/games.py), so drop the old unique index in favor of a
    # plain one (SQLite can't ALTER an index's uniqueness in place).
    cur.execute("PRAGMA index_list(games)")
    for row in cur.fetchall():
        index_name, is_unique = row[1], row[2]
        if index_name == "ix_games_chess_com_url" and is_unique:
            cur.execute("DROP INDEX ix_games_chess_com_url")
            cur.execute("CREATE INDEX ix_games_chess_com_url ON games (chess_com_url)")
            break

    # Chess.com's own "bullet"/"blitz"/"rapid"/"daily" label — existing rows
    # predate this and stay NULL until backfilled (see
    # scripts intent: routers/games.py self-heals rows it re-touches, but a
    # full backfill of older rows is a one-off script, not this migration).
    cur.execute("PRAGMA table_info(games)")
    games_cols = {row[1] for row in cur.fetchall()}
    if "time_class" not in games_cols:
        cur.execute("ALTER TABLE games ADD COLUMN time_class VARCHAR")
    if "source" not in games_cols:
        cur.execute("ALTER TABLE games ADD COLUMN source VARCHAR NOT NULL DEFAULT 'chesscom'")

    # Blunder-puzzle review tracking on flagged player moves.
    cur.execute("PRAGMA table_info(move_records)")
    move_cols = {row[1] for row in cur.fetchall()}
    if "puzzle_reviewed_at" not in move_cols:
        cur.execute("ALTER TABLE move_records ADD COLUMN puzzle_reviewed_at TIMESTAMP")
    if "puzzle_correct" not in move_cols:
        cur.execute("ALTER TABLE move_records ADD COLUMN puzzle_correct BOOLEAN")
    if "explanation" not in move_cols:
        cur.execute("ALTER TABLE move_records ADD COLUMN explanation TEXT")

    # Auto-generated takeaways from lost games, injected into every future
    # coach chat as accumulated personal context.
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='insights_rules'")
    if cur.fetchone() is None:
        cur.execute("""
            CREATE TABLE insights_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                game_id INTEGER REFERENCES games(id),
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    conn.commit()
    conn.close()


_migrate_db()

app = FastAPI()

Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://chess.ysfxjo.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(games_router)
app.include_router(stats_router)
app.include_router(coach_router)
app.include_router(puzzles_router)
app.include_router(sparring_router)
