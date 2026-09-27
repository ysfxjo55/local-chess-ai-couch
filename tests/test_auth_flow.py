import os
import subprocess
import sys


def test_fresh_install_supports_private_account_and_learning_flow(tmp_path):
    db_path = tmp_path / "account-flow.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "APP_ENV": "development",
        "JWT_SECRET": "y" * 48,
        "ACCOUNT_CLAIM_CODE": "legacy-claim-code",
        "CORS_ORIGINS": "http://localhost:5173",
        "TRUSTED_HOSTS": "localhost,testserver",
    }
    code = r'''
from fastapi.testclient import TestClient
from backend.app.main import app

with TestClient(app) as client:
    unauthenticated = client.get("/api/games", headers={"host": "localhost"})
    assert unauthenticated.status_code == 401

    created = client.post("/api/auth/register", headers={"host": "localhost"}, json={"username": "private-player", "password": "correct-horse-battery"})
    assert created.status_code == 200, created.text
    token = created.json()["access_token"]
    headers = {"host": "localhost", "authorization": f"Bearer {token}"}

    profile = client.put("/api/auth/profile", headers=headers, json={"chesscom_username": "Private_Player", "timezone": "UTC"})
    assert profile.status_code == 200, profile.text
    assert profile.json()["chesscom_username"] == "Private_Player"

    games = client.get("/api/games", headers=headers)
    assert games.status_code == 200 and games.json()["total"] == 0
    plan = client.get("/api/learning/daily-plan", headers=headers)
    assert plan.status_code == 200 and plan.json()["items"] == []

    claimed = client.post("/api/auth/claim", headers={"host": "localhost"}, json={"chesscom_username": "Private_Player", "password": "a-replaced-secure-password", "claim_code": "legacy-claim-code"})
    assert claimed.status_code == 200, claimed.text
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    claimed_headers = {"host": "localhost", "authorization": f"Bearer {claimed.json()['access_token']}"}
    assert client.get("/api/auth/me", headers=claimed_headers).status_code == 200

    logged_out = client.post("/api/auth/logout", headers=claimed_headers)
    assert logged_out.status_code == 204
    assert client.get("/api/auth/me", headers=claimed_headers).status_code == 401
'''
    completed = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stdout + completed.stderr
