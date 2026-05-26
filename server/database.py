"""Database configuration for NAVIGATOR Server.

Uses PostgreSQL when Cloud SQL/Postgres env vars are present, otherwise keeps
the existing local SQLite shared.db fallback.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

_SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DB_PATH = os.environ.get(
    "SHARED_DB_PATH",
    os.path.join(_SERVER_DIR, "shared.db"),
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
_CONNECT_ARGS = {"check_same_thread": False} if SHARED_DB_URL.get_backend_name() == "sqlite" else {}

engine = create_engine(SHARED_DB_URL, connect_args=_CONNECT_ARGS, pool_pre_ping=True)
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
    from models import GeminiApiKey, PublishedSnapshot, Subscription, Team, User  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _run_migrations()


def _run_migrations() -> None:
    with engine.begin() as conn:
        _add_col(conn, "users", "github_id", "TEXT")
        _add_col(conn, "users", "github_login", "TEXT")
        _add_col(conn, "users", "github_oauth_token", "TEXT")
        _add_col(conn, "users", "github_username", "TEXT")
        _add_col(conn, "teams", "github_client_id", "TEXT")
        _add_col(conn, "teams", "github_client_secret", "TEXT")
        _add_col(conn, "teams", "github_repo", "TEXT")
        _add_col(conn, "teams", "github_token", "TEXT")
        _add_col(conn, "subscriptions", "stripe_customer_id", "TEXT")
        _add_col(conn, "subscriptions", "stripe_subscription_id", "TEXT")
        _add_col(conn, "subscriptions", "current_period_end", "DATETIME", "TIMESTAMP")
        _ensure_role_constraints(conn, ("users", "team_invites"))


def _add_col(conn, table: str, column: str, sqlite_def: str, postgres_def: str | None = None) -> None:
    inspector = inspect(conn)
    if not inspector.has_table(table):
        return

    existing = {row["name"] for row in inspector.get_columns(table)}
    if column not in existing:
        col_def = postgres_def if conn.dialect.name == "postgresql" and postgres_def else sqlite_def
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"))


def _ensure_role_constraints(conn, tables: tuple[str, ...]) -> None:
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
