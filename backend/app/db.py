from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import settings

def _make_engine():
    url = settings.DATABASE_URL

    # SQLite needs check_same_thread, Postgres/MySQL — нет
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url)

engine = _make_engine()
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass
