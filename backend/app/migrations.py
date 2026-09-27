from __future__ import annotations

import logging
from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .config import settings

logger = logging.getLogger(__name__)


def _table_names(conn) -> set[str]:  # noqa: ANN001
    if not settings.DATABASE_URL.startswith("sqlite"):
        return set()
    return {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}


def _columns(conn, table: str) -> set[str]:  # noqa: ANN001
    return {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}


def _add_columns(conn, table: str, statements: Iterable[tuple[str, str]]) -> None:  # noqa: ANN001
    if table not in _table_names(conn):
        return
    columns = _columns(conn, table)
    for name, ddl in statements:
        if name not in columns:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
            columns.add(name)


def migrate_legacy_schema(engine: Engine) -> None:
    """Bring pre-release SQLite databases forward without import-time DDL.

    New installations come from SQLAlchemy metadata. This migration only adds
    additive columns/tables and safe indexes to pre-existing local databases.
    It never drops player data or invents migration state.
    """
    if not settings.DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as conn:
        tables = _table_names(conn)
        if "users" in tables:
            _add_columns(
                conn,
                "users",
                [
                    ("chesscom_username", "chesscom_username VARCHAR(64)"),
                    ("chesscom_username_norm", "chesscom_username_norm VARCHAR(64)"),
                    ("token_version", "token_version INTEGER NOT NULL DEFAULT 1"),
                    ("timezone", "timezone VARCHAR(64) NOT NULL DEFAULT 'UTC'"),
                    ("updated_at", "updated_at DATETIME"),
                ],
            )
            conn.execute(text("UPDATE users SET token_version = 1 WHERE token_version IS NULL"))
            conn.execute(text("UPDATE users SET timezone = 'UTC' WHERE timezone IS NULL OR timezone = ''"))
            conn.execute(text("UPDATE users SET chesscom_username_norm = lower(trim(chesscom_username)) WHERE chesscom_username IS NOT NULL AND chesscom_username_norm IS NULL"))

        if "games" in tables:
            _add_columns(
                conn,
                "games",
                [
                    ("user_id", "user_id INTEGER"),
                    ("time_class", "time_class VARCHAR(16)"),
                    ("source", "source VARCHAR(32) NOT NULL DEFAULT 'chesscom'"),
                    ("analysis_version", "analysis_version VARCHAR(64)"),
                ],
            )
            # Only a pre-existing game without an owner needs a legacy
            # placeholder. A fresh database has an empty games table and must
            # never receive an artificial account during normal startup.
            orphaned_games = conn.execute(text("SELECT COUNT(*) FROM games WHERE user_id IS NULL")).scalar() or 0
            if orphaned_games:
                legacy_user = conn.execute(text("SELECT id FROM users ORDER BY id LIMIT 1")).scalar()
                if legacy_user is None:
                    conn.execute(
                        text("INSERT INTO users (username, password_hash, token_version, timezone, created_at, updated_at) VALUES (:u, :p, 1, 'UTC', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"),
                        {"u": "legacy-owner", "p": "!claim-this-account-with-the-operator"},
                    )
                    legacy_user = conn.execute(text("SELECT id FROM users WHERE username = 'legacy-owner'")).scalar_one()
                conn.execute(text("UPDATE games SET user_id = :id WHERE user_id IS NULL"), {"id": legacy_user})

        if "move_records" in tables:
            _add_columns(
                conn,
                "move_records",
                [
                    ("puzzle_reviewed_at", "puzzle_reviewed_at DATETIME"),
                    ("puzzle_correct", "puzzle_correct BOOLEAN"),
                    ("explanation", "explanation TEXT"),
                    ("analysis_run_id", "analysis_run_id INTEGER"),
                ],
            )

        if "chat_messages" in tables:
            _add_columns(
                conn,
                "chat_messages",
                [
                    ("user_id", "user_id INTEGER"),
                    ("conversation_id", "conversation_id INTEGER"),
                ],
            )
            legacy_user = conn.execute(text("SELECT id FROM users ORDER BY id LIMIT 1")).scalar()
            if legacy_user is not None:
                conn.execute(text("UPDATE chat_messages SET user_id = :id WHERE user_id IS NULL"), {"id": legacy_user})

        # These indexes make real read paths bounded without risking a data
        # destructive rebuild of pre-existing SQLite tables.
        for sql in (
            "CREATE INDEX IF NOT EXISTS ix_games_user_played_at_safe ON games (user_id, played_at)",
            "CREATE INDEX IF NOT EXISTS ix_move_records_game_player_class_safe ON move_records (game_id, is_player_move, classification)",
            "CREATE INDEX IF NOT EXISTS ix_puzzle_states_user_due_safe ON puzzle_review_states (user_id, due_at)",
            "CREATE INDEX IF NOT EXISTS ix_skill_evidence_user_key_safe ON skill_evidence (user_id, skill_key)",
        ):
            try:
                conn.execute(text(sql))
            except Exception:  # Older partially-created databases are repaired by metadata on next startup.
                logger.warning("Could not create optional legacy index", exc_info=True)

        # Data correctness invariants that can be installed without altering
        # the table layout. If historical duplicates exist, retain data and
        # log the condition rather than silently deleting a player's games.
        duplicates = conn.execute(
            text(
                "SELECT COUNT(*) FROM (SELECT user_id, chess_com_url FROM games "
                "WHERE chess_com_url IS NOT NULL GROUP BY user_id, chess_com_url HAVING COUNT(*) > 1)"
            )
        ).scalar() or 0
        if not duplicates:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_games_user_chess_url_safe ON games (user_id, chess_com_url) WHERE chess_com_url IS NOT NULL"))
        else:
            logger.warning("Skipped unique game index because %s historical duplicate game keys need review", duplicates)


def verify_schema(engine: Engine) -> list[str]:
    """Return human-readable schema health findings for readiness/CI checks."""
    findings: list[str] = []
    with engine.connect() as conn:
        tables = _table_names(conn)
        required = {"users", "games", "move_records", "puzzle_review_states", "skill_states", "daily_plans", "sync_jobs"}
        missing = required - tables
        if missing:
            findings.append(f"Missing required tables: {', '.join(sorted(missing))}")
        if "games" in tables and "user_id" not in _columns(conn, "games"):
            findings.append("games.user_id is missing")
        if "users" in tables and "token_version" not in _columns(conn, "users"):
            findings.append("users.token_version is missing")
    return findings
