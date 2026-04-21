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


def _build_sa_overview(sa_phase2: dict, sa_phase3: dict, skipped_phases: list[str]) -> dict:
    return SAOverview(
        feasibility=sa_phase3,
        critical_gaps=sa_phase2.get("gap_report", []),
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


def _build_layer_distribution(sa_phase5: dict) -> dict[str, int]:
    layer_distribution: dict[str, int] = {}
    for req in sa_phase5.get("mapped_requirements", []) or []:
        layer = str(req.get("layer") or "Unknown")
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


def _compute_next_actions(data_flags: dict[str, bool], sa_phase3: dict, container_summary: dict) -> list[str]:
    next_actions: list[str] = []
    if not data_flags["has_rtm"]:
        next_actions.append("요구사항(RTM) 또는 추적 가능한 유저 스토리를 보강하세요.")
    if (sa_phase3.get("status") or "") != "Pass":
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
    sa_output: dict,
    sa_phase2: dict,
    sa_phase3: dict,
    sa_phase5: dict,
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
        feasibility_status=sa_phase3.get("status"),
        complexity_score=sa_phase3.get("complexity_score"),
        critical_gap_count=len(sa_phase2.get("gap_report", []) or []),
        skipped_phases=skipped_phases,
        architecture_pattern=sa_phase5.get("pattern") or "Clean Architecture",
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
        sanitized[key] = deep_sanitize(value)

    requirements_rtm: list = sanitized.get("requirements_rtm") or []
    context_spec: dict = sanitized.get("context_spec") or {}
    metadata: dict = sanitized.get("metadata") or {}
    # --- Compatibility Bridge: Map new modular SA nodes to existing phase-based logic ---
    sa_merge = sanitized.get("sa_merge_project_output") or {}
    sa_sched = sanitized.get("component_scheduler_output") or {}
    sa_model = sanitized.get("api_data_modeler_output") or {}
    sa_anal = sanitized.get("sa_analysis_output") or {}

    # Map sa_analysis to phase2 (Gaps) and phase3 (Feasibility)
    sa_phase2: dict = {
        "status": sa_anal.get("status"),
        "gap_report": sa_anal.get("gaps", [])
    }
    sa_phase3: dict = {
        "status": sa_anal.get("status", "Pass"),
        "reasons": [sa_anal.get("thinking", "")] if sa_anal.get("thinking") else []
    }
    # Map scheduler to phase5 (Components)
    sa_phase5: dict = {
        "components": sa_sched.get("components", []),
        "mapped_requirements": [
            {"REQ_ID": "REQ-101", "layer": c.get("domain"), "description": c.get("role")} # Dummy mapping for now
            for c in sa_sched.get("components", [])
        ]
    }
    # Map modeler to phase7 (Interfaces)
    sa_phase7: dict = {
        "interface_contracts": [
            {"contract_id": f"IF-{i}", "interface_name": a.get("endpoint"), "input_spec": str(a.get("request_schema")), "output_spec": str(a.get("response_schema"))}
            for i, a in enumerate(sa_model.get("apis", []))
        ]
    }
    
    sa_phase6: dict = {}
    sa_phase8: dict = {}
    sa_output: dict = sa_anal

    # Store in sanitized for compiler and UI compatibility
    sanitized["sa_phase2"] = sa_phase2
    sanitized["sa_phase3"] = sa_phase3
    sanitized["sa_phase5"] = sa_phase5
    sanitized["sa_phase6"] = sa_phase6
    sanitized["sa_phase7"] = sa_phase7
    sanitized["sa_phase8"] = sa_phase8
    sanitized["sa_output"] = sa_output

    skipped_phases = _collect_skipped_phases(sanitized)

    sanitized["pm_overview"] = _build_pm_overview(
        metadata=metadata,
        context_spec=context_spec,
        requirements_rtm=requirements_rtm,
    )
    sanitized["sa_overview"] = _build_sa_overview(sa_phase2, sa_phase3, skipped_phases)

    sanitized["sa_artifacts"] = compile_sa_artifacts(sanitized)

    summary_text, summary_source = _resolve_summary(context_spec, sa_output)
    priority_counts = _build_priority_counts(requirements_rtm)
    layer_distribution = _build_layer_distribution(sa_phase5)

    container_spec = (sanitized.get("sa_artifacts") or {}).get("container_diagram_spec") or {}
    container_summary = container_spec.get("summary") or {}

    data_flags = _build_data_flags(requirements_rtm, sanitized)
    next_actions = _compute_next_actions(data_flags, sa_phase3, container_summary)

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
        sa_output=sa_output,
        sa_phase2=sa_phase2,
        sa_phase3=sa_phase3,
        sa_phase5=sa_phase5,
        skipped_phases=skipped_phases,
        layer_distribution=layer_distribution,
        container_summary=container_summary,
        data_flags=data_flags,
        next_actions=next_actions,
        usage_summary=usage_summary,
    )

    return sanitized


def deep_sanitize(obj: Any) -> Any:
    """to_serializable의 하위 호환 별칭."""
    return to_serializable(obj)
