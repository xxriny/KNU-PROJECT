from __future__ import annotations

import json

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.core.utils import call_structured
from pipeline.domain.dev.nodes._shared import (
    component_name,
    dedupe,
    fallback_requirement_ids,
    get_apis,
    get_components,
    get_goal,
    get_requirements,
    get_tables,
    requirement_ids_for_components,
    requirement_desc,
    requirement_id,
    slugify,
)
from pipeline.domain.dev.schemas import MainAgentPlanningOutput
from pipeline.domain.pm.nodes.pm_db import _get_collection as _get_artifact_collection
from pipeline.domain.rag.nodes.project_db import query_project_code


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


def _load_project_rag_context(goal: str, source_session_id: str, requirements: list[dict], components: list[dict]) -> dict:
    query_text = _build_project_query(goal, requirements, components)
    try:
        chunks = query_project_code(query_text, session_id=source_session_id or None, n_results=6)
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
                "content_preview": str(item.get("content_text", ""))[:280],
            }
            for item in chunks
        ],
    }


def _safe_parse_document(value: str):
    try:
        return json.loads(value)
    except Exception:
        return value


def _load_artifact_rag_context(source_session_id: str) -> dict:
    if not source_session_id:
        return {
            "session_id": "",
            "artifact_count": 0,
            "artifacts": [],
        }

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
        preview = parsed if isinstance(parsed, (dict, list)) else str(parsed)[:400]
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
        "artifacts": artifacts[:8],
    }


SYSTEM_PROMPT = """# 역할: Develop Main Agent Planner
## 목표
- project RAG와 artifact RAG를 읽고 이번 개발 사이클의 실행 계획을 결정한다.
- UI/UX, backend, frontend 세 도메인에 작업을 분배한다.
- git-flow 기준 브랜치 전략을 만든다.

## 규칙
- 출력은 반드시 구조화된 JSON만 반환한다.
- selected_domains는 반드시 uiux, backend, frontend 중에서 선택한다.
- task_specs는 selected_domains에 포함된 도메인만 작성한다.
- target_components는 입력 컨텍스트에 있는 이름을 우선 사용한다.
- acceptance_criteria는 각 도메인별로 2개 이상 작성한다.
- thinking은 반드시 한국어 핵심 단어 3개 이내로 작성한다.
- goal은 사용자 요청을 구현 가능한 개발 목표 문장으로 재정리한다.
- branch_strategy.base_branch는 기본적으로 develop을 사용한다.
"""


def _truncate_preview(value, limit: int = 220) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    return text[:limit]


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
        for index, req in enumerate(requirements[:8], start=1)
    ]
    comp_lines = [f"- {component_name(comp)}" for comp in components[:10]]
    api_lines = [f"- {api.get('endpoint', '')}" for api in apis[:8] if api.get("endpoint")]
    table_lines = [f"- {table.get('table_name', '')}" for table in tables[:8] if table.get("table_name")]
    project_chunk_lines = [
        f"- {item.get('file_path', '')}::{item.get('func_name', '')} | sim={item.get('similarity', 0.0)} | {item.get('content_preview', '')}"
        for item in (project_rag_context.get("chunks", []) or [])[:6]
    ]
    artifact_lines = [
        f"- [{item.get('phase', '')}/{item.get('artifact_type', '')}] { _truncate_preview(item.get('preview', '')) }"
        for item in (artifact_rag_context.get("artifacts", []) or [])[:6]
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
    requirements = get_requirements(sget)
    components = get_components(sget)
    apis = get_apis(sget)
    tables = get_tables(sget)
    source_dir = sget("source_dir", "")
    source_session_id = _source_session_id(sget)

    component_names = [component_name(c) for c in components[:12]]
    uiux_requirement_ids = requirement_ids_for_components(requirements, components, component_names[:6])
    backend_requirement_ids = fallback_requirement_ids(requirements, limit=8)
    frontend_requirement_ids = requirement_ids_for_components(requirements, components, component_names[:6])
    if not uiux_requirement_ids:
        uiux_requirement_ids = fallback_requirement_ids(requirements, limit=6)
    if not frontend_requirement_ids:
        frontend_requirement_ids = fallback_requirement_ids(requirements, limit=6)
    project_rag_context = _load_project_rag_context(goal, source_session_id, requirements, components)
    project_rag_context.update({
        "source_dir": source_dir,
        "component_count": len(components),
        "api_count": len(apis),
        "table_count": len(tables),
        "components": component_names,
    })
    artifact_rag_context = _load_artifact_rag_context(source_session_id)
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
    })

    user_msg = _build_user_message(
        goal=goal,
        source_session_id=source_session_id,
        requirements=requirements,
        components=components,
        apis=apis,
        tables=tables,
        project_rag_context=project_rag_context,
        artifact_rag_context=artifact_rag_context,
    )

    fallback_task_specs = {
        "uiux": {
            "domain": "uiux",
            "goal": goal,
            "requirement_ids": uiux_requirement_ids,
            "focus": ["user flows", "screen hierarchy", "component naming consistency"],
            "inputs": ["artifact_rag_context", "project_rag_context", "requirements_rtm"],
            "target_components": dedupe(
                [name for name in component_names if "page" in name.lower() or "screen" in name.lower()] + component_names[:4]
            ),
            "acceptance_criteria": [
                "UI intent is explicit and implementable",
                "Shared components are named consistently",
            ],
        },
        "backend": {
            "domain": "backend",
            "goal": goal,
            "requirement_ids": backend_requirement_ids,
            "focus": ["API contract changes", "service/domain logic", "data model integrity"],
            "inputs": ["artifact_rag_context", "project_rag_context", "apis", "tables"],
            "target_components": dedupe(
                [f"api:{api.get('endpoint', '')}" for api in apis[:5]]
                + [f"table:{table.get('table_name', '')}" for table in tables[:5]]
            ),
            "acceptance_criteria": [
                "API and data changes are traceable to requirements",
                "Server-side responsibilities are explicit",
            ],
        },
        "frontend": {
            "domain": "frontend",
            "goal": goal,
            "requirement_ids": frontend_requirement_ids,
            "focus": ["UI implementation", "state wiring", "integration with backend contracts"],
            "inputs": ["artifact_rag_context", "project_rag_context", "components", "apis"],
            "target_components": dedupe(component_names[:6]),
            "acceptance_criteria": [
                "UI work maps to real components",
                "Frontend integration points are explicit",
            ],
        },
    }
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

    selected_domains = ["uiux", "backend", "frontend"]
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
        branch_strategy = out.branch_strategy.model_dump()
        task_specs = {
            item.domain: item.model_dump()
            for item in out.task_specs
            if item.domain in {"uiux", "backend", "frontend"}
        } or fallback_task_specs

        for domain in selected_domains:
            if domain not in task_specs and domain in fallback_task_specs:
                task_specs[domain] = fallback_task_specs[domain]
        if not branch_strategy.get("epic_branch"):
            branch_strategy["epic_branch"] = fallback_branch_strategy["epic_branch"]
        if not branch_strategy.get("domain_branches"):
            branch_strategy["domain_branches"] = fallback_branch_strategy["domain_branches"]
        if not branch_strategy.get("base_branch"):
            branch_strategy["base_branch"] = "develop"
        if not branch_strategy.get("gitflow"):
            branch_strategy["gitflow"] = "git-flow"

    return {
        "develop_goal": planned_goal,
        "project_rag_context": project_rag_context,
        "artifact_rag_context": artifact_rag_context,
        "develop_main_plan": {
            "goal": planned_goal,
            "selected_domains": selected_domains,
            "project_rag_context": project_rag_context,
            "artifact_rag_context": artifact_rag_context,
            "branch_strategy": branch_strategy,
            "task_specs": task_specs,
        },
        "uiux_task_spec": task_specs.get("uiux", fallback_task_specs["uiux"]),
        "backend_task_spec": task_specs.get("backend", fallback_task_specs["backend"]),
        "frontend_task_spec": task_specs.get("frontend", fallback_task_specs["frontend"]),
        "develop_loop_count": sget("develop_loop_count", 0),
        "source_session_id": source_session_id,
        "_thinking": thinking,
    }
