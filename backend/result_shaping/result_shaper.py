"""
Result Shaping 계층 (REQ-003)
파이프라인 raw 결과물을 JSON 직렬화 가능한 구조로 정형화한다.
민감정보 제거, pm_overview/sa_overview 스키마 기반 생성.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from result_shaping.sa_artifact_compiler import compile_sa_artifacts


# ─── 스키마 ───────────────────────────────────────────────

class PMOverview(BaseModel):
    status: str | None = None
    summary: str | None = None
    requirement_count: int = 0
    risks: list[str] = Field(default_factory=list)


class SAOverview(BaseModel):
    feasibility: dict = Field(default_factory=dict)
    critical_gaps: list[dict] = Field(default_factory=list)
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


# ─── 제외 키 ──────────────────────────────────────────────

_EXCLUDED_KEYS: frozenset[str] = frozenset({
    "api_key",
    "rtm_matrix",
    # PM Topology 탭 제거에 맞춰 최종 결과에서 semantic_graph는 노출하지 않는다.
    "semantic_graph",
})


# ─── Public API ───────────────────────────────────────────

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
    reverse_context: dict = sanitized.get("sa_reverse_context") or {}
    metadata: dict = sanitized.get("metadata") or {}
    sa_phase2: dict = sanitized.get("sa_phase2") or {}
    sa_phase3: dict = sanitized.get("sa_phase3") or {}
    sa_phase5: dict = sanitized.get("sa_phase5") or {}

    skipped_phases = [
        phase
        for phase in ("sa_phase1", "sa_phase2")
        if isinstance(sanitized.get(phase), dict)
        and sanitized.get(phase, {}).get("status") == "Skipped"
    ]

    sanitized["pm_overview"] = PMOverview(
        status=metadata.get("status"),
        summary=context_spec.get("summary") or reverse_context.get("summary"),
        requirement_count=len(requirements_rtm),
        risks=context_spec.get("risk_factors", []) or reverse_context.get("risk_factors", []),
    ).model_dump()

    sanitized["sa_overview"] = SAOverview(
        feasibility=sa_phase3,
        critical_gaps=sa_phase2.get("gap_report", []),
        skipped_phases=skipped_phases,
    ).model_dump()

    if not sanitized["pm_overview"].get("summary") and reverse_context.get("summary"):
        sanitized["pm_overview"]["summary"] = reverse_context.get("summary")

    sanitized["sa_artifacts"] = compile_sa_artifacts(sanitized)

    summary_text = context_spec.get("summary") or reverse_context.get("summary")
    if context_spec.get("summary"):
        summary_source = "context_spec"
    elif reverse_context.get("summary"):
        summary_source = "sa_reverse_context"
    else:
        summary_source = "none"

    priority_counts = {
        "must": sum(1 for r in requirements_rtm if (r.get("priority") or "") == "Must-have"),
        "should": sum(1 for r in requirements_rtm if (r.get("priority") or "") == "Should-have"),
        "could": sum(1 for r in requirements_rtm if (r.get("priority") or "") == "Could-have"),
    }

    layer_distribution: dict[str, int] = {}
    for req in sa_phase5.get("mapped_requirements", []) or []:
        layer = str(req.get("layer") or "Unknown")
        layer_distribution[layer] = layer_distribution.get(layer, 0) + 1

    container_spec = (sanitized.get("sa_artifacts") or {}).get("container_diagram_spec") or {}
    container_summary = container_spec.get("summary") or {}

    data_flags = {
        "has_rtm": len(requirements_rtm) > 0,
        "has_phase1_scan": isinstance(sanitized.get("sa_phase1"), dict),
        "has_reverse_context": bool(reverse_context.get("summary")),
        "has_sa_artifacts": isinstance(sanitized.get("sa_artifacts"), dict),
    }

    next_actions: list[str] = []
    if not data_flags["has_rtm"]:
        next_actions.append("요구사항(RTM) 또는 추적 가능한 유저 스토리를 보강하세요.")
    if (sa_phase3.get("status") or "") != "Pass":
        next_actions.append("타당성 판정 근거(reasons/alternatives)를 검토해 리스크를 먼저 해소하세요.")
    if (container_summary.get("external_count") or 0) > 0:
        next_actions.append("외부 연동 구간의 인증/재시도/관측성 정책을 계약 수준에서 명시하세요.")
    if not next_actions:
        next_actions.append("핵심 경로 기준으로 통합 테스트를 작성해 변경 회귀를 방지하세요.")

    sanitized["project_overview"] = ProjectOverview(
        status=metadata.get("status"),
        project_name=metadata.get("project_name"),
        action_type=metadata.get("action_type"),
        summary=summary_text,
        summary_source=summary_source,
        requirement_count=len(requirements_rtm),
        priority_counts=priority_counts,
        risks=context_spec.get("risk_factors", []) or reverse_context.get("risk_factors", []),
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
    ).model_dump()

    return sanitized


def deep_sanitize(obj: Any) -> Any:
    """Pydantic 모델, dict, list를 재귀적으로 JSON 직렬화 가능하게 변환."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if isinstance(obj, dict):
        return {k: deep_sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [deep_sanitize(item) for item in obj]
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    return str(obj)
