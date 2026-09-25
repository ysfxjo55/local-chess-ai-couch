import os
from pathlib import Path
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
env_path = BACKEND_DIR / ".env"

load_dotenv(dotenv_path=env_path)


class Settings:
    JWT_SECRET: str = os.getenv("JWT_SECRET", "supersecretkey")
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))
    STOCKFISH_PATH: str = os.getenv("STOCKFISH_PATH", "")
    LC0_PATH: str = os.getenv("LC0_PATH", "/opt/homebrew/bin/lc0")
    # Downloaded Maia weight files (maia-<elo>.pb.gz), one per rating level
    # offered in the sparring UI — see backend/maia_weights/README.
    MAIA_WEIGHTS_DIR: str = os.getenv("MAIA_WEIGHTS_DIR", str(BACKEND_DIR / "maia_weights"))
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4.1")
    CHESSCOM_USERNAME: str = os.getenv("CHESSCOM_USERNAME", "")

    # "openai" or "gemini" — which provider coach_llm.py actually calls.
    # Gemini's free tier (via Google's OpenAI-compatible endpoint) is the
    # default so a public deployment's LLM cost isn't uncapped spend on the
    # operator's own OpenAI key from strangers' usage. Switch back to
    # "openai" here (GPT-4.1 is still fully wired) if quality or free-tier
    # rate limits become a problem.
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

settings = Settings()