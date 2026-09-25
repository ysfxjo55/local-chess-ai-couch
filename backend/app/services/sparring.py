import io
import os
import random
import threading
import uuid
from dataclasses import dataclass, field

import chess
import chess.engine
import chess.pgn
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Game, MoveRecord, InsightsRule
from .stockfish_analysis import (
    white_cp,
    cp_loss_for_player,
    classify_cp_loss,
    format_game_context,
    build_analysis_summary,
    analyze_game_enriched,
)
from .coach_llm import SYSTEM_PROMPT, generate_analysis, generate_key_takeaway

MIN_GAMES_FOR_TARGET = 3
SEED_PLY_LIMIT = 6  # up to 3 full moves each side — enough to reach a named branch
LIVE_EVAL_TIME = 0.1  # matches the post-game Stockfish pass's per-position budget


def available_levels() -> list[int]:
    if not os.path.isdir(settings.MAIA_WEIGHTS_DIR):
        return []
    levels = []
    for name in os.listdir(settings.MAIA_WEIGHTS_DIR):
        if name.startswith("maia-") and name.endswith(".pb.gz"):
            try:
                levels.append(int(name[len("maia-"):-len(".pb.gz")]))
            except ValueError:
                continue
    return sorted(levels)


def _piece_of(san: str) -> str:
    if san.startswith("O-O"):
        return "castling"
    return {"N": "knight", "B": "bishop", "R": "rook", "Q": "queen", "K": "king"}.get(
        san[0] if san else "", "pawn"
    )


def find_weak_opening_target(db: Session, user_id: int, min_games: int = MIN_GAMES_FOR_TARGET) -> dict | None:
    """Worst (opening, color) combo from the player's real Chess.com history
    — deliberately excludes sparring-sourced games so targeting doesn't chase
    its own tail (struggling against a targeted line in sparring making the
    diagnostic think it's an even bigger weakness than it organically is).
    Returns the win-rate/sample-size plus a seed move sequence lifted from
    one of the player's actual games in that combo, so the forced opening is
    grounded in a real line they've actually faced, not a generic ECO book."""
    rows = (
        db.query(
            Game.opening,
            Game.player_color,
            func.count(Game.id).label("total_games"),
            func.count(case((Game.player_outcome == "Win", Game.id))).label("wins"),
        )
        .filter(
            Game.user_id == user_id,
            Game.opening.isnot(None),
            Game.opening != "Unknown Opening",
            Game.source == "chesscom",
        )
        .group_by(Game.opening, Game.player_color)
        .having(func.count(Game.id) >= min_games)
        .all()
    )
    if not rows:
        return None

    worst = min(rows, key=lambda r: r.wins / r.total_games)

    sample_game = (
        db.query(Game)
        .filter(
            Game.user_id == user_id,
            Game.opening == worst.opening,
            Game.player_color == worst.player_color,
            Game.source == "chesscom",
        )
        .order_by(Game.played_at.desc())
        .first()
    )
    if not sample_game or not sample_game.pgn:
        return None

    parsed = chess.pgn.read_game(io.StringIO(sample_game.pgn))
    if not parsed:
        return None

    seed_moves: list[str] = []
    board = chess.Board()
    for i, move in enumerate(parsed.mainline_moves()):
        if i >= SEED_PLY_LIMIT:
            break
        seed_moves.append(board.san(move))
        board.push(move)

    return {
        "opening": worst.opening,
        "player_color": worst.player_color,
        "win_rate": round(worst.wins / worst.total_games, 2),
        "games": worst.total_games,
        "seed_moves": seed_moves,
    }


def _find_matching_rule(db: Session, user_id: int, piece: str) -> str | None:
    """Best-effort, purely local keyword match — not semantic, just "does a
    stored rule mention this piece type" — deliberately cheap (no LLM call)
    since this runs on every single move of a live game."""
    if piece in ("pawn", "castling"):
        return None
    rules = (
        db.query(InsightsRule)
        .filter(InsightsRule.user_id == user_id)
        .order_by(InsightsRule.created_at.desc())
        .all()
    )
    for r in rules:
        if piece in r.content.lower():
            return r.content
    return None


@dataclass
class SparringSession:
    id: str
    user_id: int
    board: chess.Board
    maia_engine: chess.engine.SimpleEngine
    stockfish_engine: chess.engine.SimpleEngine
    player_color: str  # "White" | "Black"
    maia_level: int
    target: dict | None
    seed_moves: list[str]
    sans: list[str] = field(default_factory=list)  # full movetext so far, both sides
    last_ply_count: int = 0  # how many plies the most recent submit_move added (1 or 2) — takeback pops exactly this many
    done: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)


_sessions: dict[str, SparringSession] = {}
_sessions_lock = threading.Lock()


def _spawn_maia(level: int) -> chess.engine.SimpleEngine:
    weights_path = os.path.join(settings.MAIA_WEIGHTS_DIR, f"maia-{level}.pb.gz")
    if not os.path.isfile(weights_path):
        raise ValueError(f"No Maia weights for level {level}")
    return chess.engine.SimpleEngine.popen_uci([settings.LC0_PATH, f"--weights={weights_path}"])


def _spawn_stockfish() -> chess.engine.SimpleEngine:
    return chess.engine.SimpleEngine.popen_uci(settings.STOCKFISH_PATH)


def start_session(db: Session, user_id: int, maia_level: int, target_weak_opening: bool) -> SparringSession:
    target = find_weak_opening_target(db, user_id) if target_weak_opening else None

    if target:
        player_color = target["player_color"]
        seed_moves = target["seed_moves"]
    else:
        player_color = random.choice(["White", "Black"])
        seed_moves = []

    board = chess.Board()
    applied_seed: list[str] = []
    for san in seed_moves:
        try:
            board.push_san(san)
            applied_seed.append(san)
        except ValueError:
            break  # a seed move failed to apply — stop replaying, play on from here

    maia_engine = _spawn_maia(maia_level)
    stockfish_engine = _spawn_stockfish()

    session = SparringSession(
        id=str(uuid.uuid4()),
        user_id=user_id,
        board=board,
        maia_engine=maia_engine,
        stockfish_engine=stockfish_engine,
        player_color=player_color,
        maia_level=maia_level,
        target=target,
        seed_moves=applied_seed,
        sans=list(applied_seed),
    )

    # If the seed sequence leaves Maia to move (or the player is Black and
    # there was no seed at all), get its opening move in immediately so the
    # response always hands control back to the player.
    _maybe_play_maia(session)

    with _sessions_lock:
        _sessions[session.id] = session
    return session


def get_session(session_id: str, user_id: int) -> SparringSession | None:
    with _sessions_lock:
        session = _sessions.get(session_id)
    if session is None or session.user_id != user_id:
        return None
    return session


def _is_maia_turn(session: SparringSession) -> bool:
    turn_color = "White" if session.board.turn == chess.WHITE else "Black"
    return turn_color != session.player_color


def _maybe_play_maia(session: SparringSession) -> str | None:
    if session.board.is_game_over() or not _is_maia_turn(session):
        return None
    # nodes=1 is how Maia is meant to be run: its rating calibration comes
    # from the raw policy ("what would a human at this level play"), and
    # letting it search makes it play stronger than its label — and slower.
    result = session.maia_engine.play(session.board, chess.engine.Limit(nodes=1))
    san = session.board.san(result.move)
    session.board.push(result.move)
    session.sans.append(san)
    return san


def submit_move(
    db: Session, session: SparringSession, from_square: str, to_square: str, promotion: str | None
) -> dict:
    if session.done:
        raise ValueError("Game already finished")
    if _is_maia_turn(session):
        raise ValueError("Not your turn")

    uci = from_square + to_square + (promotion or "")
    try:
        move = chess.Move.from_uci(uci)
    except ValueError:
        raise ValueError("Malformed move")
    if move not in session.board.legal_moves:
        raise ValueError("Illegal move")

    eval_before = white_cp(
        session.stockfish_engine.analyse(session.board, chess.engine.Limit(time=LIVE_EVAL_TIME))["score"]
    )
    player_san = session.board.san(move)
    session.board.push(move)
    session.sans.append(player_san)
    eval_after = white_cp(
        session.stockfish_engine.analyse(session.board, chess.engine.Limit(time=LIVE_EVAL_TIME))["score"]
    )

    cp_loss = cp_loss_for_player(eval_before, eval_after, session.player_color)
    classification = classify_cp_loss(cp_loss)

    warning = None
    if classification in ("Blunder", "Mistake"):
        piece = _piece_of(player_san)
        warning = {
            "classification": classification,
            "cp_loss": cp_loss,
            "matched_rule": _find_matching_rule(db, session.user_id, piece),
        }

    ply_count = 1
    maia_san = None
    if not session.board.is_game_over():
        maia_san = _maybe_play_maia(session)
        if maia_san:
            ply_count = 2

    session.last_ply_count = ply_count

    done = session.board.is_game_over()
    result_str = None
    game_id = None
    if done:
        session.done = True
        result_str = session.board.result()
        game_id = _finalize_game(db, session, result_str)

    return {
        "fen": session.board.fen(),
        "player_san": player_san,
        "maia_san": maia_san,
        "warning": warning,
        "done": done,
        "result": result_str,
        "game_id": game_id,
    }


def takeback(session: SparringSession) -> dict:
    if session.done:
        raise ValueError("Game already finished — nothing to take back")
    if session.last_ply_count == 0:
        raise ValueError("No move to take back yet")
    for _ in range(session.last_ply_count):
        if session.board.move_stack:
            session.board.pop()
            session.sans.pop()
    session.last_ply_count = 0
    return {"fen": session.board.fen(), "moves": list(session.sans)}


def abandon_session(session_id: str, user_id: int) -> bool:
    with _sessions_lock:
        session = _sessions.get(session_id)
        if session is None or session.user_id != user_id:
            return False
        del _sessions[session_id]
    _close_engines(session)
    return True


def _close_engines(session: SparringSession) -> None:
    try:
        session.maia_engine.quit()
    except Exception:
        pass
    try:
        session.stockfish_engine.quit()
    except Exception:
        pass


def _finalize_game(db: Session, session: SparringSession, result_str: str) -> int:
    """Runs on the winning move itself (synchronous, in the request that
    just finished the game) — replays the full session movetext through a
    fresh PGN game object and the real Stockfish full-analysis pass (not
    the quick live-eval used for in-game warnings), then stores it exactly
    like a synced Chess.com game: same Game/MoveRecord shape, so it shows
    up in the dashboard, feeds the puzzle queue, and counts in Insights."""
    _close_engines(session)
    with _sessions_lock:
        _sessions.pop(session.id, None)

    game = chess.pgn.Game()
    board = chess.Board()
    node = game
    for san in session.sans:
        move = board.parse_san(san)
        node = node.add_variation(move)
        board.push(move)

    if session.player_color == "White":
        game.headers["White"] = "you"
        game.headers["Black"] = f"Maia {session.maia_level}"
    else:
        game.headers["White"] = f"Maia {session.maia_level}"
        game.headers["Black"] = "you"
    game.headers["Result"] = result_str

    if result_str == "1-0":
        winner = "White"
    elif result_str == "0-1":
        winner = "Black"
    else:
        winner = "Draw"
    player_outcome = "Draw" if winner == "Draw" else ("Win" if winner == session.player_color else "Loss")

    with chess.engine.SimpleEngine.popen_uci(settings.STOCKFISH_PATH) as engine:
        move_records, _ = analyze_game_enriched(game, engine, session.player_color)

    opening_label = (
        f"Sparring: {session.target['opening']}" if session.target else "Sparring practice"
    )

    db_game = Game(
        user_id=session.user_id,
        chess_com_url=f"sparring:{session.id}",
        pgn=str(game),
        event="Sparring vs Maia",
        date=None,
        white=game.headers["White"],
        black=game.headers["Black"],
        result=result_str,
        player_color=session.player_color,
        opponent=f"Maia {session.maia_level}",
        player_outcome=player_outcome,
        opening=opening_label,
        time_class=None,
        source="sparring",
    )
    db.add(db_game)
    db.flush()

    for ply, record in enumerate(move_records):
        db.add(MoveRecord(game_id=db_game.id, ply=ply, **record))
    db.commit()

    if player_outcome == "Loss":
        try:
            ctx = {
                "event": db_game.event, "date": db_game.date, "white": db_game.white,
                "black": db_game.black, "result": db_game.result, "player": "you",
                "player_color": db_game.player_color, "opponent": db_game.opponent,
                "player_outcome": db_game.player_outcome,
            }
            game_format = format_game_context(ctx)
            analysis_summary = build_analysis_summary(ctx, move_records)
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"### Game Details\n{game_format}\n\n### Move Analysis Summary\n{analysis_summary}"},
            ]
            db_game.coach_analysis = generate_analysis(messages)
            db.add(InsightsRule(
                user_id=session.user_id, game_id=db_game.id,
                content=generate_key_takeaway(game_format, analysis_summary),
            ))
            db.commit()
        except Exception:
            db.rollback()

    return db_game.id
