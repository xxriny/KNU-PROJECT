"""
SQLAlchemy SQLite 데이터베이스 설정.

local.db  — 개인 데이터: users, teams, sessions, results, memos, agile_tasks
shared.db — 공유 데이터: published_snapshots (향후 배포 예정)
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

_STORAGE_DIR = os.environ.get(
    "NAVIGATOR_STORAGE_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage"),
)
os.makedirs(_STORAGE_DIR, exist_ok=True)

# ── 로컬 DB (개인 산출물) ───────────────────────────────────
LOCAL_DB_PATH = os.path.join(_STORAGE_DIR, "local.db")
LOCAL_DB_URL = f"sqlite:///{LOCAL_DB_PATH}"

engine = create_engine(LOCAL_DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ── 공유 DB (팀 스냅샷, 향후 배포) ─────────────────────────
SHARED_DB_PATH = os.path.join(_STORAGE_DIR, "shared.db")
SHARED_DB_URL = f"sqlite:///{SHARED_DB_PATH}"

shared_engine = create_engine(SHARED_DB_URL, connect_args={"check_same_thread": False})
SharedSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=shared_engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_shared_db():
    db = SharedSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _add_column_if_missing(conn, table: str, column: str, col_def: str) -> None:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    existing = {row[1] for row in rows}
    if column not in existing:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"))


def _migrate_role_constraint(conn) -> None:
    """users.role CheckConstraint를 새 역할 포함하도록 확장."""
    schema = conn.execute(
        text("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'")
    ).scalar() or ""
    if "devops" in schema:
        return

    conn.execute(text("ALTER TABLE users RENAME TO users_bak"))
    conn.execute(text("""
        CREATE TABLE users (
            id TEXT NOT NULL PRIMARY KEY,
            team_id TEXT REFERENCES teams(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL DEFAULT 'engineer',
            github_username TEXT,
            github_id TEXT UNIQUE,
            github_login TEXT,
            github_oauth_token TEXT,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """))
    conn.execute(text("INSERT INTO users SELECT * FROM users_bak"))
    conn.execute(text("DROP TABLE users_bak"))


def _run_migrations() -> None:
    """기존 local.db에 나중에 추가된 컬럼을 안전하게 추가합니다."""
    with engine.begin() as conn:
        _add_column_if_missing(conn, "teams", "github_client_id",     "TEXT")
        _add_column_if_missing(conn, "teams", "github_client_secret", "TEXT")
        _add_column_if_missing(conn, "users", "github_username",      "TEXT")
        _add_column_if_missing(conn, "users", "github_id",            "TEXT")
        _add_column_if_missing(conn, "users", "github_login",         "TEXT")
        _add_column_if_missing(conn, "users", "github_oauth_token",   "TEXT")
        _migrate_role_constraint(conn)
        try:
            _add_column_if_missing(conn, "agile_tasks", "team_id", "TEXT DEFAULT ''")
        except Exception:
            pass


def init_db():
    from auth.models import (  # noqa: F401
        User, Team, AnalysisSession, DesignChangeRequest,
        MemoItem, AnalysisResult,
    )
    from auth.shared_models import PublishedSnapshot  # noqa: F401

    # 로컬 테이블 생성 (PublishedSnapshot 제외)
    local_tables = [
        t for name, t in Base.metadata.tables.items()
        if name != "published_snapshots"
    ]
    Base.metadata.create_all(bind=engine, tables=local_tables)

    # 공유 테이블 생성
    shared_tables = [Base.metadata.tables["published_snapshots"]]
    Base.metadata.create_all(bind=shared_engine, tables=shared_tables)

    _run_migrations()
