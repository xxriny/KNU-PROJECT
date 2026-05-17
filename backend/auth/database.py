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


def _migrate_role_constraint(conn) -> None:
    """users.role 컬럼의 CheckConstraint를 새 역할(backend/frontend/devops)을 포함하도록 확장.

    SQLite는 ALTER COLUMN을 지원하지 않으므로:
    1. 기존 테이블을 백업으로 복사
    2. 새 스키마로 테이블 재생성
    3. 데이터 복원 후 백업 삭제
    """
    # 이미 새 constraint가 적용됐는지 확인 — sqlite_master에서 스키마 확인
    schema = conn.execute(
        text("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'")
    ).scalar() or ""
    if "devops" in schema:
        return  # 이미 마이그레이션 완료

    # 테이블 백업
    conn.execute(text("ALTER TABLE users RENAME TO users_bak"))

    # 새 테이블 생성 (CheckConstraint 제거 — SQLAlchemy가 앱 레벨에서 검증)
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

    # 데이터 복원
    conn.execute(text("INSERT INTO users SELECT * FROM users_bak"))
    conn.execute(text("DROP TABLE users_bak"))


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
        # role 컬럼 CheckConstraint 확장 (backend/frontend/devops 추가)
        _migrate_role_constraint(conn)
        # agile tasks 테이블 — team_id 컬럼
        try:
            _add_column_if_missing(conn, "agile_tasks", "team_id",    "TEXT DEFAULT ''")
        except Exception:
            pass  # 테이블이 없으면 task_coordinator.py가 따로 생성


def init_db():
    from auth.models import User, Team, AnalysisSession, DesignChangeRequest, MemoItem, AnalysisResult, PublishedSnapshot  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _run_migrations()
