from __future__ import annotations

from typing import Any

from pipeline.core.node_base import NodeContext, pipeline_node


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _text_contains_any(items: list[Any], needles: list[str]) -> bool:
    text = " ".join(str(item).lower() for item in items)
    return any(needle.lower() in text for needle in needles if needle)


def _check(check: str, ready: bool, reason: str) -> dict:
    return {
        "check": check,
        "ready": ready,
        "status": "pass" if ready else "fail",
        "reason": reason,
    }


def _common_domain_checks(domain: str, result: dict, spec: dict) -> list[dict]:
    acceptance_criteria = _as_list(spec.get("acceptance_criteria"))
    test_plan = _as_list(result.get("test_plan"))
    proposed_changes = _as_list(result.get("proposed_changes"))
    return [
        _check(
            "requirement_trace",
            bool(_as_list(result.get("requirement_ids"))),
            f"{domain} result must trace back to requirement_ids.",
        ),
        _check(
            "target_files_or_areas",
            bool(_as_list(result.get("files"))),
            f"{domain} result must identify concrete target files or implementation areas.",
        ),
        _check(
            "concrete_changes",
            len(proposed_changes) >= 2,
            f"{domain} result must list at least two concrete proposed_changes.",
        ),
        _check(
            "acceptance_criteria_coverage",
            not acceptance_criteria or len(test_plan) >= len(acceptance_criteria),
            f"{domain} test_plan must cover declared acceptance_criteria.",
        ),
    ]


def _uiux_evidence_checks(ctx: NodeContext) -> list[dict]:
    result = ctx.sget("uiux_result", {}) or {}
    artifact = ctx.sget("uiux_artifact", {}) or {}
    spec = ctx.sget("uiux_task_spec", {}) or {}
    screens = _as_list(artifact.get("screens"))
    flows = _as_list(artifact.get("user_flows"))
    components = _as_list(artifact.get("component_tree"))
    handoff = artifact.get("frontend_handoff") or {}
    screen_states = [state for screen in screens for state in _as_list(screen.get("states"))]
    return [
        *_common_domain_checks("uiux", result, spec),
        _check(
            "screen_coverage",
            bool(screens) and all(screen.get("route") and screen.get("requirement_ids") for screen in screens),
            "UI/UX screens must include routes and requirement trace.",
        ),
        _check(
            "fsm_state_coverage",
            _text_contains_any(screen_states, ["loading"]) and _text_contains_any(screen_states, ["error"]),
            "UI/UX screen states must include loading and error states.",
        ),
        _check(
            "user_flow_coverage",
            bool(flows) and all(flow.get("steps") and flow.get("success_criteria") for flow in flows),
            "UI/UX user flows must include steps and success criteria.",
        ),
        _check(
            "component_contracts",
            bool(components) and all(component.get("source_component") for component in components),
            "UI/UX components must reference source_component contracts.",
        ),
        _check(
            "frontend_handoff",
            bool(_as_list(handoff.get("routes"))) and bool(_as_list(handoff.get("api_client_needs"))),
            "UI/UX frontend_handoff must include routes and api_client_needs.",
        ),
        _check(
            "accessibility_and_empty_error_states",
            bool(_as_list(artifact.get("accessibility_requirements")))
            and bool(_as_list(artifact.get("empty_states")))
            and bool(_as_list(artifact.get("error_states"))),
            "UI/UX artifact must define accessibility, empty, and error states.",
        ),
    ]


def _backend_evidence_checks(ctx: NodeContext) -> list[dict]:
    result = ctx.sget("backend_result", {}) or {}
    spec = ctx.sget("backend_task_spec", {}) or {}
    dev_context = (spec.get("dev_task") or {}).get("context") or {}
    target_apis = _as_list(dev_context.get("target_api_specs")) or _as_list(ctx.sget("apis", []) or [])
    target_tables = _as_list(dev_context.get("target_table_specs")) or _as_list(ctx.sget("tables", []) or [])
    result_text = _as_list(result.get("files")) + _as_list(result.get("proposed_changes")) + _as_list(result.get("test_plan"))
    api_needles = [str(api.get("endpoint") or "") for api in target_apis if isinstance(api, dict)]
    table_needles = [str(table.get("table_name") or "") for table in target_tables if isinstance(table, dict)]
    return [
        *_common_domain_checks("backend", result, spec),
        _check(
            "api_contract_trace",
            not api_needles or _text_contains_any(result_text, api_needles),
            "Backend result must reference target SA API endpoints.",
        ),
        _check(
            "data_contract_trace",
            not table_needles or _text_contains_any(result_text, table_needles),
            "Backend result must reference target SA table/data contracts.",
        ),
        _check(
            "approved_stack_trace",
            not (spec.get("approved_stack") or dev_context.get("approved_stack")) or bool(result.get("approved_stack")),
            "Backend result must carry approved_stack evidence when provided by task spec.",
        ),
    ]


def _frontend_evidence_checks(ctx: NodeContext) -> list[dict]:
    result = ctx.sget("frontend_result", {}) or {}
    spec = ctx.sget("frontend_task_spec", {}) or {}
    frontend_plan = result.get("frontend_plan") or {}
    screen_bindings = _as_list(frontend_plan.get("screen_bindings"))
    return [
        *_common_domain_checks("frontend", result, spec),
        _check(
            "route_handoff",
            bool(_as_list(frontend_plan.get("routes"))),
            "Frontend plan must include routes from UI/UX handoff.",
        ),
        _check(
            "api_client_contracts",
            bool(_as_list(frontend_plan.get("api_client_needs"))),
            "Frontend plan must include api_client_needs tied to SA/backend contracts.",
        ),
        _check(
            "screen_state_bindings",
            bool(screen_bindings)
            and all(_text_contains_any(_as_list(binding.get("states")), ["loading", "error"]) for binding in screen_bindings if isinstance(binding, dict)),
            "Frontend screen_bindings must include loading/error implementation states.",
        ),
    ]


def _evidence_checks(domain: str, ctx: NodeContext) -> list[dict]:
    if domain == "uiux":
        return _uiux_evidence_checks(ctx)
    if domain == "backend":
        return _backend_evidence_checks(ctx)
    if domain == "frontend":
        return _frontend_evidence_checks(ctx)
    return []


def _status_with_retry(retries: int) -> str:
    return "rework" if retries < 1 else "blocked"


def _gate_payload(domain: str, qa_result: dict, retries: int, evidence_checks: list[dict]) -> dict:
    fixes_required = [str(item) for item in (qa_result.get("fixes_required") or []) if str(item).strip()]
    findings = [str(item) for item in (qa_result.get("findings") or []) if str(item).strip()]
    status = (qa_result.get("status") or "").lower()
    failed_evidence = [item for item in evidence_checks if not item.get("ready")]
    evidence_findings = [item["reason"] for item in failed_evidence]
    blocking_findings = fixes_required or findings or evidence_findings

    if status not in {"pass", "rework"}:
        next_status = _status_with_retry(retries)
        return {
            "status": next_status,
            "domain": domain,
            "reason": "Domain QA result is missing or invalid.",
            "blocking_findings": blocking_findings or ["Domain QA result must include status=pass or status=rework."],
            "evidence_checks": evidence_checks,
        }

    if status == "rework" or fixes_required or failed_evidence:
        next_status = _status_with_retry(retries)
        reason = "Domain QA requested one rework cycle."
        if fixes_required:
            reason = "Domain QA fixes are required."
        if failed_evidence:
            reason = "Domain Gate evidence checks failed."
        if next_status == "blocked":
            reason = "Domain Gate still requires changes after the retry budget was exhausted."
        return {
            "status": next_status,
            "domain": domain,
            "reason": reason,
            "blocking_findings": blocking_findings,
            "evidence_checks": evidence_checks,
        }

    return {
        "status": "pass",
        "domain": domain,
        "reason": "Domain QA passed.",
        "blocking_findings": [],
        "evidence_checks": evidence_checks,
    }


@pipeline_node("develop_uiux_domain_gate")
def develop_uiux_domain_gate_node(ctx: NodeContext) -> dict:
    retries = ctx.sget("uiux_retry_count", 0)
    return {
        "uiux_domain_gate_result": _gate_payload(
            "uiux",
            ctx.sget("uiux_qa_result", {}) or {},
            retries,
            _evidence_checks("uiux", ctx),
        ),
        "uiux_retry_count": retries + 1,
        "_thinking": "uiux-domain-gate",
    }


@pipeline_node("develop_backend_domain_gate")
def develop_backend_domain_gate_node(ctx: NodeContext) -> dict:
    retries = ctx.sget("backend_retry_count", 0)
    return {
        "backend_domain_gate_result": _gate_payload(
            "backend",
            ctx.sget("backend_qa_result", {}) or {},
            retries,
            _evidence_checks("backend", ctx),
        ),
        "backend_retry_count": retries + 1,
        "_thinking": "backend-domain-gate",
    }


@pipeline_node("develop_frontend_domain_gate")
def develop_frontend_domain_gate_node(ctx: NodeContext) -> dict:
    retries = ctx.sget("frontend_retry_count", 0)
    return {
        "frontend_domain_gate_result": _gate_payload(
            "frontend",
            ctx.sget("frontend_qa_result", {}) or {},
            retries,
            _evidence_checks("frontend", ctx),
        ),
        "frontend_retry_count": retries + 1,
        "_thinking": "frontend-domain-gate",
    }
