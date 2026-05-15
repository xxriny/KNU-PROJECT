from __future__ import annotations

from typing import Any

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.domain.dev.nodes._shared import (
    _as_list,
    dedupe,
    api_endpoint,
    table_name,
    column_names,
    component_name,
    artifact_items,
    slug,
    looks_like_endpoint,
    policy_enforcement_result,
)
from pipeline.domain.dev.schemas import UIUXArtifact


def _screen_targets(spec: dict, components: list[dict[str, Any]]) -> list[str]:
    targets = [str(item) for item in _as_list(spec.get("target_components")) if item]
    component_targets = [component_name(c) for c in components if component_name(c)]
    return dedupe([*targets, *component_targets]) or ["MainScreen"]


def _api_dependencies(spec: dict, apis: list[dict[str, Any]]) -> list[str]:
    return dedupe([
        *[
            str(item).strip()
            for item in [*_as_list(spec.get("inputs")), *_as_list(spec.get("acceptance_criteria"))]
            if looks_like_endpoint(item)
        ],
        *[api_endpoint(api) for api in apis if api_endpoint(api)],
    ])


def _data_dependencies(tables: list[dict[str, Any]]) -> list[str]:
    return dedupe([
        f"{table_name(t)}.{col}"
        for t in tables
        for col in column_names(t)
        if table_name(t)
    ])


def _build_uiux_artifact(
    *,
    spec: dict,
    apis: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    components: list[dict[str, Any]],
    result: dict,
) -> dict:
    dev_task = spec.get("dev_task") or {}
    dev_context = dev_task.get("context") or {}
    targets = _as_list(dev_context.get("target_components")) or _screen_targets(spec, components)
    requirement_ids = dedupe(_as_list(spec.get("requirement_ids")))
    rework_instruction = dev_context.get("rework_instruction") or spec.get("rework_instruction") or {}
    approved_stack = dev_context.get("approved_stack") or spec.get("approved_stack") or {}
    generation_policy = dev_task.get("constraints") or spec.get("generation_policy") or {}
    acceptance_criteria = dedupe(_as_list(spec.get("acceptance_criteria")))
    api_deps = _api_dependencies(spec, apis)
    data_deps = _data_dependencies(tables)
    component_sources = dedupe([component_name(c) for c in components if component_name(c)])

    screens = []
    component_tree = []
    routes = []
    for index, target in enumerate(targets[:6], start=1):
        name = str(target).replace("uiux:", "").replace("frontend:", "") or f"Screen {index}"
        route = f"/{slug(name, f'screen-{index}')}"
        child_components = ["Header", "Content", "ActionArea", "FeedbackMessage"]
        routes.append(route)
        screens.append({
            "id": f"screen_{index}",
            "name": name,
            "purpose": "Implement the PM requirement through the mapped SA contracts.",
            "route": route,
            "requirement_ids": requirement_ids,
            "acceptance_criteria": acceptance_criteria,
            "primary_actions": ["view", "submit" if api_deps else "navigate"],
            "api_dependencies": api_deps,
            "data_dependencies": data_deps,
            "states": ["default", "loading", "empty", "error"],
        })
        component_tree.append({
            "name": name,
            "role": "page",
            "source_component": component_sources[index - 1] if index - 1 < len(component_sources) else name,
            "requirement_ids": requirement_ids,
            "children": child_components,
            "states": ["default", "loading", "empty", "error"],
        })
        for child in child_components:
            component_tree.append({
                "name": f"{name}{child}",
                "role": "component",
                "source_component": child,
                "requirement_ids": requirement_ids,
                "children": [],
                "states": ["default", "loading", "empty", "error"] if child == "FeedbackMessage" else ["default"],
            })
    if screens:
        component_tree.append({
            "name": "AppLayout",
            "role": "layout",
            "source_component": "Layout",
            "requirement_ids": requirement_ids,
            "children": [screen["name"] for screen in screens],
            "states": ["default", "loading", "empty", "error"],
        })

    form_fields = [dep.split(".", 1)[1] for dep in data_deps if "." in dep][:8]
    endpoint_summary = ", ".join(api_deps) if api_deps else "the mapped SA contract"
    implementation_notes = dedupe([
        *_as_list(result.get("proposed_changes")),
        *(str(item) for item in _as_list(rework_instruction.get("actions"))),
        "Keep api_dependencies limited to SA endpoint strings.",
        "Keep data_contracts limited to SA table.field contracts.",
        "Render explicit success and failure feedback from API responses.",
    ])
    artifact = UIUXArtifact(
        status="ready_for_frontend",
        screens=screens,
        user_flows=[{
            "id": "flow_1",
            "name": "Primary requirement flow",
            "requirement_ids": requirement_ids,
            "steps": [
                "Open the mapped screen route.",
                "Review the default, loading, empty, or error state.",
                f"Use the primary action backed by {endpoint_summary}.",
                "Show success feedback after a successful API response.",
                "Show validation or request failure feedback when an API response fails.",
                "Confirm the acceptance criteria result.",
            ],
            "success_criteria": acceptance_criteria,
        }],
        component_tree=component_tree,
        form_states=[{
            "form": "PrimaryContractForm",
            "fields": form_fields,
            "data_dependencies": data_deps,
            "validation_rules": ["Required SA data fields must show validation errors."],
            "error_states": ["validation_error", "submit_failed"],
        }],
        empty_states=["No data from the mapped contract yet."],
        error_states=["Mapped API request failed.", "Mapped data contract validation failed."],
        accessibility_requirements=[
            "Controls have accessible names.",
            "Form errors are associated with fields.",
            "Keyboard navigation follows visual order.",
            "State is not conveyed by color alone.",
        ],
        frontend_handoff={
            "routes": routes,
            "api_client_needs": api_deps,
            "data_contracts": data_deps,
            "state_management_notes": ["Represent default, loading, empty, error, and success states explicitly."],
            "implementation_notes": implementation_notes,
        },
    )
    return artifact.model_dump()


@pipeline_node("develop_uiux_agent")
def develop_uiux_agent_node(ctx: NodeContext) -> dict:
    """Map PM/SA artifacts into a frontend handoff without redefining contracts."""
    spec = ctx.sget("uiux_task_spec", {}) or {}
    dev_task = spec.get("dev_task") or {}
    dev_context = dev_task.get("context") or {}
    apis = _as_list(dev_context.get("target_api_specs")) or artifact_items(ctx, "apis")
    tables = _as_list(dev_context.get("target_table_specs")) or artifact_items(ctx, "tables")
    components = _as_list(dev_context.get("component_specs")) or artifact_items(ctx, "components")
    targets = _as_list(dev_context.get("target_components")) or _screen_targets(spec, components)
    requirement_ids = dedupe(_as_list(spec.get("requirement_ids")))
    rework_instruction = dev_context.get("rework_instruction") or spec.get("rework_instruction") or {}
    approved_stack = dev_context.get("approved_stack") or spec.get("approved_stack") or {}
    generation_policy = dev_task.get("constraints") or spec.get("generation_policy") or {}

    result = {
        "status": "draft",
        "domain": "uiux",
        "summary": "Mapped PM/SA contracts into UIUX frontend handoff.",
        "requirement_ids": requirement_ids,
        "proposed_changes": dedupe([
            *(f"Create screen handoff for {target}" for target in targets[:6]),
            *(f"Bind UI interaction to SA endpoint: {api_endpoint(api)}" for api in apis if api_endpoint(api)),
        ]),
        "files": dedupe([f"uiux:{target}" for target in targets[:6]]),
        "dependencies": dedupe([
            "PM requirements",
            "SA API contracts" if apis else "",
            "SA DB contracts" if tables else "",
            "SA component contracts" if components else "",
        ]),
        "test_plan": dedupe([
            "Validate screen route coverage.",
            "Validate default/loading/empty/error states.",
            *[str(item) for item in _as_list(spec.get("acceptance_criteria"))],
            *[str(item) for item in _as_list(rework_instruction.get("actions"))],
        ]),
        "approved_stack": approved_stack,
        "generation_policy": generation_policy,
        "policy_enforcement": policy_enforcement_result(),
        "rework_instruction": rework_instruction,
    }
    return {
        "uiux_result": result,
        "uiux_artifact": _build_uiux_artifact(
            spec=spec,
            apis=apis,
            tables=tables,
            components=components,
            result=result,
        ),
        "_thinking": "contract handoff",
    }
