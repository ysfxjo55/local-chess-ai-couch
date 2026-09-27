from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db import Base
from backend.app.models import Game, MoveRecord, User
from backend.app.services.skill_model import record_engine_evidence


def test_engine_evidence_is_rebuildable_and_deduplicated():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    user = User(username="learner", password_hash="hash")
    game = Game(user=user, chess_com_url="https://example.test/game/3", pgn="*", event="test", date="2026.01.01", white="learner", black="opponent", result="0-1", player_color="White", opponent="opponent", player_outcome="Loss", opening="Sicilian Defense")
    move = MoveRecord(game=game, ply=28, label="Move 15 (White)", san="f4", side="White", is_player_move=True, eval_before=20, eval_after=-210, cp_loss=230, classification="Blunder", best_move="Be3")
    db.add_all([user, game, move])
    db.flush()

    assert record_engine_evidence(db, user.id, game, [move]) == 2  # phase + opening
    assert record_engine_evidence(db, user.id, game, [move]) == 0
    states = {state.skill_key: state for state in user.skill_states}
    assert states["phase:middlegame"].mastery < 0.5
    assert states["phase:middlegame"].priority > 0
