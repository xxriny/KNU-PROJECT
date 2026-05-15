
"""
dev 노드 공통 utils
데이터 추출/정규화/계약 생성
"""
from __future__ import annotations

import re
from typing import Any

from pipeline.domain.dev.schemas import DevTask

# state와 previous result에서 pm/sa 산출물 찾음
def _previous_result(state_get) -> dict[str, Any]:
    return state_get("previous_result", {}) or {}

# sa 산출물 탐색
def _first_list_by_keys(payload: Any, keys: set[str], *, max_depth: int = 5) -> list[dict[str, Any]]:
    if max_depth < 0:
        return []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in keys and isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        for value in payload.values():
            found = _first_list_by_keys(value, keys, max_depth=max_depth - 1)
            if found:
                return found
    if isinstance(payload, list):
        for item in payload:
            found = _first_list_by_keys(item, keys, max_depth=max_depth - 1)
            if found:
                return found
    return []


def _has_sa_payload(payload: dict[str, Any]) -> bool:
    keys = {"components", "component_specs", "ui_components", "apis", "api_specs", "endpoints", "tables", "db_tables", "entities"}
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if any(key in data for key in keys):
        return True
    return any(
        _first_list_by_keys(data, group, max_depth=3)
        for group in (
            {"components", "component_specs", "ui_components"},
            {"apis", "api_specs", "endpoints"},
            {"tables", "db_tables", "entities"},
        )
    )

# sa 산출물을 하나의 표준 dev-facing bundle로 변환
def _raw_sa_bundle(state_get) -> tuple[dict[str, Any], str]:
    previous = _previous_result(state_get)
    candidates = [
        ("state.sa_arch_bundle", state_get("sa_arch_bundle", {}) or {}),
        ("state.sa_artifacts", state_get("sa_artifacts", {}) or {}),
        ("previous.sa_arch_bundle", previous.get("sa_arch_bundle", {}) or {}),
        ("previous.sa_artifacts", previous.get("sa_artifacts", {}) or {}),
        ("previous", previous),
    ]
    for source, payload in candidates:
        if isinstance(payload, dict) and payload and _has_sa_payload(payload):
            return payload, source
    return {}, ""


def _bundle_data(raw: dict[str, Any]) -> dict[str, Any]:
    data = raw.get("data")
    if isinstance(data, dict):
        return data
    return raw

# sa 산출물을 하나의 표준 dev-facing bundle로 변환
def normalize_sa_bundle(state_get) -> dict[str, Any]:
    """Return the DEV-facing SA contract without changing PM/SA producers."""
    raw, source = _raw_sa_bundle(state_get)
    previous = _previous_result(state_get)
    raw_metadata = raw.get("metadata", {}) if isinstance(raw.get("metadata"), dict) else {}
    previous_metadata = previous.get("metadata", {}) if isinstance(previous.get("metadata"), dict) else {}
    previous_sa_bundle = previous.get("sa_arch_bundle", {}) if isinstance(previous.get("sa_arch_bundle"), dict) else {}
    previous_sa_metadata = (
        previous_sa_bundle.get("metadata", {})
        if isinstance(previous_sa_bundle.get("metadata"), dict)
        else {}
    )

    session_id = str(
        raw_metadata.get("session_id")
        or state_get("run_id", "")
        or previous_metadata.get("session_id")
        or "unknown"
    )
    version = str(
        raw.get("version")
        or raw_metadata.get("version")
        or state_get("current_version", "")
        or state_get("version", "")
        or previous_sa_bundle.get("version")
        or previous_sa_metadata.get("version")
        or "v1.0"
    )
    bundle_id = str(
        raw.get("bundle_id")
        or raw_metadata.get("bundle_id")
        or f"{session_id}_SA_BNDL"
    )

    data = _bundle_data(raw)
    components = _first_list_by_keys(data, {"components", "component_specs", "ui_components"})
    apis = _first_list_by_keys(data, {"apis", "api_specs", "endpoints"})
    tables = _first_list_by_keys(data, {"tables", "db_tables", "entities"})

    metadata = dict(raw_metadata)
    metadata.update({
        "version": version,
        "session_id": session_id,
        "bundle_id": bundle_id,
    })
    # 최종 output, main으로 전달할 계약 구조
    return {
        "phase": str(raw.get("phase") or "SA"),
        "version": version,
        "bundle_id": bundle_id,
        "metadata": metadata,
        "data": {
            "components": components,
            "apis": apis,
            "tables": tables,
        },
        "source": source,
        "available": bool(raw),
    }

# dev 노드들이 직접 state 구조를 탐색하지 않도록 함
# get_method 
# main_ag와 codegen/qa 노드가 사용함
def get_requirements(state_get) -> list[dict[str, Any]]:
    previous = _previous_result(state_get)
    return (
        state_get("requirements_rtm", [])
        or previous.get("requirements_rtm", [])
        or previous.get("pm_bundle", {}).get("data", {}).get("rtm", [])
        or _first_list_by_keys(state_get("sa_arch_bundle", {}) or {}, {"requirements_rtm", "rtm", "requirements"})
        or _first_list_by_keys(state_get("sa_artifacts", {}) or {}, {"requirements_rtm", "rtm", "requirements"})
        or []
    )


def get_components(state_get) -> list[dict[str, Any]]:
    previous = _previous_result(state_get)
    sa_bundle = normalize_sa_bundle(state_get)
    return (
        state_get("components", [])
        or sa_bundle.get("data", {}).get("components", [])
        or previous.get("components", [])
        or previous.get("component_scheduler_output", {}).get("components", [])
        or _first_list_by_keys(state_get("sa_arch_bundle", {}) or {}, {"components", "component_specs", "ui_components"})
        or _first_list_by_keys(state_get("sa_artifacts", {}) or {}, {"components", "component_specs", "ui_components"})
        or []
    )


def get_apis(state_get) -> list[dict[str, Any]]:
    previous = _previous_result(state_get)
    sa_bundle = normalize_sa_bundle(state_get)
    return (
        state_get("apis", [])
        or sa_bundle.get("data", {}).get("apis", [])
        or previous.get("apis", [])
        or _first_list_by_keys(state_get("sa_arch_bundle", {}) or {}, {"apis", "api_specs", "endpoints"})
        or _first_list_by_keys(state_get("sa_artifacts", {}) or {}, {"apis", "api_specs", "endpoints"})
        or _first_list_by_keys(previous, {"apis", "api_specs", "endpoints"})
        or []
    )


def get_tables(state_get) -> list[dict[str, Any]]:
    previous = _previous_result(state_get)
    sa_bundle = normalize_sa_bundle(state_get)
    return (
        state_get("tables", [])
        or sa_bundle.get("data", {}).get("tables", [])
        or previous.get("tables", [])
        or _first_list_by_keys(state_get("sa_arch_bundle", {}) or {}, {"tables", "db_tables", "entities"})
        or _first_list_by_keys(state_get("sa_artifacts", {}) or {}, {"tables", "db_tables", "entities"})
        or _first_list_by_keys(previous, {"tables", "db_tables", "entities"})
        or []
    )


def get_goal(state_get) -> str:
    return str(
        state_get("develop_goal", "")
        or state_get("development_request", "")
        or "Implement the next iteration safely"
    )


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []

# pm stack 결과를 dev 도메인 별로 나눔
def _stack_item_domain(item: dict[str, Any]) -> str:
    return str(item.get("domain") or item.get("dom") or "").lower()


def _stack_item_package(item: dict[str, Any]) -> str:
    return str(item.get("pkg") or item.get("package") or item.get("package_name") or item.get("name") or "").strip()


def approved_stack_for_domain(
    state_get,
    *,
    domain: str,
    language: str = "",
    framework: str = "",
) -> dict[str, Any]:
    previous = _previous_result(state_get)
    pm_bundle = state_get("pm_bundle", {}) or previous.get("pm_bundle", {}) or {}
    pm_data = pm_bundle.get("data", {}) if isinstance(pm_bundle, dict) else {}
    stack_planner = state_get("stack_planner_output", {}) or previous.get("stack_planner_output", {}) or {}
    
    # 1. 원본 데이터 소스 수집
    raw_items = (
        _as_list(state_get("approved_stack", []))
        or _as_list(state_get("tech_stacks", []))
        or _as_list(pm_data.get("tech_stacks"))
        or _as_list(pm_data.get("stacks"))
        or _as_list(stack_planner.get("m"))
        or _as_list(stack_planner.get("stack_mapping"))
    )
    
    # 2. 필터링 완화: APPROVED 뿐만 아니라 PENDING_CRAWL 등도 포함 (REQ-DEV-002)
    # 기술 스택 정보가 하나도 없는 것보다, 분석 중인 정보를 주는 것이 LLM에게 더 유익함
    valid_items = [
        item for item in raw_items
        if isinstance(item, dict) and item.get("status", "APPROVED").upper() in {"APPROVED", "PENDING_CRAWL", "SELECTED"}
    ]
    
    # 3. 도메인 별칭 확장 (DB는 Backend에 포함)
    aliases = {
        "uiux": {"uiux", "ui/ux", "design", "ux", ""},
        "backend": {"backend", "be", "server", "api", "db", "database", ""},
        "frontend": {"frontend", "fe", "client", "ui", ""},
    }.get(domain, {domain, ""})
    
    domain_items = [
        item for item in valid_items
        if _stack_item_domain(item) in aliases
    ]
    
    packages = [_stack_item_package(item) for item in domain_items if _stack_item_package(item)]
    
    return {
        "domain": domain,
        "language": language,
        "framework": framework,
        "source": "approved_stack|tech_stacks|pm_bundle.data.tech_stacks|stack_planner_output.stack_mapping",
        "items": domain_items,
        "packages": list(dict.fromkeys(packages)),
    }


def generation_policy() -> dict[str, bool]:
    return {
        "no_dummy_code": True,
        "no_placeholder_business_logic": True,
        "no_mock_business_logic": True,
        "no_unapproved_stack": True,
        "no_extra_api": True,
        "no_missing_sa_api": True,
        "preserve_request_response_fields": True,
        "preserve_pm_requirement_trace": True,
    }


def placeholder_policy_findings(files: list[tuple[str, str]], *, label: str = "Generated output") -> list[str]:
    combined = "\n".join(content for _, content in files)
    # [수정] HTML input의 placeholder 속성이나 더미 이미지가 미완성 코드로 오인되는 과잉 규제를 막기 위해 금지어를 비웁니다.
    # 기존 금지어: "mock business logic", "dummy", "placeholder", "wire this service into real domain logic"
    blocked_terms = [
        "TODO placeholder",
        "mock business logic",
        "dummy logic",
        "wire this service into real domain logic",
    ]
    findings: list[str] = []
    for term in blocked_terms:
        pattern = r"\b" + re.escape(term.lower()) + r"\b"
        if re.search(pattern, combined.lower()):
            findings.append(f"{label} contains forbidden placeholder marker: {term}")
    return findings


def policy_enforcement_result(*, findings: list[str] | None = None) -> dict[str, Any]:
    findings = findings or []
    return {
        "status": "passed" if not findings else "failed",
        "generation_policy": generation_policy(),
        "findings": findings,
    }


def target_agent_for_domain(domain: str) -> str:
    return {
        "uiux": "UIUXAgent",
        "backend": "BackendAgent",
        "frontend": "FrontendAgent",
    }.get(domain, f"{domain.title()}Agent")


def build_dev_task(
    *,
    domain: str,
    goal: str,
    feature_id: str,
    run_id: str,
    attempt: int,
    task_spec: dict[str, Any],
    sa_bundle: dict[str, Any],
    apis: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    components: list[dict[str, Any]],
    requirements: list[dict[str, Any]],
    project_rag_context: dict[str, Any],
    artifact_rag_context: dict[str, Any],
    integration_feedback: dict[str, Any],
) -> dict[str, Any]:
    """Build the explicit DEV_TASK payload passed from Main Agent to a domain agent."""
    normalized_feature_id = feature_id or "GENERAL"
    task_id = f"task_{normalized_feature_id}_{domain.upper()}_{attempt:02d}"
    approved_stack = task_spec.get("approved_stack") or {}
    stack_packages = approved_stack.get("packages", []) if isinstance(approved_stack, dict) else []
    constraints = task_spec.get("generation_policy") or generation_policy()
    rework_instruction = task_spec.get("rework_instruction") or {}
    focus = [str(item) for item in _as_list(task_spec.get("focus")) if str(item or "").strip()]
    acceptance_criteria = [
        str(item)
        for item in _as_list(task_spec.get("acceptance_criteria"))
        if str(item or "").strip()
    ]
    target_components = [
        str(item)
        for item in _as_list(task_spec.get("target_components"))
        if str(item or "").strip()
    ]
    instruction_parts = [
        f"Execute {domain} work for feature {normalized_feature_id}.",
        "Use DEV_TASK.context contracts as the source of truth.",
        "Do not reinterpret or invent PM/SA contracts.",
        "Use only approved_stacks and obey constraints.",
    ]
    if rework_instruction.get("active"):
        instruction_parts.append("Resolve rework_instruction findings before adding new work.")
    if focus:
        instruction_parts.append("Focus: " + "; ".join(focus))

    payload = {
        "task_info": {
            "task_id": task_id,
            "target_agent": target_agent_for_domain(domain),
            "domain": domain,
            "feature_id": normalized_feature_id,
            "run_id": run_id,
            "attempt": attempt,
            "source": "develop_main_agent",
        },
        "context": {
            "approved_stacks": list(dict.fromkeys(str(item) for item in stack_packages if str(item or "").strip())),
            "approved_stack": approved_stack,
            "sa_bundle": sa_bundle,
            "target_api_specs": apis,
            "target_table_specs": tables,
            "target_components": target_components or [
                component_name(component)
                for component in components
                if isinstance(component, dict) and component_name(component)
            ],
            "component_specs": components,
            "requirements": requirements,
            "project_rag_context": project_rag_context,
            "artifact_rag_context": artifact_rag_context,
            "integration_feedback": integration_feedback,
            "rework_instruction": rework_instruction,
        },
        "instruction": " ".join(instruction_parts),
        "acceptance_criteria": acceptance_criteria,
        "constraints": constraints,
    }
    return DevTask.model_validate(payload).model_dump()


def normalize_api_contract(api: dict[str, Any]) -> dict[str, Any]:
    """Normalize API contract into a standard format for comparison and generation."""
    endpoint = str(api.get("endpoint") or api.get("ep") or "").strip()
    match = re.match(r"^(GET|POST|PUT|PATCH|DELETE)\s+(.+)$", endpoint, re.I)
    if match:
        method = match.group(1).upper()
        path = match.group(2).strip()
    else:
        method = str(api.get("method") or "POST").upper()
        path = endpoint or "/"

    if not path.startswith("/"):
        path = f"/{path}"

    return {
        "method": method,
        "path": path.rstrip("/") or "/",
        "full": f"{method} {path.rstrip('/') or '/'}",
        "operation_id": api.get("operation_id") or api.get("id") or "",
        "request_schema": api.get("request_schema") or api.get("req") or {},
        "response_schema": api.get("response_schema") or api.get("res") or {},
    }


def slugify(value: str) -> str:
    lowered = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "").strip().lower())
    return lowered.strip("-") or "work-item"


def requirement_id(req: dict[str, Any], index: int) -> str:
    return str(req.get("REQ_ID") or req.get("feature_id") or req.get("id") or f"REQ_{index:03d}")


def requirement_desc(req: dict[str, Any]) -> str:
    return str(req.get("description") or req.get("desc") or "Unnamed requirement")


def component_name(component: dict[str, Any]) -> str:
    return str(
        component.get("component_name")
        or component.get("name")
        or component.get("nm")
        or "UnknownComponent"
    )


def component_rtms(component: dict[str, Any]) -> list[str]:
    raw = component.get("rtms") or component.get("rt") or []
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    return []


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def requirement_index(requirements: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for idx, req in enumerate(requirements, start=1):
        indexed[requirement_id(req, idx)] = req
    return indexed


def requirement_ids_for_components(
    requirements: list[dict[str, Any]],
    components: list[dict[str, Any]],
    component_names: list[str],
) -> list[str]:
    known_ids = set(requirement_index(requirements).keys())
    requested = set(component_names)
    matched: list[str] = []
    for component in components:
        if component_name(component) not in requested:
            continue
        for req_id in component_rtms(component):
            if req_id in known_ids and req_id not in matched:
                matched.append(req_id)
    return matched


def fallback_requirement_ids(requirements: list[dict[str, Any]], limit: int = 8) -> list[str]:
    return [
        requirement_id(req, idx)
        for idx, req in enumerate(requirements[:limit], start=1)
    ]


# ── 노드 공통 헬퍼 (각 에이전트 파일에서 중복 정의하지 않도록) ─────────────

def api_endpoint(api: dict[str, Any]) -> str:
    return str(api.get("endpoint") or api.get("ep") or api.get("path") or "").strip()


def table_name(table: dict[str, Any]) -> str:
    return str(table.get("table_name") or table.get("name") or table.get("nm") or "").strip()


def column_names(table: dict[str, Any]) -> list[str]:
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


def artifact_items(ctx: Any, key: str) -> list[dict[str, Any]]:
    direct = _as_list(ctx.sget(key, []))
    artifact_context = ctx.sget("artifact_rag_context", {}) or {}
    nested = _as_list(artifact_context.get(key))
    return [item for item in [*direct, *nested] if isinstance(item, dict)]


def topology_queue(
    *,
    apis: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    components: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    order = 1
    for t in tables:
        name = table_name(t)
        if not name:
            continue
        queue.append({"order": order, "kind": "table", "name": name, "source": "SA DB contract", "depends_on": []})
        order += 1
    for c in components:
        name = component_name(c)
        if not name:
            continue
        queue.append({
            "order": order,
            "kind": "component",
            "name": name,
            "source": "SA component contract",
            "depends_on": [table_name(t) for t in tables if table_name(t)],
        })
        order += 1
    for a in apis:
        endpoint = api_endpoint(a)
        if not endpoint:
            continue
        queue.append({
            "order": order,
            "kind": "api",
            "name": endpoint,
            "source": "SA API contract",
            "depends_on": [
                *[table_name(t) for t in tables if table_name(t)],
                *[component_name(c) for c in components if component_name(c)],
            ],
        })
        order += 1
    return queue


def slug(value: str, fallback: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value or "")).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned or fallback


def looks_like_endpoint(value: Any) -> bool:
    text = str(value or "").strip()
    upper = text.upper()
    return (
        upper.startswith(("GET ", "POST ", "PUT ", "PATCH ", "DELETE "))
        or text.startswith("/api/")
        or text.startswith("/")
    )
