import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Render provides DATABASE_URL starting with "postgres://" but SQLAlchemy
# requires "postgresql://". Fall back to SQLite for local development.
_url = os.environ.get("DATABASE_URL", "sqlite:///./usmle_exam.db")
if _url.startswith("postgres://"):
    _url = _url.replace("postgres://", "postgresql+pg8000://", 1)
elif _url.startswith("postgresql://"):
    _url = _url.replace("postgresql://", "postgresql+pg8000://", 1)

_kwargs = {"check_same_thread": False} if _url.startswith("sqlite") else {}
engine = create_engine(_url, connect_args=_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
