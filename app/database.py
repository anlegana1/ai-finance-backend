from sqlmodel import SQLModel, create_engine, Session
from .config import settings


if settings.database_url.startswith("sqlite"):
    engine = create_engine(
        settings.database_url,
        echo=True,
        connect_args={"check_same_thread": False}, 
    )
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
