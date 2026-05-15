"""
BACKEND_AGENT
main agent에서 spec을 받아 백엔드 설계/구현 계획 구체화
api,db,sevice,val, error handling, tests 중심 사고함
backend qa, domain gate, codgen, verifier가 소비할 산출물 생성함.
"""
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


def _component_name(component: dict[str, Any]) -> str:
    return str(component.get("component_name") or component.get("name") or component.get("nm") or "").strip()


def _columns(table: dict[str, Any]) -> list[str]:
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


def _artifact_items(ctx: NodeContext, key: str) -> list[dict[str, Any]]:
    direct = _as_list(ctx.sget(key, []))
    artifact_context = ctx.sget("artifact_rag_context", {}) or {}
    nested = _as_list(artifact_context.get(key))
    return [item for item in [*direct, *nested] if isinstance(item, dict)]


def _topology_queue(
    *,
    apis: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    components: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    order = 1
    for table in tables:
        name = _table_name(table)
        if not name:
            continue
        queue.append({
            "order": order,
            "kind": "table",
            "name": name,
            "source": "SA DB contract",
            "depends_on": [],
        })
        order += 1
    for component in components:
        name = _component_name(component)
        if not name:
            continue
        queue.append({
            "order": order,
            "kind": "component",
            "name": name,
            "source": "SA component contract",
            "depends_on": [_table_name(table) for table in tables if _table_name(table)],
        })
        order += 1
    for api in apis:
        endpoint = _api_endpoint(api)
        if not endpoint:
            continue
        queue.append({
            "order": order,
            "kind": "api",
            "name": endpoint,
            "source": "SA API contract",
            "depends_on": [
                *[_table_name(table) for table in tables if _table_name(table)],
                *[_component_name(component) for component in components if _component_name(component)],
            ],
        })
        order += 1
    return queue


@pipeline_node("develop_backend_agent")
def develop_backend_agent_node(ctx: NodeContext) -> dict:
    """Map PM/SA backend contracts into a codegen handoff.

    This node must not reinterpret the product design. Missing or inconsistent
    contracts should be caught by QA/gates, not invented here.
    """
    spec = ctx.sget("backend_task_spec", {}) or {}
    dev_task = spec.get("dev_task") or {}
    dev_context = dev_task.get("context") or {}
    apis = _as_list(dev_context.get("target_api_specs")) or _artifact_items(ctx, "apis")
    tables = _as_list(dev_context.get("target_table_specs")) or _artifact_items(ctx, "tables")
    components = _as_list(dev_context.get("component_specs")) or _artifact_items(ctx, "components")
    requirement_ids = _dedupe(_as_list(spec.get("requirement_ids")))
    approved_stack = dev_context.get("approved_stack") or spec.get("approved_stack") or {}
    generation_policy = dev_task.get("constraints") or spec.get("generation_policy") or {}
    topology_queue = _topology_queue(apis=apis, tables=tables, components=components)
    rework_instruction = dev_context.get("rework_instruction") or spec.get("rework_instruction") or {}

    api_files = [f"api:{endpoint}" for endpoint in (_api_endpoint(api) for api in apis) if endpoint]
    table_files = [f"table:{name}" for name in (_table_name(table) for table in tables) if name]
    component_files = [
        f"component:{name}"
        for name in (_component_name(component) for component in components)
        if name
    ]
    target_files = [str(target) for target in _as_list(spec.get("target_components")) if target]
    files = _dedupe([*api_files, *table_files, *component_files, *target_files])

    proposed_changes = _dedupe([
        *(f"Implement SA API contract: {_api_endpoint(api)}" for api in apis if _api_endpoint(api)),
        *(
            f"Persist SA table contract: {_table_name(table)}"
            + (f" ({', '.join(_columns(table))})" if _columns(table) else "")
            for table in tables
            if _table_name(table)
        ),
        *(f"Expose backend support for SA component: {_component_name(component)}" for component in components if _component_name(component)),
    ])

    dependencies = _dedupe([
        "PM requirements",
        "SA API contracts" if apis else "",
        "SA DB contracts" if tables else "",
        "SA component contracts" if components else "",
        *[str(item) for item in _as_list(spec.get("inputs"))],
    ])

    test_plan = _dedupe([
        *(f"Verify request/response contract for {_api_endpoint(api)}" for api in apis if _api_endpoint(api)),
        *(f"Verify persistence contract for {_table_name(table)}" for table in tables if _table_name(table)),
        *[str(item) for item in _as_list(spec.get("acceptance_criteria"))],
    ])

    missing = []
    if not apis:
        missing.append("SA API contracts are empty.")
    if not tables:
        missing.append("SA DB contracts are empty.")

    backend_result = {
        "status": "draft",
        "domain": "backend",
        "summary": "Mapped PM/SA backend contracts into codegen inputs.",
        "requirement_ids": requirement_ids,
        "proposed_changes": proposed_changes,
        "files": files or ["backend:contract-handoff"],
        "dependencies": dependencies,
        "test_plan": _dedupe([
            *(test_plan or ["Verify generated backend matches PM/SA contracts."]),
            *[str(item) for item in _as_list(rework_instruction.get("actions"))],
        ]),
        "contract_handoff": {
            "apis": apis,
            "tables": tables,
            "components": components,
            "approved_stack": approved_stack,
            "generation_policy": generation_policy,
            "topology_queue": topology_queue,
            "summary_notes": [
                "Generate in topology_queue order.",
                "After each module is generated, append a concise note instead of carrying full prior context.",
                "Do not add contracts that are absent from PM/SA inputs.",
            ],
            "missing_contracts": missing,
            "rework_instruction": rework_instruction,
        },
        "approved_stack": approved_stack,
        "generation_policy": generation_policy,
        "policy_enforcement": policy_enforcement_result(),
        "rework_instruction": rework_instruction,
        "topology_queue": topology_queue,
        "summary_notes": [
            {"order": item["order"], "note": f"{item['kind']}:{item['name']} mapped from {item['source']}"}
            for item in topology_queue
        ],
    }
    return {"backend_result": backend_result, "_thinking": "contract mapping"}
