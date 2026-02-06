from sqlmodel import SQLModel, create_engine, Session
from .config import settings
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import NullPool


if settings.database_url.startswith("sqlite"):
    engine = create_engine(
        settings.database_url,
        echo=True,
        connect_args={"check_same_thread": False, "timeout": 60},
        poolclass=NullPool,  # avoid multiple pooled connections holding write locks
    )
    # Configure SQLite pragmas to reduce locking
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
            conn.exec_driver_sql("PRAGMA busy_timeout=60000;")
    except OperationalError:
        # If the database is momentarily locked (e.g., during reloader startup), continue without failing.
        pass
else:
    engine = create_engine(
        settings.database_url,
        echo=True,
    )


def get_session():
    with Session(engine) as session:
        yield session


def init_db():
    from .models import user, expense 

    # Lightweight migration for SQLite: add users.default_currency if missing.
    try:
        if settings.database_url.startswith("sqlite"):
            with engine.connect() as conn:
                cols = conn.exec_driver_sql("PRAGMA table_info('users');").fetchall()
                col_names = {row[1] for row in cols}  # row[1] is the column name
                if "default_currency" not in col_names:
                    conn.exec_driver_sql(
                        "ALTER TABLE users ADD COLUMN default_currency TEXT NOT NULL DEFAULT 'CAD'"
                    )
    except Exception:
        # Best-effort migration; avoid blocking app startup if DB is locked.
        pass

    SQLModel.metadata.create_all(engine)
