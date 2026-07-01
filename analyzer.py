import io
import chess
import chess.pgn
import chess.engine
import ollama
from fetch_game import fetch_last_game_pgn


SYSTEM_PROMPT = """
    ROLE & PERSONA:
    You are an expert, highly encouraging, and insightful English Chess Coach. Your mission is to help a beginner-level chess player improve by analyzing their post-game data. Your tone should be friendly, motivating, constructive, and educational—like a passionate grandmaster teaching a friend.

    CONTEXT & INPUT DATA SPECIFICATION:
    You will receive GAME METADATA and a chronological MOVE LIST from one specific game. This is your ONLY source of truth. Base your entire analysis exclusively on this data. Do not invent moves, reference other games, or assume positions not present in the list.

    The player you are coaching is identified in GAME METADATA (player name, color, opponent, official result, and outcome). Always coach from THEIR perspective:
    - If they played Black, negative scores favor them and positive scores favor the opponent.
    - If they played White, positive scores favor them and negative scores favor the opponent.
    - The official Result and Player outcome in metadata are authoritative for win/loss/draw questions.

    Move list format: "Move N (Side): [SAN] | Score for White: [Evaluation]"
    - Evaluation Guide:
      * Positive numbers mean White is ahead.
      * Negative numbers mean Black is ahead.
      * Centipawns scale: +100 is roughly equal to a 1-pawn advantage.
      * "#+N" or "#-N" means a forced checkmate in N moves.
      * "#+0" or "#-0" means the game ended in checkmate.

    ANALYSIS GUIDELINES & TASKS:
    1. Identify the Turning Point: Scan the scores chronologically and find the move where the evaluation swung most sharply against the coached player.
    2. Strategic Explanation: Explain why that specific move from the provided list was problematic or strong, using beginner-friendly chess concepts tied directly to the moves and scores given.
    3. Constructive Advice: State the underlying principle behind the mistake and what the player should prioritize in future games.
    4. Bulleted Takeaway: End with 2-3 short, actionable tips derived only from this game's move list and evaluations.

    OUTPUT FORMAT REQUIREMENTS:
    - Language: Write the entire analysis in natural, fluent, and highly engaging English.
    - Open the analysis by naming both players from metadata (e.g. "In your game against [Opponent] as [your color]...").
    - When referring to the other side during the review, use the opponent's username from metadata instead of generic phrases like "your opponent".
    - Always refer to the coached player by their color from metadata; never flip perspectives.
    - Ground every claim in the provided metadata and move/score data.
    - Avoid dry or robotic math terminology; translate evaluation changes into human tactical and strategic language.
    - Keep the structure scannable using bolding and clear markdown headers.
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
    return f"""GAME METADATA (use this to identify the game and who you are coaching):
- Event: {ctx['event']}
- Date: {ctx['date']}
- White: {ctx['white']}
- Black: {ctx['black']}
- Official Result: {ctx['result']}
- Player you are coaching: {ctx['player']} ({ctx['player_color']})
- Opponent: {ctx['opponent']}
- Player outcome: {ctx['player_outcome']}"""


def analyze_game_with_stockfish(game, engine):
    board = game.board()
    game_moves_data = []
    move_number = 1

    for move in game.mainline_moves():
        side = "White" if board.turn == chess.WHITE else "Black"
        human_move = board.san(move)

        board.push(move)
        info = engine.analyse(board, chess.engine.Limit(time=0.1))
        white_score = info["score"].white()

        if side == "Black":
            move_label = f"Move {move_number}... ({side})"
            move_number += 1
        else:
            move_label = f"Move {move_number} ({side})"

        game_moves_data.append(
            f"{move_label}: {human_move} | Score for White: {white_score}"
        )

    return game_moves_data


def stream_coach_response(messages):
    response = ollama.chat(
        model='qwen3.5:9b',
        messages=messages,
        think=False,
        stream=True,
        options={'temperature': 0.7},
    )

    for chunk in response:
        content = chunk['message']['content']
        yield content

    

def run_full_analysis(username):
    raw_pgn = fetch_last_game_pgn(username)
    engine = None
    if raw_pgn:
        pgn_file = io.StringIO(raw_pgn)
        first_game = chess.pgn.read_game(pgn_file)
        game_ctx = build_game_context(first_game, username)

        try:
            engine = chess.engine.SimpleEngine.popen_uci("/opt/homebrew/bin/stockfish")
            game_moves_data = analyze_game_with_stockfish(first_game, engine)
        except Exception:
            return None
        finally:
            if engine:
                engine.quit()

        full_game_summary = (
            format_game_context(game_ctx)
            + "\n\nMOVE LIST:\n"
            + "\n".join(game_moves_data)
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze this game:\n\n{full_game_summary}"},
        ]

        return {
            "game_ctx": game_ctx,
            "full_game_summary": full_game_summary,
            "move_list": game_moves_data,
            "messages": messages,
        }

