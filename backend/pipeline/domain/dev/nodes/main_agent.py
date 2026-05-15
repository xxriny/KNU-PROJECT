"""
PM/SA 결과와 개발 요청을 본 뒤 개발 전략 수립.
1. DOMAIN SELECT
2. 각 도메인 작업 분해
3. 각 도메인 AGENT에 넘길 TASK SPEC을 생성함.
"""
from __future__ import annotations

import json
import re

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.core.utils import call_structured
from pipeline.domain.dev.nodes._shared import (
    approved_stack_for_domain,
    build_dev_task,
    component_name,
    dedupe,
    fallback_requirement_ids,
    generation_policy,
    get_apis,
    get_components,
    get_goal,
    get_requirements,
    get_tables,
    normalize_sa_bundle,
    requirement_ids_for_components,
    requirement_desc,
    requirement_id,
    slugify,
)
from pipeline.domain.dev.schemas import MainAgentPlanningOutput

MAX_MAIN_AGENT_REQUIREMENTS = 8
MAX_MAIN_AGENT_COMPONENTS = 6
MAX_MAIN_AGENT_APIS = 4
MAX_MAIN_AGENT_TABLES = 4
MAX_MAIN_AGENT_PROJECT_HITS = 2
MAX_MAIN_AGENT_ARTIFACT_HITS = 2
MAX_MAIN_AGENT_PROJECT_PREVIEW_CHARS = 100
MAX_MAIN_AGENT_ARTIFACT_PREVIEW_CHARS = 180


def _source_session_id(state_get) -> str:
    previous = state_get("previous_result", {}) or {}
    return str(
        previous.get("run_id")
        or previous.get("metadata", {}).get("session_id")
        or state_get("source_session_id", "")
        or ""
    )


def _build_project_query(goal: str, requirements: list[dict], components: list[dict]) -> str:
    req_text = ", ".join(requirement_desc(req) for req in requirements[:4])
    comp_text = ", ".join(component_name(comp) for comp in components[:4])
    return "\n".join(
        part for part in [
            goal.strip(),
            req_text.strip(),
            comp_text.strip(),
        ] if part
    ) or "project structure and implementation context"


def _normalize_tokens(value: str) -> set[str]:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9\uac00-\ud7a3]+", " ", text)
    return {token for token in text.split() if token}


def _requirement_domain_keywords(domain: str) -> set[str]:
    return {
        "uiux": {"uiux", "ui", "ux", "screen", "page", "view", "layout", "design", "flow", "handoff", "accessibility"},
        "backend": {"backend", "api", "server", "db", "database", "schema", "table", "entity", "auth", "login", "token"},
        "frontend": {"frontend", "react", "vite", "component", "state", "route", "page", "screen", "ui", "ux"},
    }.get(domain, {domain})


def _requirement_trace_tokens(req: dict) -> set[str]:
    tokens = set()
    for key in ("REQ_ID", "feature_id", "id", "description", "desc", "title", "name", "summary"):
        value = req.get(key)
        if value:
            tokens.update(_normalize_tokens(str(value)))
    return tokens


def _component_trace_requirement_ids(components: list[dict]) -> set[str]:
    traced: set[str] = set()
    for component in components:
        traced.update(str(req_id) for req_id in component.get("rtms", []) if str(req_id).strip())
        traced.update(str(req_id) for req_id in component.get("rt", []) if str(req_id).strip())
    return traced


def _api_trace_requirement_ids(apis: list[dict]) -> set[str]:
    traced: set[str] = set()
    for api in apis:
        for key in ("rtms", "rt", "requirement_ids", "feature_ids"):
            raw = api.get(key)
            if isinstance(raw, list):
                traced.update(str(item) for item in raw if str(item).strip())
            elif isinstance(raw, str):
                traced.update(part.strip() for part in raw.split(",") if part.strip())
    return traced


def _table_trace_requirement_ids(tables: list[dict]) -> set[str]:
    traced: set[str] = set()
    for table in tables:
        for key in ("rtms", "rt", "requirement_ids", "feature_ids"):
            raw = table.get(key)
            if isinstance(raw, list):
                traced.update(str(item) for item in raw if str(item).strip())
            elif isinstance(raw, str):
                traced.update(part.strip() for part in raw.split(",") if part.strip())
    return traced


def _select_requirements_for_domain(
    *,
    domain: str,
    requirements: list[dict],
    components: list[dict],
    apis: list[dict],
    tables: list[dict],
) -> list[dict]:
    if not requirements:
        return []

    domain_keywords = _requirement_domain_keywords(domain)
    traced_ids = {
        *_component_trace_requirement_ids(components),
        *_api_trace_requirement_ids(apis),
        *_table_trace_requirement_ids(tables),
    }
    matched: list[dict] = []
    fallback: list[dict] = []

    for req in requirements:
        req_id = requirement_id(req, 0)
        tokens = _requirement_trace_tokens(req)
        text = " ".join(tokens)
        is_traced = req_id in traced_ids
        keyword_hit = bool(domain_keywords.intersection(tokens))
        if is_traced or keyword_hit:
            matched.append(req)
        elif text:
            fallback.append(req)

    if matched:
        return matched
    return fallback[: min(len(fallback), 4)]


def _merge_requirement_lists(*lists: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen: set[str] = set()
    for items in lists:
        for index, req in enumerate(items, start=1):
            req_id = requirement_id(req, index)
            if req_id in seen:
                continue
            seen.add(req_id)
            merged.append(req)
    return merged


def _load_project_rag_context(goal: str, source_session_id: str, requirements: list[dict], components: list[dict]) -> dict:
    query_text = _build_project_query(goal, requirements, components)
    try:
        from pipeline.domain.rag.nodes.project_db import query_project_code

        chunks = query_project_code(
            query_text,
            session_id=source_session_id or None,
            n_results=MAX_MAIN_AGENT_PROJECT_HITS,
        )
    except Exception as exc:
        return {
            "session_id": source_session_id,
            "query": query_text,
            "hits": 0,
            "chunks": [],
            "error": str(exc),
        }
    return {
        "session_id": source_session_id,
        "query": query_text,
        "hits": len(chunks),
        "chunks": [
            {
                "file_path": item.get("file_path", ""),
                "func_name": item.get("func_name", ""),
                "similarity": item.get("similarity", 0.0),
                "content_preview": str(item.get("content_text", ""))[:MAX_MAIN_AGENT_PROJECT_PREVIEW_CHARS],
            }
            for item in chunks
        ],
    }


def _safe_parse_document(value: str):
    try:
        return json.loads(value)
    except Exception:
        return value


def _smart_truncate(data: Any, limit: int = 500) -> str:
    """데이터 구조를 유지하면서 지능적으로 요약 (REQ-DEV-001)"""
    if not data:
        return ""
    
    if isinstance(data, list):
        # 리스트인 경우 상위 3개만 샘플링
        count = len(data)
        sample = data[:3]
        text = json.dumps(sample, ensure_ascii=False)
        if count > 3:
            text = text[:-1] + f", ...and {count-3} more items]"
        return text[:limit]
    
    if isinstance(data, dict):
        # 핵심 필드(summary, thinking, status)가 있다면 우선 추출
        vital_fields = {k: data[k] for k in ["summary", "th", "thinking", "status", "mode"] if k in data}
        if vital_fields:
            return json.dumps(vital_fields, ensure_ascii=False)
        
        # 일반 딕셔너리는 키 목록 위주로 요약
        keys = list(data.keys())
        if len(keys) > 5:
            summary = {k: data[k] for k in keys[:5]}
            text = json.dumps(summary, ensure_ascii=False)
            return text[:-1] + f", ...total {len(keys)} keys}}"
        
    text = str(data)
    return text[:limit] + ("..." if len(text) > limit else "")


def _load_artifact_rag_context(source_session_id: str) -> dict:
    if not source_session_id:
        return {
            "session_id": "",
            "artifact_count": 0,
            "artifacts": [],
        }

    from pipeline.domain.pm.nodes.pm_db import _get_collection as _get_artifact_collection

    collection = _get_artifact_collection()
    results = collection.get(where={"session_id": source_session_id})
    ids = results.get("ids", []) or []
    docs = results.get("documents", []) or []
    metas = results.get("metadatas", []) or []

    artifacts = []
    for idx in range(len(ids)):
        meta = metas[idx] if idx < len(metas) else {}
        doc = docs[idx] if idx < len(docs) else ""
        parsed = _safe_parse_document(doc)
        
        # 지능형 요약 적용
        preview = _smart_truncate(parsed, limit=MAX_MAIN_AGENT_ARTIFACT_PREVIEW_CHARS)
        
        artifacts.append({
            "chunk_id": ids[idx],
            "phase": meta.get("phase", ""),
            "artifact_type": meta.get("artifact_type", ""),
            "feature_id": meta.get("feature_id", ""),
            "preview": preview,
        })

    return {
        "session_id": source_session_id,
        "artifact_count": len(artifacts),
        "artifacts": artifacts[:MAX_MAIN_AGENT_ARTIFACT_HITS],
    }


SYSTEM_PROMPT = """
당신은 '개발 오케스트레이션 총괄자'입니다. PM/SA 산출물과 사용자 요청을 기준으로 이번 DEV 사이클의 실행 도메인과 작업 분배를 결정하십시오.

[1. 도메인 선택 (MANDATORY)]
- selected_domains는 uiux, backend, frontend 중 필요한 도메인만 포함하십시오.
- 전체 앱/fullstack/서비스 요청이면 uiux, backend, frontend를 모두 선택하십시오.
- backend/API/server/DB 요청이면 backend를 선택하십시오.
- frontend/screen/React/UI 요청이면 frontend를 선택하고, UIUX handoff가 필요하므로 uiux도 함께 선택하십시오.
- design/UIUX/user flow/screen design 요청이면 uiux를 선택하십시오.
- 선택하지 않은 도메인의 task_spec을 억지로 만들지 마십시오.

[2. PM/SA Trace 규칙]
- 모든 task_spec.requirement_ids는 PM requirement_id를 기준으로 작성하십시오.
- backend task는 SA apis/tables를 target_components에 반영하십시오.
- frontend task는 UIUX/SA component와 API dependency를 반영하십시오.
- uiux task는 화면, 사용자 흐름, 접근성, frontend handoff를 만들 수 있어야 합니다.

[3. Branch 전략]
- branch_strategy.base_branch 기본값은 develop입니다.
- domain_branches는 selected_domains에 포함된 도메인만 생성하십시오.
- branch명은 feature/{goal-slug}-{domain} 형태를 우선 사용하십시오.

[4. 출력 규격(JSON)]
{
  "thinking": "한국어 핵심어 5개 이내",
  "goal": "개발 목표",
  "selected_domains": ["uiux|backend|frontend"],
  "branch_strategy": {
    "gitflow": "git-flow",
    "base_branch": "develop",
    "epic_branch": "feature/...",
    "domain_branches": [{"domain": "backend", "branch": "feature/..."}]
  },
  "task_specs": [{
    "domain": "uiux|backend|frontend",
    "goal": "도메인 목표",
    "requirement_ids": ["REQ_ID"],
    "focus": ["핵심 작업"],
    "inputs": ["참조 산출물"],
    "target_components": ["대상"],
    "acceptance_criteria": ["검증 기준"]
  }]
}
"""


def _infer_selected_domains(ctx: NodeContext, goal: str) -> list[str]:
    request = " ".join([
        str(goal or ""),
        str(ctx.sget("development_request", "") or ""),
    ]).lower()
    explicit_backend = any(token in request for token in ["backend", "back-end", "api", "server", "database", "db", "백엔드", "서버", "데이터베이스"])
    explicit_frontend = any(token in request for token in ["frontend", "front-end", "react", "vite", "ui", "screen", "page", "프론트", "화면", "페이지"])
    explicit_uiux = any(token in request for token in ["uiux", "ui/ux", "ux", "design", "handoff", "디자인", "사용자 흐름", "화면 설계"])
    fullstack = any(token in request for token in ["fullstack", "full-stack", "전체 앱", "전체", "앱", "서비스"])

    selected: list[str] = []
    if fullstack:
        selected = ["uiux", "backend", "frontend"]
    else:
        if explicit_uiux:
            selected.append("uiux")
        if explicit_backend or ctx.sget("enable_backend_codegen", False):
            selected.append("backend")
        if explicit_frontend or ctx.sget("enable_frontend_codegen", False):
            if "uiux" not in selected:
                selected.append("uiux")
            selected.append("frontend")

    if not selected:
        selected = ["uiux", "backend", "frontend"]
    return [domain for domain in ["uiux", "backend", "frontend"] if domain in set(selected)]


def _filter_branch_strategy(branch_strategy: dict, selected_domains: list[str]) -> dict:
    selected = set(selected_domains)
    filtered = dict(branch_strategy or {})
    filtered["domain_branches"] = [
        item for item in (filtered.get("domain_branches") or [])
        if item.get("domain") in selected
    ]
    return filtered


def _truncate_preview(value, limit: int = 220) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    return text[:limit]


def _sa_bundle_context(sget) -> dict:
    bundle = normalize_sa_bundle(sget)
    data = bundle.get("data", {}) or {}
    return {
        "source": bundle.get("source", ""),
        "available": bool(bundle.get("available")),
        "phase": bundle.get("phase", "SA"),
        "version": bundle.get("version", ""),
        "bundle_id": bundle.get("bundle_id", ""),
        "keys": sorted(list(data.keys())) if isinstance(data, dict) else [],
        "counts": {
            "components": len(data.get("components", []) or []),
            "apis": len(data.get("apis", []) or []),
            "tables": len(data.get("tables", []) or []),
        },
        "preview": _truncate_preview(bundle, limit=900),
    }


def _current_feature_id(sget) -> str:
    request_feature = sget("development_request_feature", {}) or {}
    return str(
        sget("current_feature_id", "")
        or sget("feature_id", "")
        or request_feature.get("feature_id", "")
        or request_feature.get("id", "")
        or ""
    )


def _trace_ids(item: dict) -> set[str]:
    values: list[str] = []
    for key in ("feature_id", "id", "REQ_ID"):
        if item.get(key):
            values.append(str(item.get(key)))
    for key in ("rtms", "rt", "requirement_ids", "feature_ids"):
        raw = item.get(key)
        if isinstance(raw, list):
            values.extend(str(value) for value in raw)
        elif isinstance(raw, str):
            values.extend(part.strip() for part in raw.split(",") if part.strip())
    return set(values)


def _matches_feature(item: dict, current_feature_id: str) -> bool:
    return bool(current_feature_id and current_feature_id in _trace_ids(item))


def _filter_for_feature(items: list[dict], current_feature_id: str, *, keep_untraced: bool = False) -> list[dict]:
    if not current_feature_id:
        return items
    filtered = []
    for item in items:
        traces = _trace_ids(item)
        if current_feature_id in traces or (keep_untraced and not traces):
            filtered.append(item)
    return filtered


def _integration_feedback(sget) -> dict:
    integration = sget("integration_qa_result", {}) or {}
    global_sync = sget("global_fe_sync_result", {}) or {}
    domain_gates = {
        domain: sget(f"{domain}_domain_gate_result", {}) or {}
        for domain in ("uiux", "backend", "frontend")
    }
    domain_qa = {
        domain: sget(f"{domain}_qa_result", {}) or {}
        for domain in ("uiux", "backend", "frontend")
    }
    return {
        "active": bool(integration or global_sync or any(domain_gates.values()) or any(domain_qa.values())),
        "integration_qa": integration,
        "global_fe_sync": global_sync,
        "domain_gates": domain_gates,
        "domain_qa": domain_qa,
    }


def _integration_rework_targets(sget) -> list[str]:
    integration = sget("integration_qa_result", {}) or {}
    status = str(integration.get("status", "")).lower()
    if status not in {"rework_uiux", "rework_backend", "rework_frontend"}:
        return []
    targets = [
        str(target).lower()
        for target in (integration.get("rework_targets") or [])
        if str(target).lower() in {"uiux", "backend", "frontend"}
    ]
    if not targets and status.startswith("rework_"):
        targets = [status.replace("rework_", "", 1)]
    return [domain for domain in ["uiux", "backend", "frontend"] if domain in set(targets)]


def _rework_instruction_for(sget, domain: str) -> dict:
    integration = sget("integration_qa_result", {}) or {}
    global_sync = sget("global_fe_sync_result", {}) or {}
    domain_gate = sget(f"{domain}_domain_gate_result", {}) or {}
    domain_qa = sget(f"{domain}_qa_result", {}) or {}
    findings: list[str] = []
    actions: list[str] = []

    if domain in (integration.get("rework_targets") or []):
        findings.extend(str(item) for item in integration.get("findings", []) or [])
        actions.append("Resolve integration QA findings assigned to this domain.")
    if domain == "frontend" and str(global_sync.get("status", "")).lower() == "rework_frontend":
        findings.extend(str(item) for item in global_sync.get("sync_actions", []) or [])
        actions.append("Align frontend handoff/routes/API needs with UIUX artifact.")
    if domain == "uiux" and str(global_sync.get("status", "")).lower() == "rework_uiux":
        findings.extend(str(item) for item in global_sync.get("sync_actions", []) or [])
        actions.append("Revise UIUX artifact without changing SA API/DB contracts.")
    if str(domain_gate.get("status", "")).lower() in {"rework", "blocked"}:
        findings.extend(str(item) for item in domain_gate.get("blocking_findings", []) or [])
        actions.append("Address domain gate blocking findings.")
    if str(domain_qa.get("status", "")).lower() == "rework":
        findings.extend(str(item) for item in domain_qa.get("fixes_required", []) or [])
        actions.append("Address domain QA fixes.")

    return {
        "domain": domain,
        "active": bool(findings or actions),
        "source": {
            "integration_status": integration.get("status", ""),
            "global_fe_sync_status": global_sync.get("status", ""),
            "domain_gate_status": domain_gate.get("status", ""),
            "domain_qa_status": domain_qa.get("status", ""),
        },
        "findings": dedupe(findings),
        "actions": dedupe(actions),
    }


def _build_user_message(
    *,
    goal: str,
    source_session_id: str,
    requirements: list[dict],
    components: list[dict],
    apis: list[dict],
    tables: list[dict],
    project_rag_context: dict,
    artifact_rag_context: dict,
) -> str:
    req_lines = [
        f"- {requirement_id(req, index)}: {requirement_desc(req)}"
        for index, req in enumerate(requirements[:MAX_MAIN_AGENT_REQUIREMENTS], start=1)
    ]
    comp_lines = [f"- {component_name(comp)}" for comp in components[:MAX_MAIN_AGENT_COMPONENTS]]
    api_lines = [f"- {api.get('endpoint', '')}" for api in apis[:MAX_MAIN_AGENT_APIS] if api.get("endpoint")]
    table_lines = [f"- {table.get('table_name', '')}" for table in tables[:MAX_MAIN_AGENT_TABLES] if table.get("table_name")]
    project_chunk_lines = [
        f"- {item.get('file_path', '')}::{item.get('func_name', '')} | sim={item.get('similarity', 0.0)} | {item.get('content_preview', '')}"
        for item in (project_rag_context.get("chunks", []) or [])[:MAX_MAIN_AGENT_PROJECT_HITS]
    ]
    artifact_lines = [
        f"- [{item.get('phase', '')}/{item.get('artifact_type', '')}] { _truncate_preview(item.get('preview', '')) }"
        for item in (artifact_rag_context.get("artifacts", []) or [])[:MAX_MAIN_AGENT_ARTIFACT_HITS]
    ]
    return "\n".join([
        f"<goal>\n{goal}\n</goal>",
        f"<source_session_id>\n{source_session_id}\n</source_session_id>",
        "<requirements>",
        "\n".join(req_lines) or "- none",
        "</requirements>",
        "<components>",
        "\n".join(comp_lines) or "- none",
        "</components>",
        "<apis>",
        "\n".join(api_lines) or "- none",
        "</apis>",
        "<tables>",
        "\n".join(table_lines) or "- none",
        "</tables>",
        "<project_rag_hits>",
        "\n".join(project_chunk_lines) or "- none",
        "</project_rag_hits>",
        "<artifact_rag_hits>",
        "\n".join(artifact_lines) or "- none",
        "</artifact_rag_hits>",
    ])


@pipeline_node("develop_main_agent")
def develop_main_agent_node(ctx: NodeContext) -> dict:
    sget = ctx.sget
    api_key = ctx.api_key
    model = ctx.model
    goal = get_goal(sget)
    normalized_sa_bundle = normalize_sa_bundle(sget)
    current_feature_id = _current_feature_id(sget)
    requirements = get_requirements(sget)
    components = get_components(sget)
    apis = get_apis(sget)
    tables = get_tables(sget)
    requirements = _filter_for_feature(requirements, current_feature_id)
    components = _filter_for_feature(components, current_feature_id)
    apis = _filter_for_feature(apis, current_feature_id, keep_untraced=True)
    tables = _filter_for_feature(tables, current_feature_id, keep_untraced=True)
    source_dir = sget("source_dir", "")
    source_session_id = _source_session_id(sget)
    inferred_selected_domains = _infer_selected_domains(ctx, goal)
    integration_rework_targets = _integration_rework_targets(sget)
    if integration_rework_targets:
        inferred_selected_domains = integration_rework_targets

    selected_requirements_by_domain = {
        domain: _select_requirements_for_domain(
            domain=domain,
            requirements=requirements,
            components=components,
            apis=apis,
            tables=tables,
        )
        for domain in ("uiux", "backend", "frontend")
    }
    prompt_requirements = _merge_requirement_lists(
        *(selected_requirements_by_domain.get(domain, []) for domain in inferred_selected_domains),
    ) or requirements

    component_names = [component_name(c) for c in components[:12]]
    uiux_requirement_ids = [requirement_id(req, index) for index, req in enumerate(selected_requirements_by_domain["uiux"], start=1)]
    backend_requirement_ids = [requirement_id(req, index) for index, req in enumerate(selected_requirements_by_domain["backend"], start=1)]
    frontend_requirement_ids = [requirement_id(req, index) for index, req in enumerate(selected_requirements_by_domain["frontend"], start=1)]
    if not uiux_requirement_ids:
        uiux_requirement_ids = fallback_requirement_ids(requirements, limit=6)
    if not frontend_requirement_ids:
        frontend_requirement_ids = fallback_requirement_ids(requirements, limit=6)
    project_rag_context = _load_project_rag_context(goal, source_session_id, prompt_requirements, components)
    project_rag_context.update({
        "source_dir": source_dir,
        "component_count": len(components),
        "api_count": len(apis),
        "table_count": len(tables),
        "components": component_names,
    })
    artifact_rag_context = _load_artifact_rag_context(source_session_id)
    sa_bundle_context = _sa_bundle_context(sget)
    artifact_rag_context.update({
        "requirement_count": len(requirements),
        "requirements": [
            {"id": requirement_id(req, index), "description": requirement_desc(req)}
            for index, req in enumerate(requirements[:8], start=1)
        ],
        "project_overview": (sget("project_overview", {}) or {}),
        "pm_overview": (sget("pm_overview", {}) or {}),
        "sa_overview": (sget("sa_overview", {}) or {}),
        "sa_artifact_keys": sorted(list((sget("sa_artifacts", {}) or {}).keys())),
        "sa_bundle_context": sa_bundle_context,
    })

    integration_feedback = _integration_feedback(sget)
    approved_stacks = {
        domain: approved_stack_for_domain(sget, domain=domain)
        for domain in ("uiux", "backend", "frontend")
    }
    policy = generation_policy()

    fallback_task_specs = {
        "uiux": {
            "domain": "uiux",
            "goal": goal,
            "feature_id": current_feature_id,
            "current_feature_id": current_feature_id,
            "requirement_ids": uiux_requirement_ids,
            "focus": ["user flows", "screen hierarchy", "component naming consistency"],
            "inputs": ["artifact_rag_context", "project_rag_context", "sa_bundle", "requirements_rtm"],
            "target_components": dedupe(
                [name for name in component_names if "page" in name.lower() or "screen" in name.lower()] + component_names[:4]
            ),
            "acceptance_criteria": [
                "UI intent is explicit and implementable",
                "Shared components are named consistently",
            ],
            "rework_instruction": _rework_instruction_for(sget, "uiux"),
            "approved_stack": approved_stacks["uiux"],
            "generation_policy": policy,
        },
        "backend": {
            "domain": "backend",
            "goal": goal,
            "feature_id": current_feature_id,
            "current_feature_id": current_feature_id,
            "requirement_ids": backend_requirement_ids,
            "focus": ["API contract changes", "service/domain logic", "data model integrity"],
            "inputs": ["artifact_rag_context", "project_rag_context", "sa_bundle", "apis", "tables"],
            "target_components": dedupe(
                [f"api:{api.get('endpoint', '')}" for api in apis[:5]]
                + [f"table:{table.get('table_name', '')}" for table in tables[:5]]
            ),
            "acceptance_criteria": [
                "API and data changes are traceable to requirements",
                "Server-side responsibilities are explicit",
            ],
            "rework_instruction": _rework_instruction_for(sget, "backend"),
            "approved_stack": approved_stacks["backend"],
            "generation_policy": policy,
        },
        "frontend": {
            "domain": "frontend",
            "goal": goal,
            "feature_id": current_feature_id,
            "current_feature_id": current_feature_id,
            "requirement_ids": frontend_requirement_ids,
            "focus": ["UI implementation", "state wiring", "integration with backend contracts"],
            "inputs": ["artifact_rag_context", "project_rag_context", "sa_bundle", "components", "apis"],
            "target_components": dedupe(component_names[:6]),
            "acceptance_criteria": [
                "UI work maps to real components",
                "Frontend integration points are explicit",
            ],
            "rework_instruction": _rework_instruction_for(sget, "frontend"),
            "approved_stack": approved_stacks["frontend"],
            "generation_policy": policy,
        },
    }
    user_msg = _build_user_message(
        goal=goal,
        source_session_id=source_session_id,
        requirements=prompt_requirements,
        components=components,
        apis=apis,
        tables=tables,
        project_rag_context=project_rag_context,
        artifact_rag_context=artifact_rag_context,
    )

    # [DIAGNOSTIC] 로그 출력: 어떤 데이터가 토큰 폭발을 일으키는지 확인
    print(f"\n[DevelopMainAgent] Prompt Component Sizes (chars):")
    print(f" - goal: {len(goal)}")
    print(f" - requirements: {len(str(requirements))}")
    print(f" - components: {len(str(components))}")
    print(f" - apis: {len(str(apis))}")
    print(f" - tables: {len(str(tables))}")
    print(f" - project_rag: {len(str(project_rag_context))}")
    print(f" - artifact_rag: {len(str(artifact_rag_context))}")
    print(f" - TOTAL USER_MSG: {len(user_msg)}\n")

    fallback_branch_strategy = {
        "gitflow": "git-flow",
        "base_branch": "develop",
        "epic_branch": f"feature/{slugify(goal)[:40]}",
        "domain_branches": [
            {"domain": "uiux", "branch": f"feature/{slugify(goal)[:24]}-uiux"},
            {"domain": "backend", "branch": f"feature/{slugify(goal)[:24]}-backend"},
            {"domain": "frontend", "branch": f"feature/{slugify(goal)[:24]}-frontend"},
        ],
    }

    selected_domains = inferred_selected_domains
    planned_goal = goal
    branch_strategy = fallback_branch_strategy
    task_specs = fallback_task_specs
    thinking = "project-rag, artifact-rag, dispatch"

    if api_key:
        res = call_structured(
            api_key=api_key,
            model=model,
            schema=MainAgentPlanningOutput,
            system_prompt=SYSTEM_PROMPT,
            user_msg=user_msg,
            max_retries=3,
            temperature=0.1,
            compress_prompt=True,
        )
        out = res.parsed
        thinking = out.thinking or thinking
        planned_goal = out.goal or goal
        selected_domains = out.selected_domains or selected_domains
        selected_domains = [domain for domain in ["uiux", "backend", "frontend"] if domain in set(selected_domains)]
        if integration_rework_targets:
            selected_domains = integration_rework_targets
        if not integration_rework_targets and "frontend" in selected_domains and "uiux" not in selected_domains:
            selected_domains.insert(0, "uiux")
        branch_strategy = out.branch_strategy.model_dump()
        task_specs = {
            item.domain: item.model_dump()
            for item in out.task_specs
            if item.domain in {"uiux", "backend", "frontend"}
        } or fallback_task_specs

        for domain in selected_domains:
            if domain not in task_specs and domain in fallback_task_specs:
                task_specs[domain] = fallback_task_specs[domain]
            if domain in task_specs:
                task_specs[domain]["rework_instruction"] = _rework_instruction_for(sget, domain)
                task_specs[domain]["feature_id"] = task_specs[domain].get("feature_id") or current_feature_id
                task_specs[domain]["current_feature_id"] = task_specs[domain].get("current_feature_id") or current_feature_id
                task_specs[domain]["approved_stack"] = task_specs[domain].get("approved_stack") or approved_stacks[domain]
                task_specs[domain]["generation_policy"] = task_specs[domain].get("generation_policy") or policy
                if "sa_bundle" not in task_specs[domain].get("inputs", []):
                    task_specs[domain]["inputs"] = list(task_specs[domain].get("inputs", [])) + ["sa_bundle"]
        if not branch_strategy.get("epic_branch"):
            branch_strategy["epic_branch"] = fallback_branch_strategy["epic_branch"]
        if not branch_strategy.get("domain_branches"):
            branch_strategy["domain_branches"] = fallback_branch_strategy["domain_branches"]
        if not branch_strategy.get("base_branch"):
            branch_strategy["base_branch"] = "develop"
        if not branch_strategy.get("gitflow"):
            branch_strategy["gitflow"] = "git-flow"

    branch_strategy = _filter_branch_strategy(branch_strategy, selected_domains)
    dev_task_attempt = (
        int(sget("develop_integration_rework_count", 0) or 0) + 1
        if integration_rework_targets
        else int(sget("develop_integration_rework_count", 0) or 0) + 1
    )
    dev_tasks = {}
    for domain in selected_domains:
        if domain not in ("uiux", "backend", "frontend"):
            continue
        spec = task_specs.get(domain) or fallback_task_specs.get(domain, {})
        if not spec:
            continue

        task_payload = build_dev_task(
            domain=domain,
            goal=planned_goal,
            feature_id=current_feature_id,
            run_id=str(sget("run_id", "") or ""),
            attempt=dev_task_attempt,
            task_spec=spec,
            sa_bundle=normalized_sa_bundle,
            apis=apis,
            tables=tables,
            components=components,
            requirements=requirements,
            project_rag_context=project_rag_context,
            artifact_rag_context=artifact_rag_context,
            integration_feedback=integration_feedback,
        )
        spec["task_id"] = task_payload["task_info"]["task_id"]
        spec["target_agent"] = task_payload["task_info"]["target_agent"]
        spec["dev_task"] = task_payload
        dev_tasks[domain] = task_payload

    rework_instructions = {
        domain: (task_specs.get(domain) or {}).get("rework_instruction", _rework_instruction_for(sget, domain))
        for domain in selected_domains
        if domain in ("uiux", "backend", "frontend")
    }

    return {
        "develop_goal": planned_goal,
        "project_rag_context": project_rag_context,
        "artifact_rag_context": artifact_rag_context,
        "develop_main_plan": {
            "goal": planned_goal,
            "current_feature_id": current_feature_id,
            "selected_domains": selected_domains,
            "project_rag_context": project_rag_context,
            "artifact_rag_context": artifact_rag_context,
            "sa_bundle": normalized_sa_bundle,
            "sa_bundle_context": sa_bundle_context,
            "approved_stacks": approved_stacks,
            "generation_policy": policy,
            "dev_tasks": dev_tasks,
            "integration_feedback": integration_feedback,
            "rework_instructions": rework_instructions,
            "branch_strategy": branch_strategy,
            "task_specs": task_specs,
        },
        "sa_bundle": normalized_sa_bundle,
        "current_feature_id": current_feature_id,
        "integration_feedback": integration_feedback,
        "requirements_rtm": requirements,
        "components": components,
        "apis": apis,
        "tables": tables,
        "uiux_task_spec": task_specs.get("uiux") if "uiux" in selected_domains else {},
        "backend_task_spec": task_specs.get("backend") if "backend" in selected_domains else {},
        "frontend_task_spec": task_specs.get("frontend") if "frontend" in selected_domains else {},
        "develop_loop_count": sget("develop_loop_count", 0),
        "develop_integration_rework_count": (
            int(sget("develop_integration_rework_count", 0) or 0) + 1
            if integration_rework_targets
            else int(sget("develop_integration_rework_count", 0) or 0)
        ),
        "source_session_id": source_session_id,
        "_thinking": thinking,
    }
