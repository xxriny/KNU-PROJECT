from __future__ import annotations

from typing import Any

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.domain.dev.nodes._shared import policy_enforcement_result


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in items if str(item or "").strip()))


def _api_endpoint(api: dict[str, Any]) -> str:
    return str(api.get("endpoint") or api.get("ep") or api.get("path") or "").strip()


def _table_name(table: dict[str, Any]) -> str:
    return str(table.get("table_name") or table.get("name") or table.get("nm") or "").strip()


def _column_names(table: dict[str, Any]) -> list[str]:
    columns = table.get("columns") or table.get("cols") or []
    if isinstance(columns, str):
        return [part.split(":", 1)[0].strip() for part in columns.split(",") if part.strip()]
    names = []
    for column in _as_list(columns):
        if isinstance(column, dict):
            name = str(column.get("name") or column.get("column_name") or "").strip()
        else:
            name = str(column).strip()
        if name:
            names.append(name)
    return names


def _frontend_plan_from_contracts(
    *,
    uiux_artifact: dict,
    apis: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    backend_codegen: dict,
) -> dict:
    handoff = uiux_artifact.get("frontend_handoff") or {}
    screens = _as_list(uiux_artifact.get("screens"))
    routes = _dedupe([
        *[str(route) for route in _as_list(handoff.get("routes"))],
        *[str(screen.get("route")) for screen in screens if isinstance(screen, dict) and screen.get("route")],
    ])
    api_client_needs = _dedupe([
        *[str(item) for item in _as_list(handoff.get("api_client_needs"))],
        *[_api_endpoint(api) for api in apis if _api_endpoint(api)],
    ])
    data_contracts = _dedupe([
        *[str(item) for item in _as_list(handoff.get("data_contracts"))],
        *[
            f"{_table_name(table)}.{column}"
            for table in tables
            for column in _column_names(table)
            if _table_name(table)
        ],
    ])
    return {
        "routes": routes,
        "api_client_needs": api_client_needs,
        "data_contracts": data_contracts,
        "state_management": _as_list(handoff.get("state_management_notes")) or [
            "Represent loading, success, empty, and error states per screen."
        ],
        "screen_bindings": [
            {
                "screen": screen.get("name"),
                "route": screen.get("route"),
                "states": _as_list(screen.get("states")),
                "api_dependencies": _as_list(screen.get("api_dependencies")),
                "data_dependencies": _as_list(screen.get("data_dependencies")),
            }
            for screen in screens
            if isinstance(screen, dict)
        ],
        "backend_output_dir": backend_codegen.get("output_dir", ""),
        "backend_verification_adapter": backend_codegen.get("verification_adapter", ""),
    }


@pipeline_node("develop_frontend_agent")
def develop_frontend_agent_node(ctx: NodeContext) -> dict:
    """Map UIUX and SA contracts into frontend codegen inputs."""
    spec = ctx.sget("frontend_task_spec", {}) or {}
    dev_task = spec.get("dev_task") or {}
    dev_context = dev_task.get("context") or {}
    uiux_artifact = ctx.sget("uiux_artifact", {}) or {}
    apis = _as_list(dev_context.get("target_api_specs")) or _as_list(ctx.sget("apis", []))
    tables = _as_list(dev_context.get("target_table_specs")) or _as_list(ctx.sget("tables", []))
    backend_codegen = ctx.sget("backend_codegen_result", {}) or {}
    targets = _as_list(dev_context.get("target_components")) or _as_list(spec.get("target_components"))
    requirement_ids = _dedupe(_as_list(spec.get("requirement_ids")))
    rework_instruction = dev_context.get("rework_instruction") or spec.get("rework_instruction") or {}
    approved_stack = dev_context.get("approved_stack") or spec.get("approved_stack") or {}
    generation_policy = dev_task.get("constraints") or spec.get("generation_policy") or {}
    frontend_plan = _frontend_plan_from_contracts(
        uiux_artifact=uiux_artifact,
        apis=[api for api in apis if isinstance(api, dict)],
        tables=[table for table in tables if isinstance(table, dict)],
        backend_codegen=backend_codegen,
    )

    files = _dedupe([
        *[f"route:{route}" for route in frontend_plan["routes"]],
        *[f"frontend:{target}" for target in targets],
        "api:client" if frontend_plan["api_client_needs"] else "",
    ])
    dependencies = _dedupe([
        "UIUX frontend_handoff",
        "SA API contracts" if frontend_plan["api_client_needs"] else "",
        "SA data contracts" if frontend_plan["data_contracts"] else "",
        *frontend_plan["api_client_needs"],
    ])
    test_plan = _dedupe([
        *(f"Render route {route}" for route in frontend_plan["routes"]),
        "Verify loading, empty, error, and success UI states.",
        *(f"Verify API client contract for {endpoint}" for endpoint in frontend_plan["api_client_needs"]),
        *[str(item) for item in _as_list(spec.get("acceptance_criteria"))],
    ])

    frontend_result = {
        "status": "draft",
        "domain": "frontend",
        "summary": "Mapped UIUX and SA contracts into frontend codegen inputs.",
        "requirement_ids": requirement_ids,
        "proposed_changes": _dedupe([
            *(f"Implement UIUX route contract: {route}" for route in frontend_plan["routes"]),
            *(f"Bind frontend API client to SA endpoint: {endpoint}" for endpoint in frontend_plan["api_client_needs"]),
        ]),
        "files": files or ["frontend:contract-handoff"],
        "dependencies": dependencies,
        "test_plan": _dedupe([
            *test_plan,
            *[str(item) for item in _as_list(rework_instruction.get("actions"))],
        ]),
        "frontend_plan": frontend_plan,
        "approved_stack": approved_stack,
        "generation_policy": generation_policy,
        "policy_enforcement": policy_enforcement_result(),
        "rework_instruction": rework_instruction,
    }
    return {"frontend_result": frontend_result, "_thinking": "contract handoff"}
