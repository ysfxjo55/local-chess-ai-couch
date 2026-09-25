import re
import requests
from urllib.parse import quote 


class ChessComUnavailable(Exception):
    pass


def fetch_recent_games(username: str, months_back: int | None = 1) -> list[dict]:
    """Fetch games from the player's monthly archives. `months_back=1` (the
    default) is the fast incremental path for a repeat sync. Pass `None` to
    fetch every archived month — used for a user's very first sync, so they
    get their whole history instead of just whatever was played this month.

    Each item is `{"pgn": str, "time_class": str | None}` — `time_class` is
    Chess.com's own "bullet"/"blitz"/"rapid"/"daily" label, read straight
    from their API rather than inferred from the PGN's TimeControl header,
    since Chess.com's exact minute cutoffs for each label aren't public.
    """
    headers = {
        "User-Agent": "ChessAI-CoachAgent/1.0 (https://github.com/ysfxjo55/local-chess-ai-couch)"
    }
    encoded_username = quote(username)
    archive_url = f"https://api.chess.com/pub/player/{encoded_username}/games/archives"

    response = requests.get(archive_url, headers=headers, timeout=10)
    if response.status_code != 200:
        raise ChessComUnavailable(f"Could not fetch archives for {username}: HTTP {response.status_code}")

    archives = response.json().get("archives", [])
    if not archives:
        raise ChessComUnavailable(f"No game archives found for {username}")

    recent_archive_urls = archives if months_back is None else archives[-months_back:]
    all_games: list[dict] = []
    for month_url in recent_archive_urls:
        games_response = requests.get(month_url, headers=headers, timeout=10)
        if games_response.status_code != 200:
            raise ChessComUnavailable(f"Could not fetch games from {month_url}: HTTP {games_response.status_code}")

        games = games_response.json().get("games", [])
        for game in games:
            pgn = game.get("pgn")
            if pgn:
                all_games.append({"pgn": pgn, "time_class": game.get("time_class")})

    return all_games


