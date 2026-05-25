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
        # author: xxrin
        # PM 승인 후 문서 갱신에서 spec_outdated와 브랜치 시점 고정 정보를 사용할 수 있도록 보존한다.
        "spec_outdated": bool(payload.get("spec_outdated") or _as_dict(result_payload).get("spec_outdated")),
        "approved_spec_version_lock": str(_as_dict(result_payload).get("approved_spec_version_lock") or ""),
        "result": result_payload or {},
        "summary": {
            "pr_number": pr_context.get("pr_number"),
            "branch_name": pr_context.get("branch_name"),
            "gap_count": len(gap_report) if isinstance(gap_report, list) else 0,
        },
    }


def _normalize_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").strip()


def _select_approved_code_files(
    payload: dict[str, Any],
    *,
    max_files: int = 25,
) -> list[dict[str, Any]]:
    # author: xxrin
    # PM 승인 전까지는 코드 청크를 정답 지식으로 보지 않고, 승인 후에는 변경 파일을 우선해서 최소 단위만 저장한다.
    inventory = _as_dict(payload.get("code_inventory"))
    files = inventory.get("files") if isinstance(inventory.get("files"), list) else []
    changed_files = {
        _normalize_path(item)
        for item in payload.get("changed_files") or []
        if _normalize_path(item)
    }
    normalized_files = [
        item for item in files
        if isinstance(item, dict) and _normalize_path(item.get("file") or item.get("path"))
    ]

    if changed_files:
        changed = [
            item for item in normalized_files
            if _normalize_path(item.get("file") or item.get("path")) in changed_files
        ]
        rest = [item for item in normalized_files if item not in changed]
        selected = [*changed, *rest]
    else:
        selected = normalized_files

    if not selected and changed_files:
        selected = [{"file": file_path} for file_path in sorted(changed_files)]

    return selected[:max_files]


def build_approved_code_chunk_artifacts(
    task: dict[str, Any],
    decision_status: str,
    reviewed_by: str = "",
    result_payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    # author: xxrin
    # 문서 기준상 승인된 변경만 RAG 코드 청크로 반영해야 하므로 PM 승인 결과에서 별도 code chunk artifact를 만든다.
    if decision_status != "APPROVED_INTENTIONAL_CHANGE":
        return []

    payload = _as_dict(task.get("payload"))
    pr_context = _as_dict(payload.get("pr_context"))
    inventory = _as_dict(payload.get("code_inventory"))
    symbols_by_file = _as_dict(inventory.get("symbols_by_file"))
    profile = _as_dict(payload.get("implementation_profile"))
    role_map = _as_dict(profile.get("file_role_map"))
    selected_files = _select_approved_code_files(payload)
    approved_at = _now_iso()
    gap_report = payload.get("gap_report") or []
    approved_gap_ids = [
        str(item.get("gap_id") or "")
        for item in _as_dict(result_payload).get("approved_gaps") or gap_report
        if isinstance(item, dict) and str(item.get("gap_id") or "")
    ]

    artifacts: list[dict[str, Any]] = []
    for item in selected_files:
        file_path = _normalize_path(item.get("file") or item.get("path"))
        if not file_path:
            continue
        artifacts.append(
            {
                "artifact_type": "APPROVED_CODE_CHUNK",
                "task_id": task.get("id"),
                "team_id": task.get("team_id") or payload.get("team_id") or "",
                "decision_status": decision_status,
                "reviewed_by": reviewed_by,
                "approved_at": approved_at,
                "pr_context": pr_context,
                "file_path": file_path,
                "file_role": str(role_map.get(file_path) or item.get("role") or ""),
                "file_summary": {
                    key: value
                    for key, value in item.items()
                    if key not in {"content", "raw", "source"}
                },
                "symbols": symbols_by_file.get(file_path) or [],
                "approved_gap_ids": approved_gap_ids,
                "result": result_payload or {},
            }
        )
    return artifacts


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

    code_lines = []
    if artifact.get("artifact_type") == "APPROVED_CODE_CHUNK":
        code_lines.extend(
            [
                f"file_path: {artifact.get('file_path', '')}",
                f"file_role: {artifact.get('file_role', '')}",
                f"approved_gap_ids: {', '.join(artifact.get('approved_gap_ids') or [])}",
            ]
        )
        for symbol in artifact.get("symbols") or []:
            if isinstance(symbol, dict):
                code_lines.append(
                    " | ".join(
                        str(part or "")
                        for part in [
                            symbol.get("name"),
                            symbol.get("type"),
                            symbol.get("line"),
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
            "approved_code:",
            *code_lines,
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
