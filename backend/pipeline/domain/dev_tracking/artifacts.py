from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def build_dev_gap_decision_artifact(
    task: dict[str, Any],
    decision_status: str,
    reviewed_by: str = "",
    result_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # PM 결정 이후 문서/RAG/PR 알림이 같은 입력을 보도록 결정 아티팩트를 한 번에 구성한다.
    payload = _as_dict(task.get("payload"))
    pr_context = _as_dict(payload.get("pr_context"))
    gap_report = payload.get("gap_report") or []
    return {
        "artifact_type": "DEV_GAP_DECISION",
        "task_id": task.get("id"),
        "team_id": task.get("team_id") or payload.get("team_id") or "",
        "decision_status": decision_status,
        "reviewed_by": reviewed_by,
        "decided_at": _now_iso(),
        "pr_context": pr_context,
        "pm_report": payload.get("pm_report") or {},
        "gap_report": gap_report,
        "intent_classification": payload.get("intent_classification") or [],
        "milestone_status": payload.get("milestone_status") or {},
        "result": result_payload or {},
        "summary": {
            "pr_number": pr_context.get("pr_number"),
            "branch_name": pr_context.get("branch_name"),
            "gap_count": len(gap_report) if isinstance(gap_report, list) else 0,
        },
    }


def build_dev_gap_report_artifact(state: dict[str, Any]) -> dict[str, Any]:
    # 분석 직후의 GAP 리포트를 PM 결정 전 검색 가능한 지식 단위로 정규화한다.
    pr_context = _as_dict(state.get("pr_context"))
    gaps = state.get("gap_report") or []
    return {
        "artifact_type": "DEV_GAP_REPORT",
        "team_id": state.get("team_id") or "",
        "task_id": _as_dict(state.get("approval_task")).get("task_id") or "",
        "decision_status": state.get("approval_status", "PENDING"),
        "pr_context": pr_context,
        "pm_report": state.get("pm_report") or {},
        "gap_report": gaps,
        "intent_classification": state.get("intent_classification") or [],
        "milestone_status": state.get("milestone_status") or {},
        "summary": {
            "pr_number": pr_context.get("pr_number"),
            "branch_name": pr_context.get("branch_name"),
            "approval_status": state.get("approval_status", "PENDING"),
            "gap_count": len(gaps),
            "has_high_gap": bool(state.get("has_high_gap")),
        },
    }


def artifact_to_searchable_text(artifact: dict[str, Any]) -> str:
    # 벡터 DB가 제거된 현재 구조에서는 SQLite 텍스트 필드를 검색/프롬프트 컨텍스트의 원천으로 사용한다.
    pr_context = _as_dict(artifact.get("pr_context"))
    pm_report = _as_dict(artifact.get("pm_report"))
    gap_lines = []
    for gap in artifact.get("gap_report") or []:
        if not isinstance(gap, dict):
            continue
        gap_lines.append(
            " | ".join(
                str(part or "")
                for part in [
                    gap.get("gap_id"),
                    gap.get("severity"),
                    gap.get("type"),
                    gap.get("spec_target"),
                    gap.get("implementation_target"),
                    gap.get("description"),
                ]
            )
        )

    intent_lines = []
    for item in artifact.get("intent_classification") or []:
        if not isinstance(item, dict):
            continue
        intent_lines.append(
            " | ".join(
                str(part or "")
                for part in [
                    item.get("gap_id"),
                    item.get("intent"),
                    item.get("recommended_action"),
                    item.get("reason"),
                ]
            )
        )

    return "\n".join(
        [
            f"artifact_type: {artifact.get('artifact_type', '')}",
            f"decision_status: {artifact.get('decision_status', '')}",
            f"task_id: {artifact.get('task_id', '')}",
            f"repo: {pr_context.get('owner', '')}/{pr_context.get('repo', '')}",
            f"pr_number: {pr_context.get('pr_number', '')}",
            f"branch: {pr_context.get('branch_name', '')}",
            f"summary: {pm_report.get('summary', artifact.get('summary', ''))}",
            "gaps:",
            *gap_lines,
            "intent_classification:",
            *intent_lines,
        ]
    ).strip()


def persist_dev_knowledge_artifact(
    artifact: dict[str, Any],
    shared_db: Any = None,
) -> dict[str, Any]:
    # Dev Tracking 지식을 shared.db에 append-only 기록으로 남긴다.
    # 실제 벡터 인덱스가 복구되면 이 함수 뒤에 embedding upsert를 연결하면 된다.
    owns_session = False
    db = shared_db
    if db is None:
        try:
            from auth.database import Base, SharedSessionLocal, shared_engine
            from auth.shared_models import DevKnowledgeArtifact

            Base.metadata.create_all(bind=shared_engine, tables=[DevKnowledgeArtifact.__table__])
            db = SharedSessionLocal()
            owns_session = True
        except Exception as db_error:
            return {
                "status": "WARN",
                "stored": False,
                "error": str(db_error) or type(db_error).__name__,
            }
    else:
        from auth.database import Base
        from auth.shared_models import DevKnowledgeArtifact

        try:
            Base.metadata.create_all(bind=db.get_bind(), tables=[DevKnowledgeArtifact.__table__])
        except Exception:
            pass

    try:
        pr_context = _as_dict(artifact.get("pr_context"))
        row = DevKnowledgeArtifact(
            team_id=str(artifact.get("team_id") or ""),
            artifact_type=str(artifact.get("artifact_type") or "DEV_GAP_REPORT"),
            source="dev_tracking",
            owner=str(pr_context.get("owner") or ""),
            repo=str(pr_context.get("repo") or ""),
            pr_number=int(pr_context.get("pr_number") or 0),
            branch_name=str(pr_context.get("branch_name") or ""),
            task_id=str(artifact.get("task_id") or ""),
            decision_status=str(artifact.get("decision_status") or ""),
            content_json=json.dumps(artifact, ensure_ascii=False, default=str),
            searchable_text=artifact_to_searchable_text(artifact),
        )
        db.add(row)
        db.commit()
        return {
            "status": "PASS",
            "stored": True,
            "artifact_id": row.id,
            "artifact_type": row.artifact_type,
        }
    except Exception as store_error:
        try:
            db.rollback()
        except Exception:
            pass
        return {
            "status": "WARN",
            "stored": False,
            "error": str(store_error) or type(store_error).__name__,
        }
    finally:
        if owns_session and db is not None:
            db.close()
