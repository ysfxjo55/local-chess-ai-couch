# Chess Coach

A personal chess-learning system that imports a player's public Chess.com games, records Stockfish-backed move evidence, schedules position reviews, and produces an evidence-based daily training plan.

## What is implemented

- **Protected personal account:** password-protected registration/sign-in, short-lived JWTs with issuer/audience/version claims, logout revocation, and optional registration / legacy-account claim codes.
- **Safe game import:** bounded, timeout-controlled Chess.com retrieval; durable sync status; idempotent per-user game keys; no automatic LLM calls during sync.
- **Engine provenance:** every new import/sparring game has an immutable Stockfish analysis-run record with an analysis profile/version and per-move CPL classification.
- **Learning system:** server-scored puzzle outcomes, immutable attempts, deterministic spaced repetition, an evidence ledger, confidence-aware skill profile, and a frozen per-day training plan.
- **Coaching safeguards:** game ownership is checked before persisting chat; message size/history and generation requests are bounded; coach context is based on actual game and engine evidence.
- **Operational resilience:** SQLite foreign keys/WAL/busy timeout, clean first boot, readiness checks, strict API headers, origin/host configuration, request-size and route-rate limits, and sparring-engine expiry cleanup.

## Deployment architecture

The repository uses **one explicit deployment model**:

| Component | Deployment | URL | Responsibility |
|---|---|---|---|
| `frontend/` | Cloudflare static assets | `https://chess.ysfxjo.com` | UI and static headers |
| FastAPI backend | One Uvicorn worker on a durable host/volume | `https://api.ysfxjo.com` | API, SQLite database, Stockfish, Maia, LLM provider keys |

The frontend is static; it never contains secrets. Build it with `VITE_API_BASE_URL=https://api.ysfxjo.com`. The backend must set `CORS_ORIGINS=https://chess.ysfxjo.com` and `TRUSTED_HOSTS=api.ysfxjo.com`.

> SQLite is deliberately supported as a **single-worker** deployment. Do not run multiple Uvicorn workers or multiple replicas against the same SQLite file. Move the job runner and database to a shared queue/database before horizontally scaling.

## First production deployment

1. Copy `backend/.env.example` to a private `backend/.env` on the API host. Generate and set a 32+ character `JWT_SECRET`; configure `DATABASE_URL` to an absolute path on a durable volume; point `STOCKFISH_PATH` and `LC0_PATH` to real binaries.
2. Set `CORS_ORIGINS=https://chess.ysfxjo.com` and `TRUSTED_HOSTS=api.ysfxjo.com`. Configure `REGISTRATION_CODE` if account creation should be private.
3. Back up the SQLite file before deploying an existing installation:
   ```bash
   cp /durable/chess-coach/app.db /durable/chess-coach/app.db.backup-$(date +%F-%H%M%S)
   ```
4. On the API host, install dependencies and start one worker:
   ```bash
   uv sync --group dev
   APP_ENV=production uv run uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1
   ```
5. Run the health checks from a trusted terminal:
   ```bash
   curl -fsS https://api.ysfxjo.com/healthz
   curl -fsS https://api.ysfxjo.com/readyz
   ```
6. In `frontend/`, copy `.env.example` to `.env.production`, set the real API URL, then deploy:
   ```bash
   corepack enable
   pnpm install --frozen-lockfile
   pnpm run verify
   pnpm run deploy
   ```

## Developer verification

```bash
# backend
uv run ruff check backend tests
uv run pytest -q
uv run python backend/scripts/verify_schema.py

# frontend
cd frontend
corepack enable
pnpm install --frozen-lockfile
pnpm run verify
```

`npm run verify` runs lint, unit tests, and a production typecheck/build. Browser flows should additionally cover: account creation/sign-in, account linking, first/repeat sync, puzzle solve/give-up/reload, daily-plan completion, coach prompt with a selected board position, and sparring abandonment via navigation.

## Data and recovery

- SQLite contains private game data and password hashes; never commit `app.db`, WAL, or `.env` files.
- A sync interrupted by a server restart is marked failed and can be safely re-run; per-user Chess.com URLs make import retries idempotent.
- Legacy passwordless quick-start is disabled. Existing legacy users can be recovered only with the operator-configured `ACCOUNT_CLAIM_CODE`.
- The daily plan is a snapshot for the player’s timezone. It does not silently change after completion, which makes improvement history auditable.
