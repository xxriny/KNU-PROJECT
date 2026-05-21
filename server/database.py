"""
NAVIGATOR-SERVER SQLite 설정.
shared.db — users, teams, subscriptions, published_snapshots, gemini_api_keys
"""

from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# SHARED_DB_PATH: 배포 시 환경변수로 절대 경로 지정
# 개발 시 기본값 = 이 파일과 같은 디렉터리의 shared.db
_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DB_PATH = os.environ.get(
    "SHARED_DB_PATH",
    os.path.join(_SERVER_DIR, "shared.db"),
)
SHARED_DB_URL = f"sqlite:///{SHARED_DB_PATH}"

engine = create_engine(SHARED_DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """앱 시작 시 테이블 생성 + 마이그레이션."""
    from models import User, Team, Subscription, PublishedSnapshot, GeminiApiKey  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _run_migrations()


def _run_migrations() -> None:
    """기존 shared.db에 나중에 추가된 컬럼을 안전하게 추가합니다."""
    from sqlalchemy import text

    with engine.begin() as conn:
        _add_col(conn, "users",         "github_id",           "TEXT")
        _add_col(conn, "users",         "github_login",        "TEXT")
        _add_col(conn, "users",         "github_oauth_token",  "TEXT")
        _add_col(conn, "users",         "github_username",     "TEXT")
        _add_col(conn, "teams",         "github_client_id",    "TEXT")
        _add_col(conn, "teams",         "github_client_secret","TEXT")
        _add_col(conn, "teams",         "github_repo",         "TEXT")
        _add_col(conn, "teams",         "github_token",        "TEXT")
        _add_col(conn, "subscriptions", "stripe_customer_id",  "TEXT")
        _add_col(conn, "subscriptions", "stripe_subscription_id", "TEXT")
        _add_col(conn, "subscriptions", "current_period_end",  "DATETIME")


def _add_col(conn, table: str, column: str, col_def: str) -> None:
    from sqlalchemy import text

    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    if not rows:
        return  # 테이블 없으면 스킵 (create_all이 아직 미실행)
    existing = {row[1] for row in rows}
    if column not in existing:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"))
