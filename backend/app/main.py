from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import models  # noqa: F401 - registers mapped tables before create_all
from .config import settings
from .db import Base, engine
from .migrations import migrate_legacy_schema, verify_schema
from .middleware import SecurityHeadersMiddleware
from .routers.auth import router as auth_router
from .routers.coach import router as coach_router
from .routers.games import router as games_router
from .routers.games import recover_interrupted_sync_jobs
from .routers.learning import router as learning_router
from .routers.puzzles import router as puzzles_router
from .routers.sparring import router as sparring_router
from .routers.stats import router as stats_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_startup()
    # Table creation must happen before any additive legacy migration. The old
    # import-time migration previously queried/altered `games` on a fresh DB,
    # preventing first boot entirely.
    Base.metadata.create_all(bind=engine)
    migrate_legacy_schema(engine)
    recover_interrupted_sync_jobs()
    findings = verify_schema(engine)
    if findings:
        raise RuntimeError("Database schema check failed: " + "; ".join(findings))
    logger.info("Chess Coach startup checks passed")
    yield
    engine.dispose()


app = FastAPI(
    title="Chess Coach API",
    version="1.0.0",
    docs_url="/docs" if settings.APP_ENV not in {"production", "prod"} else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.TRUSTED_HOSTS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "ok"}


@app.get("/readyz", include_in_schema=False)
def readyz():
    findings = verify_schema(engine)
    if findings:
        return {"status": "degraded", "findings": findings}
    return {"status": "ready"}


app.include_router(auth_router)
app.include_router(games_router)
app.include_router(stats_router)
app.include_router(coach_router)
app.include_router(puzzles_router)
app.include_router(sparring_router)
app.include_router(learning_router)
