import io
import chess.pgn
import chess.engine
import ollama
from fetch_game import fetch_last_game_pgn

engine = chess.engine.SimpleEngine.popen_uci("/opt/homebrew/bin/stockfish")

username = input("Enter your Chess.com username: ")
print("Fetching your last live game...")
raw_pgn = fetch_last_game_pgn(username)

if raw_pgn:
    pgn_file = io.StringIO(raw_pgn)
    first_game = chess.pgn.read_game(pgn_file)

    print("Event Name:", first_game.headers.get("Event"))

    board = first_game.board()
    game_moves_data = []

    print("Analyzing game moves with Stockfish...")
    for move in first_game.mainline_moves():
        human_move = board.san(move)

        board.push(move)
        info = engine.analyse(board, chess.engine.Limit(time=0.1))
        white_score = info["score"].white()

        game_moves_data.append(f"Move: {human_move} | Score for White: {white_score}")

    engine.quit()

    full_game_summary = "\n".join(game_moves_data)

    SYSTEM_PROMPT = """
    ROLE & PERSONA:
    You are an expert, highly encouraging, and insightful English Chess Coach. Your mission is to help a beginner-level chess player improve by analyzing their post-game data. Your tone should be friendly, motivating, constructive, and educational—like a passionate grandmaster teaching a friend.

    CONTEXT & INPUT DATA SPECIFICATION:
    You will receive the ONLY source of truth: a chronological list of moves from the player's actual game, each paired with a Stockfish evaluation score. Base your entire analysis exclusively on this data. Do not invent moves, reference other games, or assume positions not present in the list.
    - Format: "Move: [SAN_Move] | Score for White: [Evaluation]"
    - Evaluation Guide:
      * Positive numbers mean White is ahead.
      * Negative numbers mean Black is ahead.
      * Centipawns scale: +100 is roughly equal to a 1-pawn advantage.
      * "#+N" or "#-N" means a forced checkmate in N moves.
      * "#+0" or "#-0" means the game ended in checkmate.

    ANALYSIS GUIDELINES & TASKS:
    1. Identify the Turning Point: Scan the scores chronologically and find the move where the evaluation swung most sharply against one side.
    2. Strategic Explanation: Do not just list the numbers. Explain why that specific move from the provided list was problematic, using beginner-friendly chess concepts tied directly to the moves and scores given.
    3. Constructive Advice: State the underlying principle behind the mistake and what the player should prioritize in future games.
    4. Bulleted Takeaway: End with 2-3 short, actionable tips derived only from this game's move list and evaluations.

    OUTPUT FORMAT REQUIREMENTS:
    - Language: Write the entire analysis in natural, fluent, and highly engaging English.
    - Ground every claim in the provided move/score data; never cite moves or patterns not found in the input.
    - Avoid dry or robotic math terminology; translate evaluation changes into human tactical and strategic language.
    - Keep the structure scannable using bolding and clear markdown headers.
    """

    messages = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {'role': 'user', 'content': f"Here is the game output for analysis:\n{full_game_summary}"},
    ]

    response = ollama.chat(
        model='qwen3.5:9b',
        messages=messages,
        think=False,
        stream=True,
        options={'temperature': 0.7},
    )

    print("\n--- AI Coach Analysis ---")
    initial_analysis = ""
    for chunk in response:
        content = chunk['message']['content']
        print(content, end='', flush=True)
        initial_analysis += content
    print("\n")

    messages.append({'role': 'assistant', 'content': initial_analysis})

    print("=" * 50)
    print("💬 AI COACH IS READY FOR DISCUSSION!")
    print("You can now ask questions about the game. Type 'exit' to quit.")
    print("=" * 50)

    while True:
        user_msg = input("\nYou: ")

        if user_msg.strip().lower() == 'exit':
            print("\nCoach: Good game, and keep practicing! See you next time! ♟️🚀")
            break

        if not user_msg.strip():
            continue

        messages.append({'role': 'user', 'content': user_msg})

        response = ollama.chat(
            model='qwen3.5:9b',
            messages=messages,
            think=False,
            stream=True,
            options={'temperature': 0.7},
        )

        print("\nCoach: ", end="")
        coach_response = ""
        for chunk in response:
            content = chunk['message']['content']
            print(content, end='', flush=True)
            coach_response += content
        print()

        messages.append({'role': 'assistant', 'content': coach_response})

else:
    print("Failed to fetch the game. Please check the username or network connection.")
    engine.quit()
