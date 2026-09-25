# Chess Coach Web App — Replace Streamlit with a Real Full-Stack App

## Context

The current project (`local-chess-ai-couch`) is a Streamlit prototype: it fetches your *single most recent* Chess.com game, runs it through Stockfish, and gets an Ollama coaching writeup + chat — all in-memory, nothing persists between sessions.

Goal: turn this into a proper personal web app, "better than Chessy" (the paid iOS app we looked at earlier), for **daily use**, **fully local/free** (Stockfish + Ollama, no cloud LLM cost), with:
- A real login (single user — just you)
- Persistent history across *all* your games, not just the last one
- Insights/trends over time (accuracy, blunder patterns, opening performance) — Chessy's actual differentiators, not the underlying Stockfish+LLM pipeline
- A coach chat that can reference your whole history, not just one game
- Reachable from your phone via Tailscale, not just localhost

This plan replaces `app.py` (Streamlit) and restructures `analyzer.py`/`fetch_game.py` into a FastAPI backend + React frontend, while reusing their working logic and fixing known bugs along the way.

## Stack Decision

| Layer | Choice | Why |
|---|---|---|
| Frontend | **React + Vite + TypeScript**, Tailwind, `react-chessboard` + `chess.js` for the board, Recharts for stat charts | Gives the "real app" feel — login, dashboard, board, charts — that Streamlit can't. |
| Backend | **FastAPI** | Directly reuses your existing `analyzer.py` functions; async, typed, pairs naturally with React. |
| Database | **SQLite via SQLAlchemy** | Single user, modest game volume — zero ops (one file, no server to run). Modeled with SQLAlchemy so a later move to Postgres is a config change, not a rewrite. |
| Engine | **Stockfish** (as now, via `python-chess`) | Unchanged — it already works. |
| LLM | **Ollama, `qwen3.5:9b`** (already installed locally) | Unchanged — free, local, already your model. |
| Auth | **Single-user JWT**: credentials in `.env` (bcrypt-hashed password), login issues a JWT, no user table/signup flow | You confirmed single-user. A full accounts system would be pure overhead. |
| Reachability | **Tailscale** on this Mac + your phone | Confirmed choice — private network, no port-forwarding, no cloud hosting cost. |
| Process model | **One process**: FastAPI serves the built React static files *and* the API (`/api/*`) from the same port | So "daily use" = one command to start, one Tailscale address to hit — no juggling a separate frontend dev server. |

**Cut from your original stack list, and why:**
- **PyTorch + RecBole** — RecBole trains recommendation models (collaborative filtering). Nothing here is a recommendation problem; "habit profiling" is aggregation over Stockfish's own classifications (SQL `GROUP BY`), not a model to train.
- **Qdrant / FAISS** — no semantic search need yet. If you later want "find games similar to this blunder," add `pgvector` to a future Postgres upgrade instead of running a second database service.
- **Notion, Neptune** — no concrete role identified for either; dropped. Say the word if you had a specific use in mind.

## Architecture

```
                 ┌─────────────────────────┐
   Phone/Laptop  │   React (built static)  │
   (Tailscale) ─▶│   served by FastAPI     │
                 └───────────┬─────────────┘
                             │ /api/*
                 ┌───────────▼─────────────┐
                 │        FastAPI          │
                 │  auth / games / stats /  │
                 │  coach routers           │
                 └───┬───────────┬─────────┘
                     │           │
           ┌─────────▼──┐   ┌────▼──────────┐
           │  SQLite DB │   │ services/     │
           │  (games,   │   │ - chess.com   │
           │  moves)    │   │   fetch       │
           └────────────┘   │ - Stockfish   │
                             │   analysis    │
                             │ - Ollama coach│
                             └───────────────┘
```

## Backend Structure (new `backend/`)

```
backend/
  app/
    main.py            # FastAPI app, mounts routers + static frontend build
    auth.py            # login, JWT issue/verify, single .env-based credential
    db.py              # SQLAlchemy engine/session (SQLite file)
    models.py           # Game, MoveRecord tables
    schemas.py          # Pydantic response/request models
    routers/
      auth.py           # POST /api/auth/login
      games.py          # POST /api/games/sync, GET /api/games, GET /api/games/{id}
      stats.py          # GET /api/stats/overview
      coach.py          # POST /api/coach/chat  (streams, history-aware)
    services/
      fetch_chess_com.py     # from fetch_game.py — extended to pull ALL new games since last sync
      stockfish_analysis.py  # from analyzer.py's analyze_game_enriched / classify_cp_loss
      coach_llm.py            # from analyzer.py's SYSTEM_PROMPT / stream_coach_response
```

`main.py` (old boilerplate) and `app.py` (Streamlit) are retired; their logic doesn't get reused as-is.

### Data model
- `Game`: chess.com game id/url (unique — dedupe key for sync), pgn, white, black, result, player_color, opponent, played_at, fetched_at
- `MoveRecord`: game_id FK, ply, label, san, side, eval_before, eval_after, cp_loss, classification, best_move, is_player_move

### Fixes folded in during the port (found in earlier review, not yet applied)
- Consistent Stockfish `Limit` across every position in a diff (currently mixes `time=0.05/0.1/0.15`, which manufactures noise in cp_loss).
- `requests.get(...)` calls get a `timeout=`.
- Replace blanket `except Exception: return None` with logged, specific errors surfaced to the frontend (e.g. "Stockfish not found" vs "Chess.com unreachable").
- Guard the "turning point" pick so a flawless game (all `cp_loss == 0`) doesn't get a fake turning point.
- URL-encode the username in the Chess.com API calls.
- Sync fetches **all games in the archive newer than the last stored game**, not just the single latest one (current `fetch_last_game_pgn` only grabs `games[-1]`).

## Frontend Structure (new `frontend/`)

```
frontend/
  src/
    lib/api.ts, auth.tsx        # fetch wrapper + auth context/route guard
    pages/
      Login.tsx
      Dashboard.tsx              # game list + "Sync" button
      GameDetail.tsx             # board (react-chessboard) + move list w/ classifications + coach text + chat
      Insights.tsx                # accuracy trend, win rate by color/opening, blunder-by-phase charts
      CoachChat.tsx                # history-aware chat, not tied to one game
```

## Sync & Analysis Flow
1. User clicks **Sync** → `POST /api/games/sync`.
2. Backend fetches the player's monthly archive(s) from Chess.com, filters out game IDs already in the DB.
3. For each new game: run `stockfish_analysis` (fixed consistent-depth version), store `Game` + `MoveRecord`s.
4. Response: list of newly analyzed games. Frontend refreshes the dashboard.
5. Opening a game's detail page lazily generates the LLM coaching writeup (same pattern as today) if not cached.

## Insights (Phase 2 — the actual "beat Chessy" feature)
Aggregate SQL over `Game`/`MoveRecord`:
- Accuracy/blunder-rate trend over time
- Win rate by color, and by opening (chess.com PGNs include `ECO`/opening headers — verify on a real fetched game and fall back to "Unknown opening" if absent)
- Blunder frequency by game phase (move-number buckets: opening/middlegame/endgame)

No vector DB, no ML model — this is what actually differentiates Chessy (weekly reports, "Rating DNA") and it's pure aggregation.

## Coach Chat (Phase 3)
Same "Python computes facts, LLM only narrates" principle as the current `SYSTEM_PROMPT` — extended so the context includes aggregate stats + a short list of the player's worst recent moves across games (structured text, same pattern as `build_analysis_summary`), not raw PGN dumps. No RAG/embeddings needed at this volume of games.

## Weekly Report
Computed **on-demand** (a page you open), not push-scheduled — this Mac won't reliably be on/awake at a fixed time. Query: last 7 days of `Game` rows → same aggregation as Insights, scoped to the week → LLM narrates. (True background scheduling via `launchd` can be added later if on-demand isn't enough.)

## Build Order
1. **Scaffold**: `backend/` FastAPI skeleton, SQLite models, single-user JWT auth, `frontend/` Vite+React+TS+Tailwind skeleton with login page + route guard.
2. **Core loop parity**: sync (multi-game, fixed bugs) → analyze → store → Dashboard + GameDetail (board, move list, coach writeup, per-game chat). This alone already beats the Streamlit version (persists forever, real board UI, auth).
3. **Insights page**: aggregate stat endpoints + charts.
4. **History-aware coach chat + on-demand weekly report.**
5. *(Deferred, not built now)*: Postgres+pgvector migration if/when semantic search over games is actually wanted.

## Verification
- Backend: run `uvicorn app.main:app`, hit `/api/auth/login` then `/api/games/sync` with `curl`/httpie, confirm SQLite rows appear (`sqlite3 app.db "select * from games"`).
- Frontend: `npm run dev` against the local API, manually walk through login → sync → dashboard → game detail → chat → insights.
- End-to-end: `npm run build`, confirm FastAPI serves the built assets and the whole thing works from a single `uvicorn` process, then confirm it's reachable from your phone over Tailscale.
