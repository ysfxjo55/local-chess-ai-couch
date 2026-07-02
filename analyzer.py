import io
import chess
import chess.pgn
import chess.engine
import ollama
from fetch_game import fetch_last_game_pgn

STOCKFISH_PATH = "/opt/homebrew/bin/stockfish"
MATE_CP = 10000

SYSTEM_PROMPT = """
ROLE & PERSONA:
You are an expert, highly encouraging, and insightful English Chess Coach. Your mission is to help a beginner-level chess player improve by analyzing their post-game data. Your tone should be friendly, motivating, constructive, and educational—like a passionate grandmaster teaching a friend.

CONTEXT & INPUT DATA SPECIFICATION:
You will receive GAME METADATA and a PRE-COMPUTED ANALYSIS SUMMARY. The summary was calculated by Stockfish using Lichess-style move classifications. It is authoritative and complete. Do NOT recalculate evaluations, do NOT second-guess the numbers, and do NOT show your internal reasoning (never write phrases like "wait", "let me re-read", or "correction").

The player you are coaching is identified in GAME METADATA (player name, color, opponent, official result, and outcome). Always coach from THEIR perspective.

The PRE-COMPUTED ANALYSIS SUMMARY includes:
- Turning point: the single player move with the largest evaluation drop
- Classifications: Blunder (200+ cp lost), Mistake (80-199), Inaccuracy (30-79), Good, Excellent
- Best move suggestions from the engine when the player deviated

ANALYSIS GUIDELINES & TASKS:
1. Open by naming both players from metadata (e.g. "In your game against [Opponent] as [your color]...").
2. Focus your review on the turning point from the summary. Explain why that move was problematic in beginner-friendly chess terms.
3. Briefly mention other significant mistakes from the summary if relevant.
4. Give constructive advice: the underlying principle and what to focus on next time.
5. End with 2-3 short, actionable bullet tips derived from this game.

OUTPUT FORMAT REQUIREMENTS:
- Language: natural, fluent, engaging English.
- Use the opponent's username from metadata, not generic "your opponent".
- Ground every claim in the provided summary and metadata.
- Translate evaluation changes into human tactical and strategic language—no raw number crunching in the output.
- Keep the structure scannable with markdown headers and bullets.
"""


def build_game_context(game, username: str) -> dict:
    white = game.headers.get("White", "Unknown")
    black = game.headers.get("Black", "Unknown")
    result = game.headers.get("Result", "*")
    username_lower = username.lower()

    if username_lower == white.lower():
        player_color = "White"
        opponent = black
    elif username_lower == black.lower():
        player_color = "Black"
        opponent = white
    else:
        player_color = "Unknown"
        opponent = "Unknown"

    if result == "1-0":
        winner = "White"
    elif result == "0-1":
        winner = "Black"
    elif result == "1/2-1/2":
        winner = "Draw"
    else:
        winner = "Unknown"

    if player_color == winner:
        player_outcome = "Win"
    elif winner == "Draw":
        player_outcome = "Draw"
    elif player_color == "Unknown":
        player_outcome = "Unknown"
    else:
        player_outcome = "Loss"

    return {
        "event": game.headers.get("Event", "Unknown"),
        "date": game.headers.get("Date", "Unknown"),
        "white": white,
        "black": black,
        "result": result,
        "player": username,
        "player_color": player_color,
        "opponent": opponent,
        "winner": winner,
        "player_outcome": player_outcome,
    }


def format_game_context(ctx: dict) -> str:
    return f"""GAME METADATA:
- Event: {ctx['event']}
- Date: {ctx['date']}
- White: {ctx['white']}
- Black: {ctx['black']}
- Official Result: {ctx['result']}
- Player you are coaching: {ctx['player']} ({ctx['player_color']})
- Opponent: {ctx['opponent']}
- Player outcome: {ctx['player_outcome']}"""


def white_cp(score) -> int:
    return score.white().score(mate_score=MATE_CP) or 0


def format_cp(cp: int) -> str:
    if cp >= MATE_CP - 100:
        return "Checkmate for White"
    if cp <= -(MATE_CP - 100):
        return "Checkmate for Black"
    return f"{cp:+d} cp"


def classify_cp_loss(cp_loss: int) -> str:
    if cp_loss >= 200:
        return "Blunder"
    if cp_loss >= 80:
        return "Mistake"
    if cp_loss >= 30:
        return "Inaccuracy"
    if cp_loss > 0:
        return "Good"
    return "Excellent"


def cp_loss_for_player(eval_before: int, eval_after: int, player_color: str) -> int:
    if player_color == "White":
        raw = eval_before - eval_after
    elif player_color == "Black":
        raw = eval_after - eval_before
    else:
        return 0

    if raw <= 0:
        return 0

    # Mate scores compress to ~±10000; cap loss for classification when mate was on the board
    if abs(eval_before) >= MATE_CP - 500 or abs(eval_after) >= MATE_CP - 500:
        return max(200, min(raw, 500))

    return raw


def had_winning_mate(eval_cp: int, player_color: str) -> bool:
    if player_color == "White":
        return eval_cp >= MATE_CP - 500
    if player_color == "Black":
        return eval_cp <= -(MATE_CP - 500)
    return False


def analyze_game_enriched(game, engine, player_color: str) -> tuple[list[dict], list[str]]:
    board = game.board()
    move_records: list[dict] = []
    move_lines: list[str] = []
    move_number = 1
    eval_before = white_cp(engine.analyse(board, chess.engine.Limit(time=0.05))["score"])

    for move in game.mainline_moves():
        side = "White" if board.turn == chess.WHITE else "Black"
        is_player = side == player_color

        current_eval_before = eval_before
        best_move = None

        if is_player:
            info_before = engine.analyse(board, chess.engine.Limit(time=0.15))
            current_eval_before = white_cp(info_before["score"])
            pv = info_before.get("pv")
            if pv:
                best_move = board.san(pv[0])

        san = board.san(move)
        board.push(move)

        eval_after = white_cp(engine.analyse(board, chess.engine.Limit(time=0.1))["score"])

        if side == "Black":
            label = f"Move {move_number}... ({side})"
            move_number += 1
        else:
            label = f"Move {move_number} ({side})"

        cp_loss = None
        classification = None
        if is_player:
            cp_loss = cp_loss_for_player(current_eval_before, eval_after, player_color)
            classification = classify_cp_loss(cp_loss)

        record = {
            "label": label,
            "san": san,
            "side": side,
            "is_player_move": is_player,
            "eval_before": current_eval_before,
            "eval_after": eval_after,
            "cp_loss": cp_loss,
            "classification": classification,
            "best_move": best_move,
        }
        move_records.append(record)

        line = f"{label}: {san} | Score for White: {format_cp(eval_after)}"
        if is_player and classification:
            line += f" | Player move: {classification}"
        move_lines.append(line)

        eval_before = eval_after

    return move_records, move_lines


def build_analysis_summary(game_ctx: dict, move_records: list[dict]) -> str:
    player_moves = [r for r in move_records if r["is_player_move"] and r["cp_loss"] is not None]

    if not player_moves:
        return "PRE-COMPUTED ANALYSIS SUMMARY:\n- No player moves identified for detailed classification."

    turning = max(player_moves, key=lambda r: r["cp_loss"])
    mistakes = [
        r for r in player_moves
        if r["classification"] in ("Blunder", "Mistake", "Inaccuracy")
    ]
    mistakes.sort(key=lambda r: r["cp_loss"], reverse=True)

    lines = [
        "PRE-COMPUTED ANALYSIS SUMMARY (authoritative — do not recalculate):",
        "",
        "TURNING POINT (largest evaluation drop by the coached player):",
        f"- Move: {turning['label']} {turning['san']}",
        f"- Classification: {turning['classification']}",
        f"- Evaluation before: {format_cp(turning['eval_before'])} → after: {format_cp(turning['eval_after'])}",
        f"- Centipawns lost on this move: {turning['cp_loss']}",
    ]
    if had_winning_mate(turning["eval_before"], game_ctx["player_color"]):
        lines.append("- Note: Player had a forced winning checkmate before this move.")
    if turning["best_move"] and turning["best_move"] != turning["san"]:
        lines.append(f"- Engine best move instead: {turning['best_move']}")

    if mistakes:
        lines.extend(["", "OTHER SIGNIFICANT PLAYER MISTAKES (newest classification system):"])
        for r in mistakes:
            entry = (
                f"- {r['label']} {r['san']}: {r['classification']} "
                f"(lost {r['cp_loss']} cp, eval {format_cp(r['eval_before'])} → {format_cp(r['eval_after'])})"
            )
            if r["best_move"] and r["best_move"] != r["san"]:
                entry += f" | Best: {r['best_move']}"
            lines.append(entry)

    excellent = [r for r in player_moves if r["classification"] == "Excellent"]
    if excellent:
        lines.extend(["", f"STRONG PLAYER MOVES: {len(excellent)} excellent move(s) with no evaluation loss."])

    return "\n".join(lines)


def stream_coach_response(messages):
    response = ollama.chat(
        model="qwen3.5:9b",
        messages=messages,
        think=False,
        stream=True,
        options={"temperature": 0.4},
    )

    for chunk in response:
        content = chunk["message"]["content"]
        if content:
            yield content


def run_full_analysis(username):
    raw_pgn = fetch_last_game_pgn(username)
    engine = None
    if not raw_pgn:
        return None

    pgn_file = io.StringIO(raw_pgn)
    first_game = chess.pgn.read_game(pgn_file)
    game_ctx = build_game_context(first_game, username)

    try:
        engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
        move_records, move_lines = analyze_game_enriched(
            first_game, engine, game_ctx["player_color"]
        )
    except Exception:
        return None
    finally:
        if engine:
            engine.quit()

    analysis_summary = build_analysis_summary(game_ctx, move_records)
    full_game_summary = (
        format_game_context(game_ctx)
        + "\n\n"
        + analysis_summary
        + "\n\nMOVE LIST (reference only):\n"
        + "\n".join(move_lines)
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Analyze this game:\n\n{full_game_summary}"},
    ]

    return {
        "game_ctx": game_ctx,
        "full_game_summary": full_game_summary,
        "analysis_summary": analysis_summary,
        "move_records": move_records,
        "move_list": move_lines,
        "messages": messages,
    }
