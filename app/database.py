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

    SQLModel.metadata.create_all(engine)
