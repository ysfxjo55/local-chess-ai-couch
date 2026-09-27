from __future__ import annotations

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
env_path = BACKEND_DIR / ".env"
load_dotenv(dotenv_path=env_path)


def _csv(name: str, default: str) -> list[str]:
    return [item.strip().rstrip("/") for item in os.getenv(name, default).split(",") if item.strip()]


class Settings:
    """Environment-backed configuration with production-safe defaults.

    Development can start without a configured secret by using an ephemeral
    process-only secret. Production must supply a durable secret explicitly;
    `validate_startup()` enforces that before serving requests.
    """

    APP_ENV: str = os.getenv("APP_ENV", "development").strip().lower()
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'app.db'}")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "") or secrets.token_urlsafe(48)
    JWT_SECRET_CONFIGURED: bool = bool(os.getenv("JWT_SECRET", ""))
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
    JWT_ISSUER: str = os.getenv("JWT_ISSUER", "chess-coach")
    JWT_AUDIENCE: str = os.getenv("JWT_AUDIENCE", "chess-coach-web")
    REGISTRATION_CODE: str = os.getenv("REGISTRATION_CODE", "")
    ACCOUNT_CLAIM_CODE: str = os.getenv("ACCOUNT_CLAIM_CODE", "")

    STOCKFISH_PATH: str = os.getenv("STOCKFISH_PATH", "")
    ENGINE_ANALYSIS_SECONDS: float = float(os.getenv("ENGINE_ANALYSIS_SECONDS", "0.20"))
    PUZZLE_ENGINE_SECONDS: float = float(os.getenv("PUZZLE_ENGINE_SECONDS", "0.25"))
    SYNC_MAX_GAMES: int = int(os.getenv("SYNC_MAX_GAMES", "2000"))
    CHESSCOM_TIMEOUT_SECONDS: float = float(os.getenv("CHESSCOM_TIMEOUT_SECONDS", "15"))
    LC0_PATH: str = os.getenv("LC0_PATH", "/opt/homebrew/bin/lc0")
    MAIA_WEIGHTS_DIR: str = os.getenv("MAIA_WEIGHTS_DIR", str(BACKEND_DIR / "maia_weights"))
    SPARRING_SESSION_TTL_MINUTES: int = int(os.getenv("SPARRING_SESSION_TTL_MINUTES", "30"))
    MAX_ACTIVE_SPARRING_SESSIONS: int = int(os.getenv("MAX_ACTIVE_SPARRING_SESSIONS", "1"))

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4.1")
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    COACH_MAX_MESSAGE_CHARS: int = int(os.getenv("COACH_MAX_MESSAGE_CHARS", "4000"))
    COACH_HISTORY_LIMIT: int = int(os.getenv("COACH_HISTORY_LIMIT", "24"))

    CORS_ORIGINS: list[str] = _csv(
        "CORS_ORIGINS", "http://localhost:5173,https://chess.ysfxjo.com"
    )
    TRUSTED_HOSTS: list[str] = _csv(
        "TRUSTED_HOSTS", "localhost,127.0.0.1,chess.ysfxjo.com,api.ysfxjo.com"
    )
    MAX_REQUEST_BYTES: int = int(os.getenv("MAX_REQUEST_BYTES", "65536"))

    def validate_startup(self) -> None:
        if self.APP_ENV in {"production", "prod"}:
            if not self.JWT_SECRET_CONFIGURED or len(self.JWT_SECRET) < 32:
                raise RuntimeError("JWT_SECRET must be explicitly configured with at least 32 characters in production")
            if self.REGISTRATION_CODE == "" and self.ACCOUNT_CLAIM_CODE == "":
                # Public registration is still supported when no code is set,
                # but operators should make that decision deliberately.
                pass
            if not self.DATABASE_URL.startswith("sqlite:///"):
                raise RuntimeError("This release supports a SQLite DATABASE_URL only; configure a durable SQLite volume")


settings = Settings()
