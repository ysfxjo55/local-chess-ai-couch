# CLAUDE.md

## What this project is

`local-chess-ai-couch` is being rebuilt from a Streamlit prototype into a real full-stack personal web app — the user's own "better than Chessy" chess coaching tool. Fully local/free: Stockfish for engine analysis, Ollama for the LLM, single-user, reachable from the user's phone via Tailscale.

Read these three files before doing any planning or implementation work — they are the source of truth, not this file:

- **WEBAPP_PLAN.md** — stack decision, architecture, folder structure, build order.
- **API_CONTRACT.md** — the exact frontend/backend boundary (request/response shapes). Don't change a shape here unilaterally.
- **IMPROVEMENTS.md** — backend-only roadmap for fixing the Stockfish analysis/classification logic (CPL, phases, mate scores). Not frontend work.

## Role split — read this every session

- **I (Claude) own `frontend/` only.** React + Vite + TypeScript, Tailwind, `react-chessboard`/`chess.js`, Recharts.
- **The user owns `backend/`** (FastAPI, SQLite/SQLAlchemy, Stockfish, Ollama integration) and the existing prototype files (`analyzer.py`, `app.py`, `fetch_game.py`).
- **Do not create, scaffold, or edit backend code unless explicitly told to** in that specific conversation. This includes `backend/`, `analyzer.py`, `app.py`, `fetch_game.py`, and anything in IMPROVEMENTS.md's scope. Default assumption: any task mentioned is frontend, unless the user says otherwise.
- If a frontend task needs a backend change or a new endpoint, don't build it — flag the gap and propose an addition to API_CONTRACT.md for the user to implement.

## Current state (as of 2026-08-03)

Still the Streamlit prototype (`app.py`, `analyzer.py`, `fetch_game.py`, `main.py` at repo root). No `backend/` or `frontend/` directories exist yet — the rebuild hasn't been scaffolded. WEBAPP_PLAN.md's "Build Order" section is the next-step checklist.
