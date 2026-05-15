"""
BACKEND_AGENT
main agent에서 spec을 받아 백엔드 설계/구현 계획 구체화
api,db,sevice,val, error handling, tests 중심 사고함
backend qa, domain gate, codgen, verifier가 소비할 산출물 생성함.
"""
from __future__ import annotations

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.domain.dev.nodes._shared import (
    _as_list,
    dedupe,
    api_endpoint,
    table_name,
    column_names,
    component_name,
    artifact_items,
    topology_queue,
    policy_enforcement_result,
)


@pipeline_node("develop_backend_agent")
def develop_backend_agent_node(ctx: NodeContext) -> dict:
    """Map PM/SA backend contracts into a codegen handoff.

    This node must not reinterpret the product design. Missing or inconsistent
    contracts should be caught by QA/gates, not invented here.
    """
    spec = ctx.sget("backend_task_spec", {}) or {}
    dev_task = spec.get("dev_task") or {}
    dev_context = dev_task.get("context") or {}
    apis = _as_list(dev_context.get("target_api_specs")) or artifact_items(ctx, "apis")
    tables = _as_list(dev_context.get("target_table_specs")) or artifact_items(ctx, "tables")
    components = _as_list(dev_context.get("component_specs")) or artifact_items(ctx, "components")
    requirement_ids = dedupe(_as_list(spec.get("requirement_ids")))
    approved_stack = dev_context.get("approved_stack") or spec.get("approved_stack") or {}
    generation_policy = dev_task.get("constraints") or spec.get("generation_policy") or {}
    tq = topology_queue(apis=apis, tables=tables, components=components)
    rework_instruction = dev_context.get("rework_instruction") or spec.get("rework_instruction") or {}

    api_files = [f"api:{ep}" for ep in (api_endpoint(api) for api in apis) if ep]
    table_files = [f"table:{name}" for name in (table_name(t) for t in tables) if name]
    component_files = [f"component:{name}" for name in (component_name(c) for c in components) if name]
    target_files = [str(target) for target in _as_list(spec.get("target_components")) if target]
    files = dedupe([*api_files, *table_files, *component_files, *target_files])

    proposed_changes = dedupe([
        *(f"Implement SA API contract: {api_endpoint(api)}" for api in apis if api_endpoint(api)),
        *(
            f"Persist SA table contract: {table_name(t)}"
            + (f" ({', '.join(column_names(t))})" if column_names(t) else "")
            for t in tables
            if table_name(t)
        ),
        *(f"Expose backend support for SA component: {component_name(c)}" for c in components if component_name(c)),
    ])

    dependencies = dedupe([
        "PM requirements",
        "SA API contracts" if apis else "",
        "SA DB contracts" if tables else "",
        "SA component contracts" if components else "",
        *[str(item) for item in _as_list(spec.get("inputs"))],
    ])

    test_plan = dedupe([
        *(f"Verify request/response contract for {api_endpoint(api)}" for api in apis if api_endpoint(api)),
        *(f"Verify persistence contract for {table_name(t)}" for t in tables if table_name(t)),
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
        "test_plan": dedupe([
            *(test_plan or ["Verify generated backend matches PM/SA contracts."]),
            *[str(item) for item in _as_list(rework_instruction.get("actions"))],
        ]),
        "contract_handoff": {
            "apis": apis,
            "tables": tables,
            "components": components,
            "approved_stack": approved_stack,
            "generation_policy": generation_policy,
            "topology_queue": tq,
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
        "topology_queue": tq,
        "summary_notes": [
            {"order": item["order"], "note": f"{item['kind']}:{item['name']} mapped from {item['source']}"}
            for item in tq
        ],
    }
    return {"backend_result": backend_result, "_thinking": "contract mapping"}
