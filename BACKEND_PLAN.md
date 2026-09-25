# Backend Plan — Your Part

This is the detailed, step-by-step spec for `backend/`. I wrote it as a learning guide, not code — you implement each piece yourself. Each step lists exactly what to install, what to build, what every file is responsible for, and a concrete acceptance test (mostly `curl`) so you know when it's actually done, not just "looks done."

Source of truth for shapes you must match exactly: `API_CONTRACT.md`. Don't improvise a response field name — if you think one needs to change, edit `API_CONTRACT.md` first and tell me, since I build the frontend against it.

Two places below where I'm adding to what `WEBAPP_PLAN.md`'s "Data model" section currently says (it only lists `Game`/`MoveRecord`) — flagged inline with **[SCHEMA ADDITION]**. Update that section yourself once you've built it, since the backend schema is your call to finalize.

---



## Step 0 — Prerequisites

**Get:**

- Stockfish binary already at `/opt/homebrew/bin/stockfish` (used by `analyzer.py` today) — keep it, just stop hardcoding the path (see Step 2).
- Ollama running locally with `qwen3.5:9b` pulled (already true, per `analyzer.py`).
- `sqlite3` CLI for manually inspecting the DB while you test (`brew install sqlite` if you don't have it — macOS usually ships it already, check with `sqlite3 --version`).

**Install (run at repo root — this project stays one** `uv`**-managed environment,** `backend/` **is just a package inside it, not a separate project):**

```bash
uv add fastapi "uvicorn[standard]" sqlalchemy python-dotenv pyjwt bcrypt
```

Why these and not alternatives:

- `pyjwt` over `python-jose` — smaller, does exactly one thing (JWT encode/decode), no extra crypto backend choices to make.
- `bcrypt` directly, **not** `passlib[bcrypt]` — passlib has had unresolved compatibility breaks with recent `bcrypt` versions (it calls a `bcrypt.__about__` attribute that newer bcrypt releases removed). Calling `bcrypt.hashpw`/`bcrypt.checkpw` yourself is 4 lines and has no such trap.
- No `python-multipart`/`OAuth2PasswordBearer` — the login contract takes a JSON body (`{"username", "password"}`), not an OAuth2 form, so you don't need FastAPI's form-based security helpers. A plain Pydantic model + manual `Authorization: Bearer` header check is enough.

---



## Step 1 — Scaffold: FastAPI skeleton + SQLite models + JWT auth

**Branch:** `backend/scaffold`

### File tree to create

```
backend/
  __init__.py
  app/
    __init__.py
    main.py
    auth.py
    db.py
    models.py
    schemas.py
    routers/
      __init__.py
      auth.py
    services/
      __init__.py
.env                   # gitignored — add to .gitignore if not already covered
```



### `.env`

```
JWT_SECRET=<random 32+ byte string — generate with: python -c "import secrets; print(secrets.token_hex(32))">
JWT_EXPIRE_MINUTES=10080          # 7 days — daily-use single-user app, don't make yourself re-login constantly
CHESS_COACH_USERNAME=<pick a login username, doesn't need to match your chess.com handle>
CHESS_COACH_PASSWORD_HASH=<bcrypt hash, see below>
CHESSCOM_USERNAME=<your actual chess.com username, used by the sync service in Step 2>
STOCKFISH_PATH=/opt/homebrew/bin/stockfish
OLLAMA_MODEL=qwen3.5:9b
```

Generate the password hash once and paste the output into `.env`:

```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
```

Never store the plaintext password anywhere, only the hash.

### `backend/app/db.py`

- SQLAlchemy `create_engine("sqlite:///./app.db", connect_args={"check_same_thread": False})` (the `check_same_thread` flag is required for SQLite + FastAPI's threaded request handling — omit it and you'll get intermittent `SQLite objects created in a thread` errors under load).
- `SessionLocal = sessionmaker(...)`, a `Base = declarative_base()`, and a `get_db()` generator function (yields a session, closes it in `finally`) for use as a FastAPI dependency.



### `backend/app/models.py`

SQLAlchemy models. Two from `WEBAPP_PLAN.md`, plus one addition. **No** `User` **table, on purpose** — this is single-user (per `WEBAPP_PLAN.md`'s Auth row: credentials live in `.env`, no signup flow). `/api/auth/login` checks the submitted username/password directly against `CHESS_COACH_USERNAME`/`CHESS_COACH_PASSWORD_HASH` env vars, no table lookup. Since there's only ever one user, no other table needs a `user_id` FK either. If multi-user support ever becomes a real requirement, that's the point to add `User` and retrofit `user_id` onto `Game`/`MoveRecord`/`ChatMessage` — not before.

`Game`


| column           | type                                | notes                                                                                                                                                                                                                                                                                                                                                            |
| ---------------- | ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`             | Integer, PK                         |                                                                                                                                                                                                                                                                                                                                                                  |
| `chess_com_url`  | String, unique, indexed             | from the PGN `Link` header — this is your dedupe key for sync                                                                                                                                                                                                                                                                                                    |
| `pgn`            | Text                                | full raw PGN, kept for re-analysis later                                                                                                                                                                                                                                                                                                                         |
| `event`, `date`  | String                              | from PGN headers, for `GET /api/games/{id}`                                                                                                                                                                                                                                                                                                                      |
| `white`, `black` | String                              |                                                                                                                                                                                                                                                                                                                                                                  |
| `result`         | String                              | `"1-0"` / `"0-1"` / `"1/2-1/2"` / `"*"`                                                                                                                                                                                                                                                                                                                          |
| `player_color`   | String                              | `White`/`Black`                                                                                                                                                                                                                                                                                                                                                  |
| `opponent`       | String                              |                                                                                                                                                                                                                                                                                                                                                                  |
| `player_outcome` | String                              | `Win`/`Loss`/`Draw`/`Unknown`                                                                                                                                                                                                                                                                                                                                    |
| `opening`        | String, default `"Unknown opening"` | **[SCHEMA ADDITION]** not in `WEBAPP_PLAN.md`'s original model — needed for `win_rate_by_opening` in Step 3. Parse from PGN `ECOUrl` header (last path segment, e.g. `.../openings/Sicilian-Defense` → `"Sicilian Defense"`) or `Opening`/`ECO` header if present; fall back to the default. This resolves the open question at the bottom of `API_CONTRACT.md`. |
| `played_at`      | DateTime                            | parsed from PGN `UTCDate`+`UTCTime` (or `Date`) headers                                                                                                                                                                                                                                                                                                          |
| `fetched_at`     | DateTime, default now               |                                                                                                                                                                                                                                                                                                                                                                  |
| `coach_analysis` | Text, nullable                      | populated lazily by `POST /api/games/{id}/analysis`                                                                                                                                                                                                                                                                                                              |


`MoveRecord`


| column                      | type                     | notes                    |
| --------------------------- | ------------------------ | ------------------------ |
| `id`                        | Integer, PK              |                          |
| `game_id`                   | Integer, FK → `games.id` |                          |
| `ply`                       | Integer                  | move index, for ordering |
| `label`, `san`, `side`      | String                   |                          |
| `is_player_move`            | Boolean                  |                          |
| `eval_before`, `eval_after` | Integer                  |                          |
| `cp_loss`                   | Integer, nullable        |                          |
| `classification`            | String, nullable         | one of `Blunder          |
| `best_move`                 | String, nullable         |                          |


`ChatMessage` — **[SCHEMA ADDITION]**, not in `WEBAPP_PLAN.md`'s original model. Needed because `GET /api/games/{id}` returns `chat_history`, and `POST /api/coach/chat` needs somewhere to persist history for both per-game and global (Phase 3) chat.


| column       | type                                   | notes                                              |
| ------------ | -------------------------------------- | -------------------------------------------------- |
| `id`         | Integer, PK                            |                                                    |
| `game_id`    | Integer, FK → `games.id`, **nullable** | `null` = global chat message, not scoped to a game |
| `role`       | String                                 | `"user"` / `"assistant"`                           |
| `content`    | Text                                   |                                                    |
| `created_at` | DateTime, default now                  | orders the conversation                            |




### `backend/app/schemas.py`

Pydantic request/response models, one-to-one with every JSON shape in `API_CONTRACT.md`. For Step 1 you only need:

- `LoginRequest { username: str, password: str }`
- `TokenResponse { access_token: str, token_type: str }`
- `MeResponse { username: str }`

(Add the rest — `GameSyncItem`, `GameListItem`, `GameDetail`, `MoveOut`, `ChatMessageOut`, `StatsOverview`, `CoachChatRequest` — in Steps 2–4, right before you build the router that uses them.)

### `backend/app/auth.py`

Pure logic, no routing:

- `hash_password(password: str) -> str` — `bcrypt.hashpw`
- `verify_password(password: str, hashed: str) -> bool` — `bcrypt.checkpw`
- `create_access_token(username: str) -> str` — `jwt.encode({"sub": username, "exp": ...}, JWT_SECRET, algorithm="HS256")`, expiry = now + `JWT_EXPIRE_MINUTES`
- `get_current_user(authorization: str = Header(None)) -> str` — FastAPI dependency. Parse `Bearer <token>` out of the header (400/401 if missing or malformed), `jwt.decode(...)`, return the `sub` claim. Raise `HTTPException(401, "Not authenticated")` on any failure (missing header, bad signature, expired). This dependency gets attached to every route except `/api/auth/login`.



### `backend/app/routers/auth.py`

- `POST /api/auth/login` — body is `LoginRequest`. Compare `username` against `CHESS_COACH_USERNAME` from env, `verify_password` against `CHESS_COACH_PASSWORD_HASH`. Match → `TokenResponse`. No match → `401 {"detail": "Incorrect username or password"}` (don't leak which field was wrong).
- `GET /api/auth/me` — depends on `get_current_user`, returns `MeResponse`.



### `backend/app/main.py`

- `app = FastAPI()`
- `Base.metadata.create_all(bind=engine)` on startup (fine for SQLite at this scale — no migration tool needed yet).
- `app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])` — `5173` is Vite's default dev port; needed so my frontend dev server can call this API before we're serving it from one process.
- `app.include_router(auth_router, prefix="/api/auth")`
- Static-file mounting for the built frontend comes later (Step 5), once there's a `frontend/dist` to point at — skip it for now.



### Acceptance test for Step 1

```bash
uv run uvicorn backend.app.main:app --reload --port 8000
```

```bash
curl -X POST localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"<CHESS_COACH_USERNAME>","password":"<yourpassword>"}'
# → {"access_token":"...", "token_type":"bearer"}

TOKEN=<paste it>

curl localhost:8000/api/auth/me -H "Authorization: Bearer $TOKEN"
# → {"username":"<CHESS_COACH_USERNAME>"}

curl localhost:8000/api/auth/me
# → 401, no header
```

```bash
sqlite3 backend/app.db ".tables"
# → chat_messages  games  move_records   (empty, but tables exist)
```

When all four checks pass, open a PR from `backend/scaffold` into `main`.

---



## Step 2 — Core loop: sync → analyze → store, `games` router

**Branch:** `backend/core-loop`

### `backend/app/services/fetch_chess_com.py`

Port `fetch_game.py`'s `fetch_last_game_pgn`, renamed and extended to pull more than one game:

- `fetch_recent_games(username: str, months_back: int = 1) -> list[str]` — returns raw PGN strings from the last `months_back` monthly archives (walk `archives[-months_back:]`), not just `games[-1]` from the single latest month. `months_back=1` is a reasonable default for "run this daily"; bump it manually if you're backfilling history for the first time.
- **Fixes to fold in while porting** (from `WEBAPP_PLAN.md`'s known-bugs list):
  - `from urllib.parse import quote` — URL-encode `username` into both request URLs.
  - Add `timeout=10` to both `requests.get(...)` calls.
  - Replace the `print(...)`+`return None` error paths with raising a specific exception (e.g. `ChessComUnavailable`) that the router catches and turns into a `502` with a clear `detail` message — the frontend should be able to show "Chess.com unreachable" instead of a silent empty sync.



### `backend/app/services/stockfish_analysis.py`

Port from `analyzer.py`: `build_game_context`, `format_game_context`, `white_cp`, `format_cp`, `classify_cp_loss`, `cp_loss_for_player`, `had_winning_mate`, `analyze_game_enriched`, `build_analysis_summary`. Logic stays the same as today — the deeper accuracy fixes (true CPL, competitive/decided phases, Miss classification) are `IMPROVEMENTS.md`'s job, tracked separately, **not** part of this port. Only fold in these two mechanical fixes now:

- Use one consistent `chess.engine.Limit(time=0.1)` everywhere in `analyze_game_enriched` instead of the current mix of `0.05`/`0.1`/`0.15` — the varying depth manufactures noise in `cp_loss` that has nothing to do with the actual position.
- Replace `STOCKFISH_PATH = "/opt/homebrew/bin/stockfish"` (hardcoded) with `os.environ["STOCKFISH_PATH"]`.
- Guard `build_analysis_summary`'s turning-point pick: if every player move has `cp_loss == 0`, don't call `max()` into a fake turning point — branch to a "flawless game" summary instead.



### `backend/app/services/coach_llm.py`

Port `stream_coach_response` and `SYSTEM_PROMPT` as-is. Swap the hardcoded `model="qwen3.5:9b"` for `os.environ["OLLAMA_MODEL"]`.

### `backend/app/schemas.py` additions

`GameSyncItem`, `SyncResponse`, `GameListItem`, `GameListResponse`, `MoveOut`, `ChatMessageOut`, `GameDetail`, `AnalysisResponse` — copy field names and types directly from the JSON examples in `API_CONTRACT.md`'s Games section. Don't rename anything.

### `backend/app/routers/games.py`

- `POST /api/games/sync` (auth required):
  1. `fetch_recent_games(CHESSCOM_USERNAME)`.
  2. Parse each PGN with `chess.pgn.read_game`, pull the `Link` header as `chess_com_url`.
  3. Skip any URL already present in `games` table (the dedupe check).
  4. For each genuinely new game: open **one** Stockfish engine process (`SimpleEngine.popen_uci`, reused across all new games in this sync call — don't spawn one per game, that's the expensive part), run `analyze_game_enriched`, store `Game` + its `MoveRecord`s.
  5. Return `SyncResponse` — note the sync response only includes `id, opponent, result, player_color, played_at` per game, not the full move list.
- `GET /api/games?limit=20&offset=0` (auth required): query `games` ordered by `played_at desc`, paginate with `limit`/`offset`, and for each game compute `blunders`/`mistakes`/`inaccuracies` via a grouped count on `move_records` (`WHERE is_player_move AND classification = 'Blunder'` etc.) — one query per classification, or a single `GROUP BY classification` query post-filtered in Python, your call.
- `GET /api/games/{id}` (auth required): 404 if not found. Otherwise assemble the full `GameDetail` — game fields, `moves` ordered by `ply`, `chat_history` ordered by `created_at` filtered to `game_id = id`, `coach_analysis` (`null` if not yet generated).
- `POST /api/games/{id}/analysis` (auth required): 404 if game missing. Rebuild `build_analysis_summary` from the game's stored `MoveRecord`s + `format_game_context`, call `ollama.chat(..., stream=False)` for the full text (non-streaming per contract), save it to `Game.coach_analysis`, return `AnalysisResponse`.



### Acceptance test for Step 2

```bash
curl -X POST localhost:8000/api/games/sync -H "Authorization: Bearer $TOKEN"
# → {"new_games": N, "games": [...]}

sqlite3 backend/app.db "select id, opponent, result, player_color from games;"
# → matches what the sync response said

curl "localhost:8000/api/games?limit=20&offset=0" -H "Authorization: Bearer $TOKEN"
# → total + games[] with blunders/mistakes/inaccuracies counts

curl localhost:8000/api/games/1 -H "Authorization: Bearer $TOKEN"
# → full move list; spot-check classification values are exactly
#   Blunder | Mistake | Inaccuracy | Good | Excellent (case-sensitive)

curl -X POST localhost:8000/api/games/1/analysis -H "Authorization: Bearer $TOKEN"
# → {"coach_analysis": "markdown..."}

curl localhost:8000/api/games/1 -H "Authorization: Bearer $TOKEN"
# → coach_analysis is now populated (not regenerated — should return instantly, no Ollama call)
```

Run sync twice in a row — second run should return `"new_games": 0` and not touch existing rows (proves the dedupe-by-`chess_com_url` check works).

---



## Step 3 — `stats` router

**Branch:** `backend/stats`

### `backend/app/routers/stats.py`

`GET /api/stats/overview?range=30d` (auth required), `range ∈ 7d|30d|90d|all`:

- Compute a cutoff datetime from `range` (skip the filter entirely for `all`).
- `accuracy_trend`: group `MoveRecord`s (joined to `Game` for the date, filtered to `is_player_move` and `cp_loss is not null` and `Game.played_at >= cutoff`) by `date(Game.played_at)`, `avg(cp_loss)` and `count(distinct game_id)` per bucket, ordered chronologically.
- `win_rate_by_color`: group `Game` by `player_color`, `win_rate = count(player_outcome='Win') / count(*)`.
- `win_rate_by_opening`: group by `Game.opening` (the column you added in Step 1), same win-rate formula, only include openings with a minimum sample size if the numbers look too noisy with just 1-2 games (your call — not specified in the contract, use judgment).
- `blunder_rate_by_phase`: bucket by move number — `opening: ply <= 20` (≈10 full moves), `middlegame: 20 < ply <= 60`, `endgame: ply > 60` — then `count(classification='Blunder') / count(*)` per bucket, player moves only. This is a simple move-number heuristic, **not** the eval-based competitive/decided phase detection `IMPROVEMENTS.md` describes (Priority 1) — that's a future refinement, not required here.



### Acceptance test for Step 3

```bash
curl "localhost:8000/api/stats/overview?range=30d" -H "Authorization: Bearer $TOKEN"
```

Response shape matches the example in `API_CONTRACT.md`'s Stats section exactly — same 4 top-level keys, same nesting.

---



## Step 4 — `coach` router (streaming chat)

**Branch:** `backend/coach-chat`

### `backend/app/routers/coach.py`

`POST /api/coach/chat` (auth required), body: `CoachChatRequest { game_id: int | None, message: str }`.

1. Save the incoming user message to `chat_messages` immediately (`game_id` = request's `game_id`, which may be `null`).
2. Build the `messages` list for Ollama:
  - **Scoped to a game** (`game_id` given): system prompt + that game's stored analysis summary + prior `chat_messages` for that `game_id` + the new user message.
  - **Global** (`game_id` null): system prompt + a short aggregate-stats context (reuse the Step 3 queries) + a list of the player's worst recent moves across games + prior `chat_messages` where `game_id is null` + the new user message. No RAG/embeddings — per `WEBAPP_PLAN.md`, this is plain structured text at this game volume.
3. Return a `StreamingResponse(generator, media_type="text/event-stream")`. The generator calls `ollama.chat(..., stream=True)` and for each chunk yields:
  ```
   f"data: {json.dumps({'content': chunk})}\n\n"
  ```
   After the loop, yield:
   and only then save the fully-assembled assistant text as a second `chat_messages` row — if you save partial text on a dropped connection you'll get a corrupted turn in history.



### Acceptance test for Step 4

```bash
curl -N -X POST localhost:8000/api/coach/chat \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"game_id": 1, "message": "Why was move 14 a mistake?"}'
```

(`-N` disables curl's output buffering so you see the stream arrive incrementally, not all at once at the end.) You should see a sequence of `data: {"content": "..."}` lines followed by `data: {"done": true}`.

```bash
sqlite3 backend/app.db "select role, substr(content,1,40) from chat_messages where game_id=1;"
# → one 'user' row and one 'assistant' row, in order
```

---



## Step 5 — One-process integration (do this together, not solo)

Once both `frontend/` (mine) and all four backend steps (yours) are merged to `main`:

- I'll give you a `frontend/dist/` from `npm run build`.
- In `main.py`, mount it: `app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")`, added **after** the `/api/`* routers so API routes take priority.
- Run `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000` (the `--host 0.0.0.0` is what makes it reachable over Tailscale, not just `localhost`).
- `tailscale ip` on this Mac gives you the address to hit from your phone: `http://<tailscale-ip>:8000`.

This step needs both sides done — don't start it until Steps 1–4 are merged and I've merged the frontend scaffold.

---



## What "done" looks like, end to end

By the end of Step 4, from a cold `uv run uvicorn backend.app.main:app`, you should be able to: log in → sync your real Chess.com games → list them with blunder counts → open one and see its full move list with classifications → generate a coach writeup → chat about that game → hit `/api/stats/overview` and see real aggregate numbers → have a global chat that isn't tied to any one game. All of it verifiable with nothing but `curl`, `sqlite3`, and this file — no frontend required to prove the backend works.

curl -X POST localhost:8000/api/auth/login \

  -H "Content-Type: application/json" \

  -d '{"username":"admin","password":"

```dotenv
$2b$12$Vrdt.AzfokLXScyc4NgIEO91j5F7PFBGNlqoT8rfUrjUuWNUW.fUq
```

"}'