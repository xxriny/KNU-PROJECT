from __future__ import annotations

from pipeline.core.node_base import NodeContext, pipeline_node


@pipeline_node("dev_impact_analyzer")
def dev_impact_analyzer_node(ctx: NodeContext) -> dict:
    source_dir = ctx.sget("source_dir", "")
    tasks = (ctx.sget("dev_task_plan", {}) or {}).get("tasks", []) or []
    impacts = []

    for task in tasks:
        files_or_areas = []
        for component in task.get("target_components", []) or []:
            files_or_areas.append(f"component:{component}")
        if source_dir:
            files_or_areas.append(f"source_dir:{source_dir}")
        if not files_or_areas:
            files_or_areas.append("project-wide review")

        impacts.append({
            "task_id": task.get("task_id", ""),
            "files_or_areas": files_or_areas,
            "risks": [
                "Existing interfaces may change",
                "Hidden coupling with current pipeline state",
            ],
            "unknowns": [
                "Concrete file ownership is not resolved yet",
                "Runtime side effects need verification against the actual code path",
            ],
        })

    return {
        "dev_impact_output": {
            "thinking": "surface file touch points before code edits",
            "impacts": impacts,
        }
    }
