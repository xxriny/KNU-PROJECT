from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .artifacts import build_dev_gap_report_artifact, persist_dev_knowledge_artifact
from .utils import _as_dict, _parse_dt


def _snapshot_to_dict(snapshot: Any) -> dict[str, Any]:
    if snapshot is None:
        return {}
    data: dict[str, Any] = {}
    raw = getattr(snapshot, "snapshot_data", "") or "{}"
    try:
        data = json.loads(raw)
    except Exception:
        data = {"raw": raw}
    return {
        "snapshot_id": getattr(snapshot, "id", ""),
        "run_id": getattr(snapshot, "run_id", ""),
        "team_id": getattr(snapshot, "team_id", ""),
        "title": getattr(snapshot, "title", ""),
        "description": getattr(snapshot, "description", ""),
        "version": getattr(snapshot, "version", ""),
        "published_at": getattr(snapshot, "published_at", None).isoformat()
        if getattr(snapshot, "published_at", None)
        else "",
        "data": data,
        "api_contracts": _extract_contracts(data, "api"),
        "component_contracts": _extract_contracts(data, "component"),
        "milestone_status": data.get("milestone_status") if isinstance(data, dict) else {},
    }


def _extract_contracts(data: Any, kind: str) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    keys = (
        ["api_contracts", "apis", "api_modeler_output", "backend_apis"]
        if kind == "api"
        else ["component_contracts", "components", "component_scheduler_output"]
    )
    found: list[dict[str, Any]] = []
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            found.extend([item for item in value if isinstance(item, dict)])
        elif isinstance(value, dict):
            nested = value.get("apis" if kind == "api" else "components")
            if isinstance(nested, list):
                found.extend([item for item in nested if isinstance(item, dict)])
    return found


def spec_loader(state: dict[str, Any], shared_db: Any = None) -> dict[str, Any]:
    # author:xxrin
    # PR 생성 시점에 유효했던 published snapshot을 선택한다.
    if shared_db is None:
        return {
            "status": "WARN",
            "error_type": "SPEC_SNAPSHOT_DB_UNAVAILABLE",
            "published_spec_snapshot": {},
            "spec_outdated": False,
            "latest_snapshot": {},
            "dev_tracking_next_action": "gap_analyzer",
            "current_step": "spec_loader_done",
        }

    from auth.shared_models import PublishedSnapshot

    pr_context = _as_dict(state.get("pr_context"))
    branch_created_at = _parse_dt(pr_context.get("created_at")) or datetime.now()
    team_id = state.get("team_id")

    query = shared_db.query(PublishedSnapshot)
    if team_id:
        query = query.filter(PublishedSnapshot.team_id == team_id)

    all_snapshots = query.order_by(PublishedSnapshot.published_at.desc()).all()
    selected = None
    latest = all_snapshots[0] if all_snapshots else None
    for snapshot in all_snapshots:
        published_at = getattr(snapshot, "published_at", None)
        if published_at and published_at <= branch_created_at.replace(tzinfo=None):
            selected = snapshot
            break

    selected_dict = _snapshot_to_dict(selected)
    latest_dict = _snapshot_to_dict(latest)
    spec_outdated = bool(
        selected
        and latest
        and getattr(latest, "published_at", None)
        and getattr(selected, "id", "") != getattr(latest, "id", "")
    )
    status = "PASS" if selected else "WARN"
    return {
        "status": status,
        "error_type": "" if selected else "SPEC_SNAPSHOT_NOT_FOUND",
        "published_spec_snapshot": selected_dict,
        "spec_outdated": spec_outdated,
        "latest_snapshot": latest_dict,
        "dev_tracking_next_action": "gap_analyzer",
        "current_step": "spec_loader_done",
    }


def dev_knowledge_loader(state: dict[str, Any], shared_db: Any = None) -> dict[str, Any]:
    # author:xxrin
    # 과거 PM 승인/거절 결정을 intent classifier가 참고할 수 있도록 shared.db 지식을 조회한다.
    if shared_db is None:
        return {
            "status": "SKIPPED",
            "dev_knowledge": {
                "count": 0,
                "context_text": "",
                "reason": "shared_db unavailable",
            },
            "dev_knowledge_context": "",
            "dev_tracking_next_action": state.get("dev_tracking_next_action", "milestone_tracker"),
            "current_step": "dev_knowledge_loader_done",
        }

    pr_context = _as_dict(state.get("pr_context"))
    gap_terms = [
        str(gap.get("spec_target") or gap.get("type") or "")
        for gap in state.get("gap_report") or []
        if isinstance(gap, dict)
    ]
    query = " ".join(
        item
        for item in [
            str(pr_context.get("title") or ""),
            *gap_terms,
        ]
        if item
    ).strip()

    try:
        from .knowledge import query_dev_knowledge_artifacts

        result = query_dev_knowledge_artifacts(
            shared_db,
            team_id=str(state.get("team_id") or ""),
            owner=str(pr_context.get("owner") or ""),
            repo=str(pr_context.get("repo") or ""),
            query=query,
            limit=5,
        )
        return {
            "status": "PASS",
            "dev_knowledge": result,
            "dev_knowledge_context": result.get("context_text", ""),
            "dev_tracking_next_action": state.get("dev_tracking_next_action", "milestone_tracker"),
            "current_step": "dev_knowledge_loader_done",
        }
    except Exception as knowledge_error:
        return {
            "status": "WARN",
            "dev_knowledge": {
                "count": 0,
                "context_text": "",
                "error": str(knowledge_error) or type(knowledge_error).__name__,
            },
            "dev_knowledge_context": "",
            "dev_tracking_next_action": state.get("dev_tracking_next_action", "milestone_tracker"),
            "current_step": "dev_knowledge_loader_done",
        }


def analysis_persister(state: dict[str, Any], shared_db: Any = None) -> dict[str, Any]:
    # author: xxrin
    # 분석 결과와 GAP 분류 결과를 shared.db에 영속 저장합니다.
    if shared_db is None:
        return {
            "status": "SKIPPED",
            "analysis_persistence": {"stored": False, "reason": "shared_db unavailable"},
            "dev_tracking_next_action": "develop_embedding",
            "current_step": "analysis_persister_done",
        }

    from auth.shared_models import DevGapItem, DevPrAnalysis, ensure_dev_tracking_schema

    ensure_dev_tracking_schema(shared_db)

    pr_context = _as_dict(state.get("pr_context"))
    snapshot = _as_dict(state.get("published_spec_snapshot"))
    approval_task = _as_dict(state.get("approval_task"))
    classifications = {
        str(item.get("gap_id") or ""): item
        for item in state.get("intent_classification") or []
        if isinstance(item, dict)
    }
    gaps = [gap for gap in (state.get("gap_report") or []) if isinstance(gap, dict)]
    analysis = DevPrAnalysis(
        project_id=str(state.get("project_id") or state.get("team_id") or ""),
        team_id=str(state.get("team_id") or ""),
        owner=str(pr_context.get("owner") or ""),
        repo=str(pr_context.get("repo") or ""),
        pr_number=int(pr_context.get("pr_number") or 0),
        branch_name=str(pr_context.get("branch_name") or ""),
        base_branch=str(pr_context.get("base_branch") or ""),
        head_sha=str(pr_context.get("head_sha") or ""),
        branch_created_at=str(pr_context.get("created_at") or pr_context.get("branch_created_at") or ""),
        source_dir=str(state.get("source_dir") or ""),
        spec_snapshot_id=str(snapshot.get("snapshot_id") or ""),
        spec_outdated=bool(state.get("spec_outdated")),
        approval_status=str(state.get("approval_status") or ""),
        analysis_status=str(state.get("dev_tracking_next_action") or "complete"),
        task_id=str(approval_task.get("task_id") or ""),
        pm_report=json.dumps(state.get("pm_report") or {}, ensure_ascii=False, default=str),
        timeline=json.dumps(state.get("timeline") or [], ensure_ascii=False, default=str),
        gap_count=len(gaps),
        has_high_gap=bool(state.get("has_high_gap")),
    )
    shared_db.add(analysis)
    shared_db.flush()

    gap_count = 0
    for gap in gaps:
        gap_id = str(gap.get("gap_id") or "")
        classification = classifications.get(gap_id, {})
        shared_db.add(
            DevGapItem(
                analysis_id=analysis.id,
                gap_id=gap_id,
                severity=str(gap.get("severity") or ""),
                type=str(gap.get("type") or ""),
                spec_target=str(gap.get("spec_target") or ""),
                implementation_target=str(gap.get("implementation_target") or ""),
                spec_outdated_related=bool(gap.get("spec_outdated_related")),
                intent=str(classification.get("intent") or ""),
                confidence=classification.get("confidence") if isinstance(classification.get("confidence"), (int, float)) else None,
                recommended_action=str(classification.get("recommended_action") or ""),
                approval_status=str(classification.get("approval_status") or state.get("approval_status") or "PENDING_PM_APPROVAL"),
                description=str(gap.get("description") or ""),
            )
        )
        gap_count += 1

    shared_db.commit()
    return {
        "status": "PASS",
        "analysis_persistence": {
            "stored": True,
            "analysis_id": analysis.id,
            "gap_count": gap_count,
        },
        "dev_tracking_next_action": "develop_embedding",
        "current_step": "analysis_persister_done",
    }


def develop_embedding(state: dict[str, Any], shared_db: Any = None) -> dict[str, Any]:
    # author: xxrin
    # Dev GAP 보고서를 아티팩트로 저장하고 검색 텍스트를 함께 기록합니다.
    pr_context = _as_dict(state.get("pr_context"))
    gaps = state.get("gap_report") or []
    approval_status = str(state.get("approval_status") or "PENDING")
    code_chunks_allowed = approval_status == "APPROVED_INTENTIONAL_CHANGE"
    artifact = build_dev_gap_report_artifact(state)
    persistence = persist_dev_knowledge_artifact(artifact, shared_db)
    return {
        "status": persistence.get("status", "WARN"),
        "embedding_result": {
            "status": "stored" if persistence.get("stored") else "warn",
            "reason": persistence.get("error", ""),
            "artifact_id": persistence.get("artifact_id", ""),
            "metadata": {
                "artifact_type": "DEV_GAP_REPORT",
                "pr_number": pr_context.get("pr_number"),
                "branch_name": pr_context.get("branch_name"),
                "approval_status": approval_status,
                "gap_count": len(gaps),
                "has_high_gap": bool(state.get("has_high_gap")),
                # author: xxrin
                # 문서 정책상 PENDING 상태에서는 코드 청크 RAG upsert를 금지하고 GAP artifact만 저장한다.
                "write_enabled": code_chunks_allowed,
                "code_chunks_upserted": False,
                "code_chunk_policy": "blocked_until_pm_approval" if not code_chunks_allowed else "approval_required_path_ready",
            },
        },
        "dev_tracking_next_action": "develop_loop_controller",
        "current_step": "develop_embedding_done",
    }
