from __future__ import annotations

from pipeline.core.node_base import NodeContext, pipeline_node


@pipeline_node("dev_patch_planner")
def dev_patch_planner_node(ctx: NodeContext) -> dict:
    tasks = (ctx.sget("dev_task_plan", {}) or {}).get("tasks", []) or []
    impacts = (ctx.sget("dev_impact_output", {}) or {}).get("impacts", []) or []

    files = []
    for impact in impacts:
        for area in impact.get("files_or_areas", [])[:2]:
            files.append({
                "path_hint": area,
                "change_type": "modify",
                "summary": f"Update code related to {impact.get('task_id', 'task')}",
            })

    if not files:
        files.append({
            "path_hint": "backend/pipeline/domain/dev/",
            "change_type": "create",
            "summary": "Add initial development pipeline implementation files",
        })

    return {
        "dev_patch_plan": {
            "thinking": "file-level plan before implementation",
            "files": files,
            "rollout_order": [task.get("task_id", "") for task in tasks if task.get("task_id")],
        }
    }
