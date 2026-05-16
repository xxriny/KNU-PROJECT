"""
SQLAlchemy SQLite 데이터베이스 설정.
navigator.db: users, teams, analysis_sessions, design_change_requests
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

_STORAGE_DIR = os.environ.get(
    "NAVIGATOR_STORAGE_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage"),
)
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


def _add_column_if_missing(conn, table: str, column: str, col_def: str) -> None:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    existing = {row[1] for row in rows}
    if column not in existing:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"))


def _run_migrations() -> None:
    """기존 DB에 나중에 추가된 컬럼을 안전하게 추가합니다."""
    with engine.begin() as conn:
        # teams 테이블 — oauth 동적 설정 컬럼
        _add_column_if_missing(conn, "teams", "github_client_id",     "TEXT")
        _add_column_if_missing(conn, "teams", "github_client_secret", "TEXT")
        # users 테이블 — github 인증 컬럼
        _add_column_if_missing(conn, "users", "github_username",      "TEXT")
        _add_column_if_missing(conn, "users", "github_id",            "TEXT")
        _add_column_if_missing(conn, "users", "github_login",         "TEXT")
        _add_column_if_missing(conn, "users", "github_oauth_token",   "TEXT")
        # agile tasks 테이블 — team_id 컬럼
        try:
            _add_column_if_missing(conn, "agile_tasks", "team_id",    "TEXT DEFAULT ''")
        except Exception:
            pass  # 테이블이 없으면 task_coordinator.py가 따로 생성


def init_db():
    from auth.models import User, Team, AnalysisSession, DesignChangeRequest, MemoItem  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _run_migrations()
