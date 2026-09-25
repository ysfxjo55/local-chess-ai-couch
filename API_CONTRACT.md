# API Contract — Chess Coach Web App

Source of truth for the boundary between `frontend/` (Claude) and `backend/` (you). Neither side changes shapes here unilaterally — if an endpoint needs to change, update this file first and both sides adjust.

Base URL: `/api`. All authenticated endpoints require `Authorization: Bearer <jwt>`. Errors use FastAPI's default shape: `{"detail": "<message>"}` with the appropriate HTTP status (401 unauthenticated, 404 not found, 422 validation, 500 server error).

---

## Auth

### `POST /api/auth/login`
Request:
```json
{ "username": "string", "password": "string" }
```
Response `200`:
```json
{ "access_token": "jwt-string", "token_type": "bearer" }
```
`401` on bad credentials.

### `GET /api/auth/me`
Response `200`:
```json
{ "username": "string" }
```
Used by the frontend on load to check if a stored token is still valid. `401` if not.

---

## Games

### `POST /api/games/sync`
Triggers a fetch of new games from Chess.com since the last sync, runs Stockfish analysis on each, stores them. Synchronous (blocks until done — acceptable since it's a manual daily action, not a hot path).

Response `200`:
```json
{
  "new_games": 2,
  "games": [
    { "id": 41, "opponent": "someuser", "result": "1-0", "player_color": "White", "played_at": "2026-08-02T18:04:00Z", "time_class": "rapid" }
  ]
}
```
`time_class` is Chess.com's own label — `"bullet" | "blitz" | "rapid" | "daily"` — read directly from their API. `null` on rows synced before this field existed and not yet backfilled.

### `GET /api/games?limit=20&offset=0`
Response `200`:
```json
{
  "total": 57,
  "games": [
    {
      "id": 41,
      "opponent": "someuser",
      "result": "1-0",
      "player_color": "White",
      "player_outcome": "Win",
      "played_at": "2026-08-02T18:04:00Z",
      "time_class": "rapid",
      "blunders": 1,
      "mistakes": 0,
      "inaccuracies": 2
    }
  ]
}
```
`blunders`/`mistakes`/`inaccuracies` are counts of the player's own moves at that classification — enough for the dashboard list without fetching full move data per game.

### `GET /api/games/{id}`
Response `200`:
```json
{
  "id": 41,
  "event": "Live Chess",
  "date": "2026.08.02",
  "white": "you",
  "black": "someuser",
  "result": "1-0",
  "player": "you",
  "player_color": "White",
  "opponent": "someuser",
  "player_outcome": "Win",
  "time_class": "rapid",
  "moves": [
    {
      "label": "Move 1 (White)",
      "san": "e4",
      "side": "White",
      "is_player_move": true,
      "eval_before": 0,
      "eval_after": 20,
      "cp_loss": 0,
      "classification": "Excellent",
      "best_move": null
    }
  ],
  "coach_analysis": "markdown string, or null if not yet generated",
  "chat_history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}
```
`classification`/`side`/`player_color`/`player_outcome` are string enums exactly matching `analyzer.py`'s existing values: classification ∈ `Blunder | Mistake | Inaccuracy | Good | Excellent`, side/player_color ∈ `White | Black`, player_outcome ∈ `Win | Loss | Draw | Unknown`.

If `coach_analysis` is `null`, the frontend triggers generation (see below).

### `POST /api/games/{id}/analysis`
Lazily generates (or regenerates) the LLM coaching writeup for a game. Non-streaming — returns the finished text (frontend shows a spinner). If you'd rather stream this too, tell me and I'll switch the frontend to match — see Coach Chat below for the streaming pattern.

Response `200`:
```json
{ "coach_analysis": "markdown string" }
```

---

## Stats

### `GET /api/stats/overview?range=30d`
`range` ∈ `7d | 30d | 90d | all`.

Response `200`:
```json
{
  "accuracy_trend": [
    { "date": "2026-07-01", "avg_cp_loss": 42.5, "games": 2 }
  ],
  "win_rate_by_color": { "White": 0.61, "Black": 0.48 },
  "win_rate_by_opening": [
    { "opening": "Sicilian Defense", "games": 12, "win_rate": 0.5 }
  ],
  "blunder_rate_by_phase": {
    "opening": 0.05,
    "middlegame": 0.18,
    "endgame": 0.09
  }
}
```
Frontend treats `avg_cp_loss` as "lower is better" for the trend chart — if you end up computing a true 0-100 accuracy % instead, keep the field name `avg_cp_loss` → `accuracy` and tell me so I update the chart's scale/direction.

---

## Coach Chat

### `POST /api/coach/chat`
Request:
```json
{
  "game_id": 41,
  "message": "Why was move 14 a mistake?"
}
```
`game_id` is optional/nullable — omitted means the history-aware global chat (Phase 3), not scoped to one game.

Response: **Server-Sent Events** stream, `Content-Type: text/event-stream`. Each event:
```
data: {"content": "partial text chunk"}

```
Terminated by:
```
data: {"done": true}

```
Frontend uses `fetch` + a `ReadableStream` reader (not `EventSource`, since this is a `POST`) to consume it — standard pattern, no library needed.

---

## Resolved (was "Open Questions For You")
- Chess.com PGNs do include `ECOUrl`/`Opening`/`ECO` headers — `Game.opening` is parsed and populated at sync time with an `"Unknown Opening"` fallback. Resolved.
- SSE framing is confirmed working exactly as specified (`data: {"content": ...}\n\n` chunks, `data: {"done": true}\n\n"` terminator) — verified against the live `coach.py` implementation and consumed correctly by the frontend's `fetch` + `ReadableStream` reader. Resolved.

---

## Proposed additions (frontend-requested, not yet implemented)

Flagged during the frontend build — the frontend already ships with graceful
fallbacks for all of these (placeholder text, session-only chat, per-game-only
practice mode), so none of this blocks anything. Implement whenever convenient.

### 1. `opening: string` on `GameListItem` and `GameDetail`

`Game.opening` already exists as a populated DB column (used internally for
`win_rate_by_opening` in `/api/stats/overview`) but isn't exposed on the
per-game endpoints. Since the data already exists, this should just be a
one-line addition to each schema:

`GET /api/games` — add to each item in `games[]`:
```json
{ "opening": "Sicilian Defense" }
```

`GET /api/games/{id}` — add at the top level:
```json
{ "opening": "Sicilian Defense" }
```

Until shipped, the frontend treats `opening` as optional (`opening?: string`)
and renders `"—"` wherever it would otherwise appear (Dashboard table column,
GameDetail header).

### 2. Future: `GET /api/stats/turning-points` (cross-game Turning Point Vault)

Not needed yet — the shipped "practice this position" feature is per-game
only, computed entirely client-side from a single game's existing `moves[]`
via chess.js. Proposed for a future cross-game "Vault" page:

```
GET /api/stats/turning-points?limit=20
```
Response `200`:
```json
{
  "turning_points": [
    {
      "game_id": 41,
      "ply": 23,
      "opponent": "someuser",
      "played_at": "2026-08-02T18:04:00",
      "san": "Qd7",
      "classification": "Blunder",
      "cp_loss": 340,
      "best_move": "Nf6"
    }
  ]
}
```
Would let a future Vault page list/filter the worst moments across *all*
games without fetching every `GameDetail` individually to find them. No FEN
needed in the response — the frontend already knows how to reconstruct any
position from `game_id` + `ply` via its existing per-game reconstruction
utility, it would just fetch that one game's full `moves[]` on demand when
the user opens a specific turning point from the Vault list.

### 3. Future: `GET /api/coach/chat/history?limit=50` for global chat

No endpoint today returns `game_id: null` chat history (only
`GET /api/games/{id}` returns history, scoped to that one game). The shipped
global Coach Chat page is session-only as a result — history doesn't survive
a page refresh, even though `chat_messages` rows with `game_id = NULL` are
already being persisted correctly server-side. Proposed shape:
```json
{ "history": [{ "role": "user", "content": "..." }] }
```

### 4. Optional future: `tone` field on `CoachChatRequest`

Current frontend workaround: prepend a bracketed instruction line to the
outgoing `message` (e.g. `"[Respond in a direct, concise tone.]\n\n" +
userMessage`) before sending, and strip it back out client-side when
displaying/rehydrating history. Works correctly, but has two downsides worth
noting: (a) the prefixed string is what gets permanently persisted in
`ChatMessage.content` server-side (`db.add(chat)` happens before the LLM
call), so reloaded `chat_history` needs client-side stripping to look clean;
(b) it consumes some of the user's own message for instruction text rather
than being a clean separate parameter.

Proposed cleaner alternative for later:
```json
{ "game_id": 41, "message": "Why was move 14 a mistake?", "tone": "direct" }
```
`tone` optional, `∈ analytical | direct | patient`, default `analytical` if
omitted — backend would prepend the corresponding instruction to the system
prompt (not the stored user message), so `ChatMessage.content` stays exactly
what the user typed. Not required — the current workaround is fully
functional without it.
