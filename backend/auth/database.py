"""
SQLAlchemy SQLite 데이터베이스 설정.
navigator.db: users, teams, analysis_sessions, design_change_requests
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

_STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage")
os.makedirs(_STORAGE_DIR, exist_ok=True)

DB_PATH = os.path.join(_STORAGE_DIR, "navigator.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from auth.models import User, Team, AnalysisSession, DesignChangeRequest, MemoItem  # noqa: F401
    Base.metadata.create_all(bind=engine)
