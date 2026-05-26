"""SQLAlchemy database configuration.

local.db remains SQLite for per-device data. The shared auth/team database uses
PostgreSQL when Cloud SQL/Postgres env vars are present, otherwise it falls back
to the existing server/shared.db SQLite file.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

_STORAGE_DIR = os.environ.get(
    "NAVIGATOR_STORAGE_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage"),
)
os.makedirs(_STORAGE_DIR, exist_ok=True)

LOCAL_DB_PATH = os.path.join(_STORAGE_DIR, "local.db")
LOCAL_DB_URL = make_url(f"sqlite:///{LOCAL_DB_PATH}")

engine = create_engine(LOCAL_DB_URL, connect_args={"check_same_thread": False}, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

_AUTH_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_AUTH_DIR)
_NAVIGATOR_DIR = os.path.dirname(_BACKEND_DIR)

SHARED_DB_PATH = os.environ.get(
    "NAVIGATOR_SHARED_DB_PATH",
    os.path.join(_NAVIGATOR_DIR, "server", "shared.db"),
)


def _build_shared_db_url():
    explicit_url = os.environ.get("NAVIGATOR_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if explicit_url:
        return make_url(explicit_url)

    instance = os.environ.get("NAVIGATOR_CLOUDSQL_INSTANCE", "").strip()
    host = os.environ.get("NAVIGATOR_DB_HOST", "").strip()
    if instance or host:
        password = os.environ.get("NAVIGATOR_DB_PASSWORD")
        if password is None:
            raise RuntimeError("NAVIGATOR_DB_PASSWORD is required for PostgreSQL connections")

        return URL.create(
            "postgresql+psycopg",
            username=os.environ.get("NAVIGATOR_DB_USER", "navigator_user"),
            password=password,
            host=None if instance else host,
            port=int(os.environ.get("NAVIGATOR_DB_PORT", "5432")) if host else None,
            database=os.environ.get("NAVIGATOR_DB_NAME", "navigator_shared"),
            query={"host": f"/cloudsql/{instance}"} if instance else {},
        )

    return make_url(f"sqlite:///{SHARED_DB_PATH}")


SHARED_DB_URL = _build_shared_db_url()
_SHARED_CONNECT_ARGS = {"check_same_thread": False} if SHARED_DB_URL.get_backend_name() == "sqlite" else {}

shared_engine = create_engine(SHARED_DB_URL, connect_args=_SHARED_CONNECT_ARGS, pool_pre_ping=True)
SharedSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=shared_engine)


class Base(DeclarativeBase):
    """Base for local per-device tables."""


class SharedBase(DeclarativeBase):
    """Base for shared auth/team/published artifact tables."""


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


def _add_column_if_missing(conn, table: str, column: str, sqlite_def: str, postgres_def: str | None = None) -> None:
    inspector = inspect(conn)
    if not inspector.has_table(table):
        return

    existing = {row["name"] for row in inspector.get_columns(table)}
    if column not in existing:
        col_def = postgres_def if conn.dialect.name == "postgresql" and postgres_def else sqlite_def
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"))


def _migrate_sqlite_role_constraint(conn) -> None:
    schema = conn.execute(
        text("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'")
    ).scalar() or ""
    if "devops" in schema and "software_engineer" in schema and "engineer" in schema:
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
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            CHECK (role IN ('pm', 'engineer', 'software_engineer', 'backend', 'frontend', 'devops'))
        )
    """))
    conn.execute(text("INSERT INTO users SELECT * FROM users_bak"))
    conn.execute(text("DROP TABLE users_bak"))


def _ensure_role_constraints(conn, tables: tuple[str, ...]) -> None:
    if conn.dialect.name == "sqlite":
        if "users" in tables and inspect(conn).has_table("users"):
            _migrate_sqlite_role_constraint(conn)
        return
    if conn.dialect.name != "postgresql":
        return

    allowed = "'pm', 'engineer', 'software_engineer', 'backend', 'frontend', 'devops'"
    inspector = inspect(conn)
    for table in tables:
        if not inspector.has_table(table):
            continue
        columns = {row["name"] for row in inspector.get_columns(table)}
        if "role" not in columns:
            continue

        old_constraints = conn.execute(
            text(
                """
                SELECT con.conname
                FROM pg_constraint con
                JOIN pg_class rel ON rel.oid = con.conrelid
                WHERE rel.relname = :table
                  AND con.contype = 'c'
                  AND pg_get_constraintdef(con.oid) ILIKE '%role%'
                """
            ),
            {"table": table},
        ).fetchall()
        for (name,) in old_constraints:
            safe_name = name.replace('"', '""')
            conn.execute(text(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS "{safe_name}"'))

        conn.execute(
            text(
                f"ALTER TABLE {table} ADD CONSTRAINT ck_{table}_role "
                f"CHECK (role IN ({allowed}))"
            )
        )


def _run_migrations() -> None:
    with shared_engine.begin() as conn:
        _add_column_if_missing(conn, "teams", "github_client_id", "TEXT")
        _add_column_if_missing(conn, "teams", "github_client_secret", "TEXT")
        _add_column_if_missing(conn, "users", "github_username", "TEXT")
        _add_column_if_missing(conn, "users", "github_id", "TEXT")
        _add_column_if_missing(conn, "users", "github_login", "TEXT")
        _add_column_if_missing(conn, "users", "github_oauth_token", "TEXT")
        _ensure_role_constraints(conn, ("users", "team_members", "team_invites"))

    with engine.begin() as conn:
        _add_column_if_missing(conn, "agile_tasks", "team_id", "TEXT DEFAULT ''")


def init_db():
    from auth.shared_models import PublishedSnapshot, Subscription, Team, User  # noqa: F401
    from auth.models import AnalysisResult, AnalysisSession, DesignChangeRequest, MemoItem  # noqa: F401

    SharedBase.metadata.create_all(bind=shared_engine)
    Base.metadata.create_all(bind=engine)
    _run_migrations()
