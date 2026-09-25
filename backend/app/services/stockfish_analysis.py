import chess
import chess.pgn
import chess.engine
import os
from backend.app.config import settings
from datetime import datetime
STOCKFISH_PATH = settings.STOCKFISH_PATH
MATE_CP = 10000


def build_game_context(game, username: str) -> dict:
    white = game.headers.get("White", "Unknown")
    black = game.headers.get("Black", "Unknown")
    result = game.headers.get("Result", "*")
    eco_url = game.headers.get("ECOUrl")
    opening_name = game.headers.get("Opening")
    eco_code = game.headers.get("ECO")  
    username_lower = username.lower()

    opening = (
    eco_url.split('/openings/')[-1].strip('.').replace('-', ' ') if eco_url 
    else opening_name if opening_name 
    else eco_code if eco_code 
    else "Unknown Opening"
    )


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
        "opening": opening,
        "player_outcome": player_outcome,
    }

def parse_played_at(headers) -> datetime:
    utc_date = headers.get("UTCDate")
    utc_time = headers.get("UTCTime")
    if utc_date and utc_time:
        try:
            return datetime.strptime(f"{utc_date} {utc_time}", "%Y.%m.%d %H:%M:%S")
        except ValueError:
            pass

    date = headers.get("Date")
    if date:
        try:
            return datetime.strptime(date, "%Y.%m.%d")
        except ValueError:
            pass

    return datetime.now()


def format_game_context(ctx: dict) -> str:
    return f"""GAME METADATA:
        - Event: {ctx['event']}
        - Date: {ctx['date']}
        - White: {ctx['white']}
        - Black: {ctx['black']}
        - Official Result: {ctx['result']}
        - Player you are coaching: {ctx['player']} ({ctx['player_color']})
        - Opponent: {ctx['opponent']}
        - Player outcome: {ctx['player_outcome']}
        """


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
    eval_before = white_cp(engine.analyse(board, chess.engine.Limit(time=0.1))["score"])

    for move in game.mainline_moves():
        side = "White" if board.turn == chess.WHITE else "Black"
        is_player = side == player_color

        current_eval_before = eval_before
        best_move = None

        if is_player:
            info_before = engine.analyse(board, chess.engine.Limit(time=0.1))
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
        lines.append(f"- Stronger move instead: {turning['best_move']}")

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



