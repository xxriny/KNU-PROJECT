"""
Main Agent 태스크 조정기.
PM 승인이 필요한 작업을 큐에 적재하고 상태를 관리한다.
SQLite(auth DB)의 agile_tasks 테이블을 사용한다.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)
from typing import Optional

from sqlalchemy import Column, String, Text, DateTime, create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os

_STORAGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "storage",
)
_DB_PATH = os.path.join(_STORAGE_DIR, "local.db")
_DB_URL = f"sqlite:///{_DB_PATH}"

_engine = create_engine(_DB_URL, connect_args={"check_same_thread": False})
_Session = sessionmaker(bind=_engine)


class _Base(DeclarativeBase):
    pass


class AgileTask(_Base):
    __tablename__ = "agile_tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_type = Column(String(64), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    status = Column(String(32), default="pending")  # pending | approved | rejected | completed | failed
    area = Column(String(32), default="")           # backend | frontend | fullstack | devops
    assignee = Column(String(255), default="")
    payload = Column(Text, default="{}")  # JSON
    result = Column(Text, default="")
    created_by = Column(String(36), default="")
    reviewed_by = Column(String(36), default="")
    team_id = Column(String(36), default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def init_tasks_db():
    _Base.metadata.create_all(bind=_engine)
    with _engine.connect() as conn:
        for col_def in ["area TEXT DEFAULT ''", "assignee TEXT DEFAULT ''", "team_id TEXT DEFAULT ''"]:
            try:
                conn.execute(text(f"ALTER TABLE agile_tasks ADD COLUMN {col_def}"))
                conn.commit()
            except Exception:
                pass


# ── CRUD ────────────────────────────────────────────────────

def create_task(
    task_type: str,
    title: str,
    description: str = "",
    payload: dict | None = None,
    created_by: str = "",
    area: str = "",
    assignee: str = "",
    team_id: str = "",
) -> dict:
    import json
    init_tasks_db()
    with _Session() as session:
        task = AgileTask(
            id=str(uuid.uuid4()),
            task_type=task_type,
            title=title,
            description=description,
            area=area,
            assignee=assignee,
            payload=json.dumps(payload or {}),
            created_by=created_by,
            team_id=team_id,
        )
        session.add(task)
        session.commit()
        return _task_to_dict(task)


def list_tasks(status: str | None = None, team_id: str | None = None) -> list[dict]:
    init_tasks_db()
    with _Session() as session:
        q = session.query(AgileTask)
        if status:
            q = q.filter(AgileTask.status == status)
        if team_id:
            q = q.filter(AgileTask.team_id == team_id)
        tasks = q.order_by(AgileTask.created_at.desc()).all()
        return [_task_to_dict(t) for t in tasks]


def get_task(task_id: str) -> dict | None:
    init_tasks_db()
    with _Session() as session:
        task = session.query(AgileTask).filter(AgileTask.id == task_id).first()
        return _task_to_dict(task) if task else None


def delete_task(task_id: str) -> bool:
    init_tasks_db()
    with _Session() as session:
        task = session.query(AgileTask).filter(AgileTask.id == task_id).first()
        if not task:
            return False
        session.delete(task)
        session.commit()
        return True


def update_task_status(
    task_id: str,
    status: str,
    reviewed_by: str = "",
    result: str = "",
) -> dict | None:
    init_tasks_db()
    with _Session() as session:
        task = session.query(AgileTask).filter(AgileTask.id == task_id).first()
        if not task:
            return None
        task.status = status
        task.updated_at = _now()
        if reviewed_by:
            task.reviewed_by = reviewed_by
        if result:
            task.result = result
        session.commit()
        return _task_to_dict(task)


def _task_to_dict(task: AgileTask) -> dict:
    import json
    return {
        "id": task.id,
        "task_type": task.task_type,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "area": task.area or "",
        "assignee": task.assignee or "",
        "payload": json.loads(task.payload or "{}"),
        "result": task.result,
        "created_by": task.created_by,
        "reviewed_by": task.reviewed_by,
        "created_at": task.created_at.isoformat() if task.created_at else "",
        "updated_at": task.updated_at.isoformat() if task.updated_at else "",
    }


# ── 자동 실행 ─────────────────────────────────────────────────

def execute_approved_task(task: dict) -> str:
    """승인된 태스크를 실행하고 결과를 반환."""
    import json
    task_type = task.get("task_type", "")
    payload = task.get("payload", {})

    try:
        if task_type == "publish_docs":
            from pipeline.domain.agile.wiki_publisher import publish_to_github
            result = publish_to_github(
                result_data=payload.get("result_data", {}),
                owner=payload.get("owner", ""),
                repo=payload.get("repo", ""),
                token=payload.get("token", ""),
                page_title=payload.get("page_title", "SA 설계 문서"),
            )
            return json.dumps(result)

        elif task_type == "verify_sa":
            from pipeline.domain.agile.nodes.verifier import run_verifier
            result = run_verifier(
                sa_data=payload.get("sa_data", {}),
                api_key=payload.get("api_key", ""),
                use_llm=False,
            )
            return json.dumps({"coherence_score": result.coherence_score, "passed": result.passed})

        elif task_type == "import_issues":
            return json.dumps({"imported": len(payload.get("issues", []))})

        elif task_type in ("feature", "bugfix", "refactor", "infra", "doc_sync"):
            return json.dumps({
                "message": f"'{task_type}' 태스크가 승인되었습니다. 담당자에게 알림이 전송됩니다.",
                "area": task.get("area", ""),
                "assignee": task.get("assignee", ""),
            })

        else:
            return json.dumps({"message": f"태스크 타입 '{task_type}' 실행됨"})

    except Exception as e:
        return json.dumps({"error": str(e) or repr(e) or f"{type(e).__name__} (메시지 없음)"})
