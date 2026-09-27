from __future__ import annotations

from urllib.parse import quote

import requests

from ..config import settings


class ChessComUnavailable(Exception):
    pass


HEADERS = {
    "User-Agent": "ChessCoach/1.0 (+https://github.com/ysfxjo55/local-chess-ai-couch)",
    "Accept": "application/json",
}


def _get(session: requests.Session, url: str) -> dict:
    try:
        response = session.get(url, headers=HEADERS, timeout=settings.CHESSCOM_TIMEOUT_SECONDS)
        response.raise_for_status()
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ChessComUnavailable("Chess.com is temporarily unavailable. Please try syncing again later.") from exc
    if not isinstance(body, dict):
        raise ChessComUnavailable("Chess.com returned an unexpected response")
    return body


def fetch_recent_games(username: str, months_back: int | None = 1) -> list[dict]:
    """Fetch a bounded public-game import with validated upstream responses."""
    encoded_username = quote(username.strip(), safe="")
    archive_url = f"https://api.chess.com/pub/player/{encoded_username}/games/archives"
    with requests.Session() as session:
        archive_body = _get(session, archive_url)
        archives = archive_body.get("archives", [])
        if not isinstance(archives, list) or not archives:
            raise ChessComUnavailable("No public Chess.com game archives were found for this username")
        selected = archives if months_back is None else archives[-months_back:]
        all_games: list[dict] = []
        for month_url in selected:
            if not isinstance(month_url, str) or not month_url.startswith("https://api.chess.com/"):
                raise ChessComUnavailable("Chess.com returned an unsafe archive link")
            month_body = _get(session, month_url)
            games = month_body.get("games", [])
            if not isinstance(games, list):
                raise ChessComUnavailable("Chess.com returned an unexpected games archive")
            for game in games:
                if not isinstance(game, dict):
                    continue
                pgn = game.get("pgn")
                if isinstance(pgn, str) and pgn:
                    all_games.append({"pgn": pgn, "time_class": game.get("time_class")})
                    if len(all_games) >= settings.SYNC_MAX_GAMES:
                        return all_games
    return all_games
