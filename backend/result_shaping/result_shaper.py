"""
Result Shaping 계층 (REQ-003)
파이프라인 raw 결과물을 JSON 직렬화 가능한 구조로 정형화한다.
민감정보 제거, pm_overview/sa_overview 스키마 기반 생성.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from result_shaping.sa_artifact_compiler import compile_sa_artifacts
from pipeline.core.utils import to_serializable


# ─── 스키마 ───────────────────────────────────────────────

class PMOverview(BaseModel):
    status: str | None = None
    summary: str | None = None
    requirement_count: int = 0
    risks: list[str] = Field(default_factory=list)


class SAOverview(BaseModel):
    feasibility: dict = Field(default_factory=dict)
    critical_gaps: list[str] = Field(default_factory=list)
    skipped_phases: list[str] = Field(default_factory=list)


class ProjectOverview(BaseModel):
    status: str | None = None
    project_name: str | None = None
    action_type: str | None = None
    summary: str | None = None
    summary_source: str = "none"
    requirement_count: int = 0
    priority_counts: dict[str, int] = Field(default_factory=dict)
    risks: list[str] = Field(default_factory=list)
    feasibility_status: str | None = None
    complexity_score: int | float | None = None
    critical_gap_count: int = 0
    skipped_phases: list[str] = Field(default_factory=list)
    architecture_pattern: str | None = None
    layer_distribution: dict[str, int] = Field(default_factory=dict)
    container_summary: dict[str, int] = Field(default_factory=dict)
    data_flags: dict[str, bool] = Field(default_factory=dict)
    next_actions: list[str] = Field(default_factory=list)
    usage_summary: dict[str, Any] = Field(default_factory=dict) # New field for cost/token


# ─── 제외 키 ──────────────────────────────────────────────

_EXCLUDED_KEYS: frozenset[str] = frozenset({
    "api_key",
    "rtm_matrix",
    # PM Topology 탭 제거에 맞춰 최종 결과에서 semantic_graph는 노출하지 않는다.
    "semantic_graph",
})


# ─── Public API ───────────────────────────────────────────

def _collect_skipped_phases(sanitized: dict[str, Any]) -> list[str]:
    return [
        phase
        for phase in ("system_scan", "sa_phase2")
        if isinstance(sanitized.get(phase), dict)
        and sanitized.get(phase, {}).get("status") == "Skipped"
    ]


def _build_pm_overview(
    metadata: dict,
    context_spec: dict,
    requirements_rtm: list,
) -> dict:
    return PMOverview(
        status=metadata.get("status"),
        summary=context_spec.get("summary"),
        requirement_count=len(requirements_rtm),
        risks=context_spec.get("risk_factors", []),
    ).model_dump()


def _build_sa_overview(sa_advisor: dict, skipped_phases: list[str]) -> dict:
    return SAOverview(
        feasibility={"status": sa_advisor.get("status", "Pass")},
        critical_gaps=sa_advisor.get("gaps", []),
        skipped_phases=skipped_phases,
    ).model_dump()


def _resolve_summary(context_spec: dict, sa_output: dict) -> tuple[str | None, str]:
    if context_spec.get("summary"):
        return context_spec.get("summary"), "context_spec"
    if sa_output.get("summary"):
        return sa_output.get("summary"), "sa_output"
    return None, "none"


def _build_priority_counts(requirements_rtm: list) -> dict[str, int]:
    return {
        "must": sum(1 for r in requirements_rtm if (r.get("priority") or "") == "Must-have"),
        "should": sum(1 for r in requirements_rtm if (r.get("priority") or "") == "Should-have"),
        "could": sum(1 for r in requirements_rtm if (r.get("priority") or "") == "Could-have"),
    }


def _build_layer_distribution(components: list) -> dict[str, int]:
    layer_distribution: dict[str, int] = {}
    for c in components or []:
        layer = str(c.get("domain") or "Unknown")
        layer_distribution[layer] = layer_distribution.get(layer, 0) + 1
    return layer_distribution


def _build_data_flags(
    requirements_rtm: list,
    sanitized: dict[str, Any],
) -> dict[str, bool]:
    return {
        "has_rtm": len(requirements_rtm) > 0,
        "has_phase1_scan": isinstance(sanitized.get("system_scan"), dict),
        "has_sa_artifacts": isinstance(sanitized.get("sa_artifacts"), dict),
    }


def _compute_next_actions(data_flags: dict[str, bool], sa_status: str, container_summary: dict) -> list[str]:
    next_actions: list[str] = []
    if not data_flags["has_rtm"]:
        next_actions.append("요구사항(RTM) 또는 추적 가능한 유저 스토리를 보강하세요.")
    if sa_status != "Pass":
        next_actions.append("타당성 판정 근거(reasons/alternatives)를 검토해 리스크를 먼저 해소하세요.")
    if (container_summary.get("external_count") or 0) > 0:
        next_actions.append("외부 연동 구간의 인증/재시도/관측성 정책을 계약 수준에서 명시하세요.")
    if not next_actions:
        next_actions.append("핵심 경로 기준으로 통합 테스트를 작성해 변경 회귀를 방지하세요.")
    return next_actions


def _build_project_overview(
    *,
    metadata: dict,
    summary_text: str | None,
    summary_source: str,
    requirements_rtm: list,
    priority_counts: dict[str, int],
    context_spec: dict,
    sa_advisor: dict,
    components: list,
    skipped_phases: list[str],
    layer_distribution: dict[str, int],
    container_summary: dict,
    data_flags: dict[str, bool],
    next_actions: list[str],
    usage_summary: dict[str, Any],
) -> dict:
    return ProjectOverview(
        status=metadata.get("status"),
        project_name=metadata.get("project_name"),
        action_type=metadata.get("action_type"),
        summary=summary_text,
        summary_source=summary_source,
        requirement_count=len(requirements_rtm),
        priority_counts=priority_counts,
        risks=context_spec.get("risk_factors", []),
        feasibility_status=sa_advisor.get("status"),
        complexity_score=sa_advisor.get("complexity_score"),
        critical_gap_count=len(sa_advisor.get("gaps", []) or []),
        skipped_phases=skipped_phases,
        architecture_pattern=sa_advisor.get("pattern") or "Clean Architecture",
        layer_distribution=layer_distribution,
        container_summary={
            "component_count": int(container_summary.get("component_count") or 0),
            "external_count": int(container_summary.get("external_count") or 0),
            "connection_count": int(container_summary.get("connection_count") or 0),
        },
        data_flags=data_flags,
        next_actions=next_actions[:3],
        usage_summary=usage_summary,
    ).model_dump()

def shape_result(raw_result: dict) -> dict:
    """LangGraph raw 결과 → JSON 직렬화 가능한 정형 결과.

    - EXCLUDED_KEYS 필드 제거
    - pm_overview / sa_overview / project_overview 스키마 기반 생성
    """
    sanitized: dict[str, Any] = {}
    for key, value in raw_result.items():
        if key in _EXCLUDED_KEYS:
            continue
        sanitized[key] = to_serializable(value)

    requirements_rtm: list = sanitized.get("requirements_rtm") or []
    context_spec: dict = sanitized.get("context_spec") or {}
    metadata: dict = sanitized.get("metadata") or {}
    
    sa_advisor = sanitized.get("sa_advisor_output") or {}
    sa_sched = sanitized.get("component_scheduler_output") or {}
    sa_unified = sanitized.get("sa_unified_modeler_output") or {}
    sa_output_raw = sanitized.get("sa_output") or {}
    sa_data = sa_output_raw.get("data") or {}
    pm_bundle = sanitized.get("pm_bundle") or {}
    pm_data = pm_bundle.get("data") or {}
    merged_project = sanitized.get("merged_project") or {}
    merged_plan = merged_project.get("plan") or {}

    # ── Modular Data Aliasing (Prioritize pre-expanded sa_output) ──
    # 0. PM Stacks
    sanitized["tech_stacks"] = pm_data.get("stacks") or sanitized.get("stacks") or []
    
    extracted_rtm = (
        merged_plan.get("requirements_rtm") or 
        pm_data.get("rtm") or 
        sanitized.get("requirements_rtm") or 
        []
    )
    sanitized["requirements_rtm"] = extracted_rtm
    requirements_rtm: list = extracted_rtm
    
    context_spec: dict = sanitized.get("context_spec") or merged_plan.get("context_spec") or {}

    # 1. APIs (sa_output.data.apis > sa_unified.apis)
    raw_apis = sa_data.get("apis") or sa_unified.get("apis") or []
    expanded_apis = []
    for a in raw_apis:
        # 이미 확장된 객체인지 확인 (sa_advisor가 처리한 경우)
        if "endpoint" in a:
            expanded_apis.append(a)
        else:
            expanded_apis.append({
                "endpoint": a.get("ep", "GET /"),
                "request_schema": a.get("rq") or a.get("req", {}),
                "response_schema": a.get("rs") or a.get("res", {}),
                "description": a.get("description", "")
            })
    sanitized["apis"] = expanded_apis

    # 2. Tables (sa_output.data.tables > sa_unified.tables)
    raw_tables = sa_data.get("tables") or sa_unified.get("tables") or []
    expanded_tables = []
    for t in raw_tables:
        if "table_name" in t:
            expanded_tables.append(t)
        else:
            # 수동 확장 (폴백)
            cols_str = t.get("cl") or t.get("cols", "")
            columns = []
            if isinstance(cols_str, str):
                for col_def in (cols_str.split(",") if cols_str else []):
                    parts = col_def.split(":")
                    columns.append({
                        "name": parts[0] if len(parts) > 0 else "unknown",
                        "type": parts[1] if len(parts) > 1 else "string",
                        "constraints": parts[2] if len(parts) > 2 else ""
                    })
            else:
                columns = cols_str # 이미 리스트인 경우
            expanded_tables.append({"table_name": t.get("nm") or t.get("name", "Unknown"), "columns": columns})
    sanitized["tables"] = expanded_tables

    # 3. Components
    raw_components = sa_data.get("components") or sa_sched.get("components") or []
    expanded_components = []
    for c in raw_components:
        if "component_name" in c:
            expanded_components.append(c)
        elif "name" in c:
            # UI가 name과 component_name 둘 다 쓸 수 있으므로 alias 생성
            c_copy = dict(c)
            if "nm" in c_copy and "name" not in c_copy: c_copy["name"] = c_copy["nm"]
            if "dm" in c_copy and "domain" not in c_copy: c_copy["domain"] = c_copy["dm"]
            if "rl" in c_copy and "role" not in c_copy: c_copy["role"] = c_copy["rl"]
            expanded_components.append(c_copy)
        else:
            expanded_components.append(c)
    
    sanitized["components"] = expanded_components
    sanitized["gaps"] = sa_advisor.get("gaps", [])
    sanitized["sa_output"] = sa_output_raw # UI 탭 활성화(hasSaData)를 위해 필수

    skipped_phases = _collect_skipped_phases(sanitized)

    skipped_phases = _collect_skipped_phases(sanitized)

    sanitized["pm_overview"] = _build_pm_overview(
        metadata=metadata,
        context_spec=context_spec,
        requirements_rtm=requirements_rtm,
    )
    sanitized["sa_overview"] = _build_sa_overview(sa_advisor, skipped_phases)
    sanitized["sa_artifacts"] = compile_sa_artifacts(sanitized)

    summary_text, summary_source = _resolve_summary(context_spec, sa_advisor)
    priority_counts = _build_priority_counts(requirements_rtm)
    layer_distribution = _build_layer_distribution(expanded_components)

    # ── UI Dashboard Mapping (REQ-UI-001) ──
    # 1. Metrics
    sa_status = sa_advisor.get("status", "UNKNOWN")
    sanitized["metrics"] = {
        "performance": 95 if sa_status == "PASS" else (80 if sa_status == "WARNING" else 40),
        "stability": 90 if sa_status == "PASS" else (75 if sa_status == "WARNING" else 30),
        "integrity": sa_status
    }

    # 2. Recommendations
    sanitized["recommendations"] = sa_advisor.get("recommendations", [])

    # 3. Analysis Summary
    sanitized["analysis"] = {
        "summary": summary_text or "분석 결과를 생성할 수 없습니다.",
        "source": summary_source
    }

    container_spec = (sanitized.get("sa_artifacts") or {}).get("container_diagram_spec") or {}
    container_summary = container_spec.get("summary") or {}

    data_flags = _build_data_flags(requirements_rtm, sanitized)
    next_actions = _compute_next_actions(data_flags, sa_advisor.get("status", "Pass"), container_summary)

    usage_summary = {
        "total_tokens": sum(log.get("total", 0) for log in (raw_result.get("accumulated_usage") or [])),
        "total_cost": raw_result.get("accumulated_cost", 0.0),
        "input_tokens": sum(log.get("input", 0) for log in (raw_result.get("accumulated_usage") or [])),
        "output_tokens": sum(log.get("output", 0) for log in (raw_result.get("accumulated_usage") or [])),
    }

    sanitized["project_overview"] = _build_project_overview(
        metadata=metadata,
        summary_text=summary_text,
        summary_source=summary_source,
        requirements_rtm=requirements_rtm,
        priority_counts=priority_counts,
        context_spec=context_spec,
        sa_advisor=sa_advisor,
        components=expanded_components,
        skipped_phases=skipped_phases,
        layer_distribution=layer_distribution,
        container_summary=container_summary,
        data_flags=data_flags,
        next_actions=next_actions,
        usage_summary=usage_summary,
    )

    return sanitized
