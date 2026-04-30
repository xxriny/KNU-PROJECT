from __future__ import annotations

from typing import Any

from pipeline.core.node_base import NodeContext, pipeline_node


def _to_req_id(req: dict[str, Any], index: int) -> str:
    return str(
        req.get("REQ_ID")
        or req.get("feature_id")
        or req.get("id")
        or f"REQ_{index:03d}"
    )


def _to_req_desc(req: dict[str, Any]) -> str:
    return str(req.get("description") or req.get("desc") or "Implement requirement")


def _to_priority(req: dict[str, Any]) -> str:
    return str(req.get("priority") or req.get("pri") or "Should-have")


@pipeline_node("dev_task_planner")
def dev_task_planner_node(ctx: NodeContext) -> dict:
    sget = ctx.sget
    requirements = (
        sget("requirements_rtm", [])
        or sget("pm_bundle", {}).get("data", {}).get("rtm", [])
        or sget("features", [])
        or []
    )
    components = sget("components", []) or sget("component_scheduler_output", {}).get("components", []) or []

    tasks = []
    for index, req in enumerate(requirements[:12], start=1):
        req_id = _to_req_id(req, index)
        target_components = []
        for comp in components[:8]:
            comp_name = comp.get("component_name") or comp.get("name") or comp.get("nm")
            comp_rtms = comp.get("rtms") or comp.get("rt") or []
            if req_id in comp_rtms and comp_name:
                target_components.append(str(comp_name))

        tasks.append({
            "task_id": f"DEV_TASK_{index:03d}",
            "title": f"{req_id} implementation",
            "description": _to_req_desc(req),
            "priority": _to_priority(req),
            "related_requirements": [req_id],
            "target_components": target_components,
        })

    if not tasks:
        tasks.append({
            "task_id": "DEV_TASK_001",
            "title": "Scaffold development plan",
            "description": "No RTM was found. Start by confirming requirements and selecting target files.",
            "priority": "Must-have",
            "related_requirements": [],
            "target_components": [],
        })

    return {
        "dev_task_plan": {
            "thinking": "RTM-first, component-aware, implementation-ready",
            "tasks": tasks,
        }
    }
