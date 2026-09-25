# AI Chess Coach — Improvement Roadmap

A living document for making this project a **standalone, trustworthy** post-game review tool (replacing Chess.com Game Review over time).

---

## Current State (What Works)

| Component | Status |
|-----------|--------|
| Chess.com PGN fetch | ✅ Working |
| Game metadata (player, opponent, color, result) | ✅ Working |
| Stockfish per-move analysis | ✅ Working (shallow) |
| Pre-computed summary → LLM coaching | ✅ Working |
| Streamlit UI + chat (`session_state`) | ✅ Working |
| Enrichment layer (CPL + Blunder/Mistake/Inaccuracy) | ⚠️ Partial |

---

## Codebase Map (Where Things Live)

| File | Function | Responsibility |
|------|----------|----------------|
| `fetch_game.py` | `fetch_last_game_pgn()` | Pull latest game PGN from Chess.com API |
| `analyzer.py` | `build_game_context()` | Player color, opponent, outcome from PGN headers |
| `analyzer.py` | `analyze_game_enriched()` | Stockfish loop — evals, CPL, classifications |
| `analyzer.py` | `build_analysis_summary()` | Structured facts sent to the LLM |
| `analyzer.py` | `run_full_analysis()` | Orchestrator — returns dict for UI |
| `analyzer.py` | `stream_coach_response()` | Ollama streaming generator |
| `app.py` | — | Streamlit UI, session state, chat |

---

## Known Issues

### 1. Checkmate / huge eval scores break classification
- Mate scores map to ~±10000 cp
- Current CPL logic compares these huge numbers → **false Blunders on winning moves**
- LLM gets confused ("simulation", move 77, generic meta-analysis)

### 2. CPL method is incomplete
- Current: compares eval **before** vs **after** the played move
- Correct: compare **best move** vs **played move** (true centipawn loss)
- See: [Lichess Accuracy](https://lichess.org/page/accuracy), Chess.com ClassificationV2 (expected points model)

### 3. No "Miss" classification
- Chess.com distinguishes **Miss** (missed opportunity) from **Mistake**
- We only have Blunder / Mistake / Inaccuracy

### 4. Turning point logic is naive
- Currently: largest CPL across all player moves
- Fails on comeback wins (worst moment may be in the middlegame, not the endgame)
- Fails when mate scores inflate CPL at the end

### 5. Shallow engine depth
- ~0.1–0.15s per position vs Chess.com deep analysis
- Classifications will drift from official reviews

### 6. LLM sometimes ignores the summary
- May hallucinate or ask for PGN in chat after a bad initial analysis
- Fix the **data layer first**; prompt tweaks are secondary

### 7. Long comeback wins are the worst case
Example: `ysfxjo2` vs `B0BdaKING` — losing early, long game, won by checkmate
- Metadata says Win, but learning value is in **when you were losing**
- Endgame noise pollutes the coach report

---

## Core Principle (Architecture)

```
Chess.com PGN → Stockfish → Python (facts + classification) → LLM (coaching language only)
```

- **Never** let the LLM calculate evaluations or discover blunders
- **Never** pass raw centipawn dumps without a structured summary
- The LLM explains, motivates, and answers chat — it does not do engine math

---

## Design Decision: Analyze ALL Moves (Even Wins)

**Do NOT stop analysis when the game is won.**

We still analyze every move because:
- Wins can contain weaknesses (comeback games)
- Clean wins are worth reviewing too
- The bug is **classification in decided positions**, not analysis length

**Fix:** split the game into **phases**, not truncate the move list.

> **Rejected approach:** stopping the loop when the game is decided. That hides endgame data and does not fix false Blunder labels. Phase split is the correct fix.

---

## Phase Model: Competitive vs Decided

| Phase | Definition | Classification |
|-------|------------|----------------|
| **Competitive** | Either side can still realistically come back | Full CPL: Blunder / Mistake / Miss / Inaccuracy / Good / Excellent |
| **Decided** | Forced mate soon, or eval beyond threshold (e.g. ±600–800 cp) | Record move + eval only; label as `Winning` / `Forced` / `Not classified` — **no Blunder** |

### How to detect "Decided"
- Engine reports mate for the winning side (e.g. `#+3`)
- Or centipawn advantage exceeds a tunable threshold (start with ±600–800 cp and tune)

### In decided phase
- Keep moves in the move list
- **Do not** run `cp_loss` → Blunder pipeline
- Summary note: *"From move X the position was winning — classifications below do not apply"*

---

## Classification Thresholds

### Current (centipawn loss, competitive phase only)

| Label | CPL range |
|-------|-----------|
| Excellent | 0 |
| Good | 1–29 |
| Inaccuracy | 30–79 |
| Mistake | 80–199 |
| Blunder | 200+ |

### Target (add Miss — tune against Chess.com)

| Label | CPL range | Notes |
|-------|-----------|-------|
| Excellent | 0 | Played best move |
| Good | 1–29 | |
| Inaccuracy | 30–79 | |
| **Miss** | 80–199 | Missed tactical opportunity; best move was check/capture/fork |
| Mistake | 80–199 | Weak move without a clear missed tactic |
| Blunder | 200+ | Serious error |

### Lichess / Chess.com (reference — different models)
- **Lichess:** uses **winning chance %** drop, not raw cp — see [accuracy page](https://lichess.org/page/accuracy)
- **Chess.com:** uses **expected points** (ClassificationV2) — not identical to raw CPL thresholds
- Goal: get close enough for learning; 85%+ agreement on flagged moves is the bar

---

## Comeback Game Summary (Win but were losing)

`build_analysis_summary` should include three sections:

### A) Worst moment while behind
- Filter moves where eval was against the player
- Find largest Mistake/Blunder / CPL in that window
- This is the main learning point

### B) Turning point / comeback
- First move that clearly swung eval back in the player's favor

### C) Endgame
- When the position became decided
- No fake blunders on converting moves to checkmate

**Example output shape (B0BdaKING):**
> You won 1-0 by checkmate, but around move ~12 you were behind by X.  
> Worst move while losing: … (Miss/Mistake).  
> Comeback began around move ~25.  
> From move ~38 the position was decided — remaining moves converted the win.

---

## Improvement Roadmap (Priority Order)

### Priority 1 — Competitive vs Decided phases
**File:** `analyzer.py` → `analyze_game_enriched`, `classify_cp_loss`

- [ ] Add `phase` field to each move record (`competitive` | `decided`)
- [ ] Only compute CPL + classification in `competitive` phase
- [ ] Still record all moves and evals

**Test:** Replay `B0BdaKING` — no Blunder on winning moves like `Qxh5`, `Ra8+` in the endgame

---

### Priority 2 — Summary for wins and comebacks
**File:** `analyzer.py` → `build_analysis_summary`

- [ ] Section: worst moment while behind
- [ ] Section: comeback move
- [ ] Section: decided endgame (informational only)
- [ ] Update `SYSTEM_PROMPT` to require comeback narrative when `player_outcome = Win` but eval was negative earlier

---

### Priority 3 — Mate score display
**File:** `analyzer.py` → `white_cp`, `format_cp`

- [ ] Display mate as human text (e.g. `Mate in 3 for White`) not `9990 cp`
- [ ] Exclude mate positions from CPL math (skip entirely in decided phase)

---

### Priority 4 — True CPL (best move vs played move)
**File:** `analyzer.py` → `analyze_game_enriched`

- [ ] Before player move: engine finds best move + eval after best line
- [ ] Play actual move: eval after played move
- [ ] CPL = difference from player's perspective
- [ ] Apply **only in competitive phase**

**Algorithm (conceptual):**
1. Analyse position before player's move → get `best_move` from `pv[0]`
2. Eval after playing `best_move` on a copy of the board → `eval_best`
3. Play player's actual move → eval → `eval_played`
4. `CPL = eval_best - eval_played` (adjusted for player color)

**References:**
- [python-chess engine docs](https://python-chess.readthedocs.io/en/latest/engine.html) — `analyse`, `pv`, `score`
- [Lichess accuracy](https://lichess.org/page/accuracy) — win% drop model (optional later)
- [Chess Stack Exchange — blunders with Stockfish](https://chess.stackexchange.com/questions/41396/is-there-a-way-to-get-blunders-mistakes-and-inaccuracies-using-stockfish)

---

### Priority 5 — Miss classification
**File:** `analyzer.py` → `classify_cp_loss` (or new classifier)

- [ ] Add **Miss** between Inaccuracy and Mistake (tactical opportunity missed)
- [ ] Heuristic: CPL in 80–199 range + best move is tactical (check, capture, fork) — tune against Chess.com

---

### Priority 6 — Deeper Stockfish
**File:** `analyzer.py` → `analyze_game_enriched`

- [ ] Use `Limit(depth=18)` (or higher) for player moves in competitive phase
- [ ] Lighter depth for opponent moves if performance is slow

---

### Priority 7 — Prompt hardening
**File:** `analyzer.py` → `SYSTEM_PROMPT`

- [ ] Must name opponent from metadata
- [ ] Must use pre-computed summary only — no recalculation
- [ ] Ban phrases: "wait", "let me re-read", "simulation", "paste your PGN"
- [ ] Win after being behind → explain comeback, don't say player "lost"

---

### Priority 8 — Validation protocol
- [ ] Pick 3 games with Chess.com Game Review
- [ ] Compare critical moves (Miss / Mistake / Blunder) manually
- [ ] Target: **85%+ agreement** on flagged moves before full trust

**Test checklist (e.g. B0BdaKING):**

| Question | Expected |
|----------|----------|
| Analysis names opponent? | Yes |
| Identifies when player was losing? | Yes |
| Explains comeback + checkmate win? | Yes |
| Fake blunders on winning endgame moves? | No |
| Chat answers without asking for PGN? | Yes |

**Manual validation template:**

| Move | Chess.com | Our app | Match? |
|------|-----------|---------|--------|
| 8 Qd1 | Miss | ? | |
| 11 Ne5 | Miss | ? | |
| 16 Nxh8 | Blunder | ? | |

---

## Future Enhancements (Later)

| Feature | Purpose |
|---------|---------|
| SQLite game history | Track patterns across games |
| Recurring weakness detection | "King safety 3x this week" |
| Accuracy % per game | Chess.com-style metric (Lichess formula) |
| Board UI in Streamlit | Show best move arrows |
| Lichess cloud analysis API | Optional; not required if local CPL is correct |
| Stronger cloud LLM for coaching | Better prose; engine still local |

---

## Trust Guide: When to Rely on the App Today

| Game type | Trust level | Recommendation |
|-----------|-------------|----------------|
| **Loss** | Medium–Good | Use coach + chat; verify critical moves |
| **Quick clean win** | Medium | General notes OK |
| **Long comeback win** | Low (until Priority 1–2 done) | Use metadata only; don't trust endgame classifications |
| **Chat after bad initial analysis** | Low | Re-analyze or ask about specific moves |

### Usage rules (while improving)
- **Lost or short game** → use the project
- **Long comeback win** → wait for phase split, or cross-check middlegame manually
- **Before changing habits from one move** → verify if Chess.com agrees
- **100% sole review source** → after Priority 1–4 + validation pass

---

## Files to Touch

| File | Changes |
|------|---------|
| `analyzer.py` | Phases, CPL, summary, mate display, prompt |
| `app.py` | Later: show phase badges, accuracy, board |
| `fetch_game.py` | Stable — no changes needed for core analysis |

---

## What NOT to Do Yet

- ❌ Stop analyzing moves when the game is won (use phase split instead)
- ❌ Switch to Lichess API before fixing local logic
- ❌ Change Qwen / Streamlit to fix data bugs
- ❌ Build CPL on top of undecided-phase noise
- ❌ Claim 100% trust before B0BdaKING-style tests pass

---

## Suggested Implementation Order (Summary)

1. **Competitive vs Decided phases** (analyze all moves; classify only competitive)
2. **Comeback summary** (weakness while behind + turnaround + decided endgame)
3. **Mate score display fix** (human-readable; exclude from CPL math)
4. **True CPL** (best move vs played move) in competitive phase only
5. **Miss classification**
6. **Deeper Stockfish** (depth 18+ on player moves)
7. **Prompt hardening**
8. **Chess.com validation** on 3+ games (85%+ agreement target)

---

## Learning Resources

| Topic | Where to read |
|-------|----------------|
| How your code calculates moves today | `analyzer.py` → `analyze_game_enriched`, `cp_loss_for_player` |
| True CPL concept | [Lichess accuracy page](https://lichess.org/page/accuracy) |
| python-chess engine API | [python-chess engine docs](https://python-chess.readthedocs.io/en/latest/engine.html) |
| Lichess source (advanced) | GitHub `lichess-org/lila` → `modules/analyse` |
| Chess.com move labels | Search: "Chess.com how are moves classified ClassificationV2" |

---

## Notes from Real Games

### mishaloqq (loss, White)
- Chess.com: Miss on Qd1 (Nb5), Ne5 (Nc7+), Blunder on Nxh8
- Coach analysis broadly aligned after enrichment — good baseline for **losses**

### B0BdaKING (win 1-0, comeback, long, checkmate)
- Exposed mate-score + false Blunder bug
- LLM meta-analysis instead of coaching
- Chat asked for PGN — primary test case for Priority 1–2

### ahmadmo563 (loss, White) — early enrichment test
- Opponent name and color context worked correctly in coach output
- Validated metadata + streaming pipeline

---

## Progress Log

| Date | Change |
|------|--------|
| 2026-07-02 | Initial roadmap created |
| 2026-07-02 | Enrichment layer added (CPL + Blunder/Mistake/Inaccuracy) — partial |
| | Priority 1 (competitive/decided phases) — not started |

---

*Last updated: 2026-07-02*
