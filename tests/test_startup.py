import os
import subprocess
import sys


def test_fresh_database_starts_without_handwritten_ddl_race(tmp_path):
    db_path = tmp_path / "fresh.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "APP_ENV": "development",
        "JWT_SECRET": "x" * 48,
    }
    code = "from fastapi.testclient import TestClient; from backend.app.main import app;\nwith TestClient(app) as client:\n r=client.get('/healthz', headers={'host':'localhost'}); assert r.status_code==200; assert client.get('/readyz', headers={'host':'localhost'}).json()['status']=='ready'"
    completed = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stdout + completed.stderr
