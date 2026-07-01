import requests
import io
import chess.pgn

def fetch_last_game_pgn(username):
    headers = {
        "User-Agent": "ChessAI-CoachAgent/1.0 (ysfxjo2005@gmail.com)"
    }
    
    archive_url = f"https://api.chess.com/pub/player/{username}/games/archives"
    response = requests.get(archive_url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error fetching archives for user {username}. Code: {response.status_code}")
        return None
        
    archives = response.json().get("archives", [])
    if not archives:
        print("No game archives found for this player.")
        return None
        
    latest_month_url = archives[-1]
    
    games_response = requests.get(latest_month_url, headers=headers)
    if games_response.status_code != 200:
        print(f"Error fetching games from archive. Code: {games_response.status_code}")
        return None
        
    games = games_response.json().get("games", [])
    if not games:
        print("No games played in the current month.")
        return None
        
    last_game = games[-1]
    pgn_text = last_game.get("pgn")
    
    return pgn_text