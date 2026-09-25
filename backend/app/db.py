from sqlalchemy import Column, Integer, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


SQLALCHEMY_DATABASE_URL = "sqlite:///./app.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 15},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    # WAL mode lets reads and one write happen concurrently instead of the
    # whole file locking on every write — this is what was causing
    # "database is locked" errors under real concurrent traffic (e.g. the
    # dashboard's stats/games requests landing at the same moment as a
    # chat message insert). busy_timeout is a safety net on top: if a write
    # genuinely can't proceed instantly, retry for up to 15s before failing.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=15000")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()