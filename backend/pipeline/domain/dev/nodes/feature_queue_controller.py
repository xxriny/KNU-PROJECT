from __future__ import annotations

from typing import Any

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.domain.dev.nodes._shared import get_requirements, requirement_desc, requirement_id


_COMPLETED_STATUSES = {"completed", "complete", "done", "merged", "ready"}
_ACTIVE_STATUSES = {"in_progress", "running", "active"}
_BLOCKED_STATUSES = {"blocked", "failed", "error"}


def _priority_rank(value: Any) -> int:
    text = str(value or "").strip().lower().replace("_", "-")
    if text in {"critical", "p0", "must", "must-have", "must have"}:
        return 0
    if text in {"high", "p1", "should", "should-have", "should have"}:
        return 1
    if text in {"medium", "normal", "p2", "could", "could-have", "could have"}:
        return 2
    if text in {"low", "p3", "won't-have", "wont-have", "wont have", "nice-to-have"}:
        return 3
    return 2


def _dependencies(req: dict[str, Any]) -> list[str]:
    raw = (
        req.get("dependencies")
        or req.get("depends_on")
        or req.get("dependency_ids")
        or req.get("prerequisites")
        or []
    )
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []


def _normalize_status_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(status).lower() for key, status in value.items()}


def _completed_ids(status_map: dict[str, str], explicit_completed: Any) -> set[str]:
    completed = {feature_id for feature_id, status in status_map.items() if status in _COMPLETED_STATUSES}
    if isinstance(explicit_completed, list):
        completed.update(str(item) for item in explicit_completed if str(item).strip())
    return completed


def _requirement_feature_id(req: dict[str, Any], index: int) -> str:
    return requirement_id(req, index)


def _queue_items(requirements: list[dict[str, Any]], status_map: dict[str, str]) -> list[dict[str, Any]]:
    items = []
    for index, req in enumerate(requirements, start=1):
        feature_id = _requirement_feature_id(req, index)
        status = status_map.get(feature_id, "pending")
        items.append({
            "feature_id": feature_id,
            "title": str(req.get("title") or req.get("name") or feature_id),
            "description": requirement_desc(req),
            "priority": str(req.get("priority") or req.get("pri") or "Should-have"),
            "priority_rank": _priority_rank(req.get("priority") or req.get("pri")),
            "dependencies": _dependencies(req),
            "status": status,
        })
    return sorted(items, key=lambda item: (item["priority_rank"], item["feature_id"]))


def _select_next_feature(
    *,
    queue: list[dict[str, Any]],
    current_feature_id: str,
    status_map: dict[str, str],
    completed: set[str],
) -> str:
    if current_feature_id:
        current_status = status_map.get(current_feature_id, "pending")
        if current_status not in _COMPLETED_STATUSES and current_status not in _BLOCKED_STATUSES:
            return current_feature_id

    for item in queue:
        feature_id = item["feature_id"]
        if status_map.get(feature_id, item.get("status", "pending")) in _ACTIVE_STATUSES:
            return feature_id

    for item in queue:
        feature_id = item["feature_id"]
        status = status_map.get(feature_id, item.get("status", "pending"))
        if status in _COMPLETED_STATUSES or status in _BLOCKED_STATUSES or status in _ACTIVE_STATUSES:
            continue
        if all(dep in completed for dep in item.get("dependencies", [])):
            return feature_id
    return ""


@pipeline_node("develop_feature_queue_controller")
def develop_feature_queue_controller_node(ctx: NodeContext) -> dict:
    sget = ctx.sget
    requirements = get_requirements(sget)
    status_map = _normalize_status_map(sget("dev_feature_status", {}) or {})
    completed = _completed_ids(status_map, sget("completed_feature_ids", []))
    for feature_id in completed:
        status_map.setdefault(feature_id, "completed")
    blocked_ids = sget("blocked_feature_ids", []) or []
    if isinstance(blocked_ids, list):
        for feature_id in blocked_ids:
            if str(feature_id).strip():
                status_map.setdefault(str(feature_id), "blocked")
    current_feature_id = str(sget("current_feature_id", "") or "")

    queue = _queue_items(requirements, status_map)
    selected_feature_id = _select_next_feature(
        queue=queue,
        current_feature_id=current_feature_id,
        status_map=status_map,
        completed=completed,
    )

    selected_feature = {}
    for index, req in enumerate(requirements, start=1):
        if _requirement_feature_id(req, index) == selected_feature_id:
            selected_feature = dict(req)
            break

    next_status_map = dict(status_map)
    if selected_feature_id:
        next_status_map[selected_feature_id] = "in_progress"
        for item in queue:
            if item["feature_id"] == selected_feature_id:
                item["status"] = "in_progress"
                break

    return {
        "current_feature_id": selected_feature_id,
        "development_request_feature": selected_feature,
        "dev_feature_queue": queue,
        "dev_feature_status": next_status_map,
        "_thinking": "feature-priority, dependency-ready, single-feature-dispatch",
    }
