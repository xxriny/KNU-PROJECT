from __future__ import annotations

from typing import Any

from pipeline.core.node_base import NodeContext, pipeline_node


_COMPLETED_STATUSES = {"completed", "complete", "done", "merged", "ready"}
_BLOCKED_STATUSES = {"blocked", "failed", "error"}


def _as_status_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(status).lower() for key, status in value.items()}


def _as_id_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _dedupe_append(items: list[str], item: str) -> list[str]:
    result = list(dict.fromkeys(items))
    if item and item not in result:
        result.append(item)
    return result


def _queue_has_pending(queue: list[dict[str, Any]], status_map: dict[str, str], completed_ids: set[str]) -> bool:
    for item in queue:
        feature_id = str(item.get("feature_id") or "")
        if not feature_id:
            continue
        status = status_map.get(feature_id, str(item.get("status") or "pending").lower())
        if status in _COMPLETED_STATUSES or status in _BLOCKED_STATUSES or feature_id in completed_ids:
            continue
        dependencies = [str(dep) for dep in (item.get("dependencies") or []) if str(dep).strip()]
        if all(dep in completed_ids for dep in dependencies):
            return True
    return False


def _completion_status(ctx: NodeContext) -> tuple[str, str]:
    integration = ctx.sget("integration_qa_result", {}) or {}
    branch = ctx.sget("branch_pr_result", {}) or {}
    develop_next_action = str(ctx.sget("develop_next_action", "") or "").lower()
    integration_status = str(integration.get("status", "") or "").lower()
    branch_status = str(branch.get("status", "") or "").lower()

    if bool(branch.get("merge_ready")):
        return "completed", "branch_pr_result.merge_ready is true"
    if branch_status in {"ready", "completed", "complete"}:
        return "completed", f"branch_pr_result.status={branch_status}"
    if develop_next_action.startswith("blocked"):
        return "blocked", f"develop_next_action={develop_next_action}"
    if integration_status in _BLOCKED_STATUSES:
        return "blocked", f"integration_qa_result.status={integration_status}"
    if branch_status in _BLOCKED_STATUSES:
        return "blocked", f"branch_pr_result.status={branch_status}"
    return "in_progress", "feature work has not reached a terminal state"


@pipeline_node("develop_feature_completion")
def develop_feature_completion_node(ctx: NodeContext) -> dict:
    current_feature_id = str(ctx.sget("current_feature_id", "") or "")
    status_map = _as_status_map(ctx.sget("dev_feature_status", {}) or {})
    completed_ids = _as_id_list(ctx.sget("completed_feature_ids", []) or [])
    blocked_ids = _as_id_list(ctx.sget("blocked_feature_ids", []) or [])
    queue = ctx.sget("dev_feature_queue", []) or []
    if not isinstance(queue, list):
        queue = []

    status, reason = _completion_status(ctx)
    if current_feature_id:
        status_map[current_feature_id] = status
        if status == "completed":
            completed_ids = _dedupe_append(completed_ids, current_feature_id)
            blocked_ids = [item for item in blocked_ids if item != current_feature_id]
        elif status == "blocked":
            blocked_ids = _dedupe_append(blocked_ids, current_feature_id)
            completed_ids = [item for item in completed_ids if item != current_feature_id]

    completed_set = {feature_id for feature_id, value in status_map.items() if value in _COMPLETED_STATUSES}
    completed_set.update(completed_ids)
    has_next_feature = _queue_has_pending(queue, status_map, completed_set)

    updated_queue = []
    for item in queue:
        if not isinstance(item, dict):
            continue
        feature_id = str(item.get("feature_id") or "")
        next_item = dict(item)
        if feature_id in status_map:
            next_item["status"] = status_map[feature_id]
        updated_queue.append(next_item)

    return {
        "dev_feature_status": status_map,
        "completed_feature_ids": completed_ids,
        "blocked_feature_ids": blocked_ids,
        "dev_feature_queue": updated_queue,
        "dev_feature_completion": {
            "feature_id": current_feature_id,
            "status": status,
            "reason": reason,
            "has_next_feature": has_next_feature,
        },
        "_thinking": f"feature-completion-{status}",
    }
