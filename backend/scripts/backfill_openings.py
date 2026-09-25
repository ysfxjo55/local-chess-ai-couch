"""
One-off maintenance script: re-derives the `opening` column for games synced
before that parsing existed. Uses each game's own already-stored `pgn` text —
no Chess.com fetch, no Stockfish re-analysis needed.

Run from repo root: uv run python -m backend.scripts.backfill_openings
"""

import io
import chess.pgn

from backend.app.db import SessionLocal
from backend.app.models import Game


def parse_opening(headers) -> str:
    """Same logic as build_game_context in stockfish_analysis.py."""
    eco_url = headers.get("ECOUrl")
    opening_name = headers.get("Opening")
    eco_code = headers.get("ECO")
    return (
        eco_url.split("/openings/")[-1].strip(".").replace("-", " ")
        if eco_url
        else opening_name
        if opening_name
        else eco_code
        if eco_code
        else "Unknown Opening"
    )


def main():
    db = SessionLocal()
    try:
        games = db.query(Game).all()
        updated = 0
        still_unknown = 0

        for game in games:
            parsed = chess.pgn.read_game(io.StringIO(game.pgn))
            if parsed is None:
                continue

            new_opening = parse_opening(parsed.headers)
            if new_opening != game.opening:
                print(f"  game {game.id} (vs {game.opponent}): "
                      f"{game.opening!r} -> {new_opening!r}")
                game.opening = new_opening
                updated += 1
            if new_opening == "Unknown Opening":
                still_unknown += 1

        db.commit()
        print(f"\nDone. {updated} of {len(games)} games updated. "
              f"{still_unknown} still have no opening header in their PGN.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
