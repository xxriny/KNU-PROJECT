"""
Result Shaping 계층 (REQ-003)
파이프라인 raw 결과물을 JSON 직렬화 가능한 구조로 정형화한다.
민감정보 제거, pm_overview/sa_overview 스키마 기반 생성.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


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


# ─── 제외 키 ──────────────────────────────────────────────

_EXCLUDED_KEYS: frozenset[str] = frozenset({"api_key", "rtm_matrix"})


# ─── Public API ───────────────────────────────────────────

def shape_result(raw_result: dict) -> dict:
    """LangGraph raw 결과 → JSON 직렬화 가능한 정형 결과.

    - EXCLUDED_KEYS 필드 제거
    - pm_overview / sa_overview 스키마 기반 생성
    """
    sanitized: dict[str, Any] = {}
    for key, value in raw_result.items():
        if key in _EXCLUDED_KEYS:
            continue
        sanitized[key] = deep_sanitize(value)

    requirements_rtm: list = sanitized.get("requirements_rtm") or []
    context_spec: dict = sanitized.get("context_spec") or {}
    metadata: dict = sanitized.get("metadata") or {}
    sa_phase2: dict = sanitized.get("sa_phase2") or {}
    sa_phase3: dict = sanitized.get("sa_phase3") or {}

    skipped_phases = [
        phase
        for phase in ("sa_phase1", "sa_phase2")
        if isinstance(sanitized.get(phase), dict)
        and sanitized.get(phase, {}).get("status") == "Skipped"
    ]

    sanitized["pm_overview"] = PMOverview(
        status=metadata.get("status"),
        summary=context_spec.get("summary"),
        requirement_count=len(requirements_rtm),
        risks=context_spec.get("risk_factors", []),
    ).model_dump()

    sanitized["sa_overview"] = SAOverview(
        feasibility=sa_phase3,
        critical_gaps=sa_phase2.get("gap_report", []),
        skipped_phases=skipped_phases,
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
