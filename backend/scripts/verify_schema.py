import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.db import Base, engine
from backend.app.migrations import migrate_legacy_schema, verify_schema
from backend.app import models  # noqa: F401  # Registers all SQLAlchemy models before create_all.

Base.metadata.create_all(bind=engine)
migrate_legacy_schema(engine)
findings = verify_schema(engine)
if findings:
    raise SystemExit("Schema verification failed:\n- " + "\n- ".join(findings))
print("Schema verification passed")
