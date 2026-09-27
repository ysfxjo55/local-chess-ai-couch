from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db import Base
from backend.app.models import Game, MoveRecord, User, utcnow
from backend.app.services.spaced_repetition import record_review


def make_session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_solved_review_is_idempotent_and_scheduled():
    db = make_session()
    user = User(username="player", password_hash="hash")
    db.add(user)
    db.flush()
    game = Game(
        user_id=user.id, chess_com_url="https://example.test/game/1", pgn="*", event="test", date="2026.01.01",
        white="player", black="opponent", result="*", player_color="White", opponent="opponent", player_outcome="Unknown",
    )
    db.add(game)
    db.flush()
    move = MoveRecord(game_id=game.id, ply=12, label="Move 7 (White)", san="Nf3", side="White", is_player_move=True, eval_before=20, eval_after=-50, cp_loss=70, classification="Mistake", best_move="Bf4")
    db.add(move)
    db.flush()

    state, attempt, created = record_review(db, user_id=user.id, move=move, outcome="solved", attempts_before_result=0, response_seconds=9, idempotency_key="attempt-one")
    assert created is True
    assert attempt.result == "solved"
    assert state.interval_days == 1
    assert state.due_at > utcnow() + timedelta(hours=23)
    assert move.puzzle_correct is True

    same_state, same_attempt, created_again = record_review(db, user_id=user.id, move=move, outcome="solved", attempts_before_result=0, response_seconds=9, idempotency_key="attempt-one")
    assert created_again is False
    assert same_state.id == state.id
    assert same_attempt.id == attempt.id


def test_give_up_resets_interval_and_tracks_lapse():
    db = make_session()
    user = User(username="player-two", password_hash="hash")
    game = Game(user=user, chess_com_url="https://example.test/game/2", pgn="*", event="test", date="2026.01.01", white="player", black="opponent", result="*", player_color="White", opponent="opponent", player_outcome="Unknown")
    move = MoveRecord(game=game, ply=20, label="Move 11 (White)", san="Qe2", side="White", is_player_move=True, eval_before=30, eval_after=-250, cp_loss=280, classification="Blunder", best_move="Qc2")
    db.add_all([user, game, move])
    db.flush()

    state, _, _ = record_review(db, user_id=user.id, move=move, outcome="gave_up", attempts_before_result=2, response_seconds=21, idempotency_key="gave-up")
    assert state.lapses == 1
    assert state.repetitions == 0
    assert state.interval_days == 1
    assert move.puzzle_correct is False
