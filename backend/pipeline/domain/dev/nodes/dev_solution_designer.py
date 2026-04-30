from __future__ import annotations

from pipeline.core.node_base import NodeContext, pipeline_node


@pipeline_node("dev_solution_designer")
def dev_solution_designer_node(ctx: NodeContext) -> dict:
    tasks = (ctx.sget("dev_task_plan", {}) or {}).get("tasks", []) or []
    impacts = {
        item.get("task_id", ""): item
        for item in ((ctx.sget("dev_impact_output", {}) or {}).get("impacts", []) or [])
    }
    solutions = []

    for task in tasks:
        task_id = task.get("task_id", "")
        impact = impacts.get(task_id, {})
        target_scope = ", ".join(impact.get("files_or_areas", [])[:3]) or "target files"
        solutions.append({
            "task_id": task_id,
            "approach": f"Implement incrementally in {target_scope} and keep existing contracts stable.",
            "steps": [
                "Locate the current entry point and dependent state updates.",
                "Add or extend the smallest viable module for the task.",
                "Connect the new behavior through existing pipeline or API boundaries.",
                "Verify regression risk with focused tests or manual flow checks.",
            ],
            "validation": [
                "Confirm the target requirement is covered.",
                "Check that existing result shaping still produces stable output.",
            ],
        })

    return {
        "dev_solution_output": {
            "thinking": "incremental integration, stable contracts, explicit verification",
            "solutions": solutions,
        }
    }
