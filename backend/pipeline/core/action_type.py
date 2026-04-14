"""분석 action_type 공용 정규화 헬퍼."""

from __future__ import annotations

ANALYSIS_ACTION_TYPES = {"CREATE", "UPDATE", "REVERSE_ENGINEER"}


def normalize_action_type(action_type: str) -> str:
    normalized = (action_type or "CREATE").strip().upper()
    return normalized if normalized in ANALYSIS_ACTION_TYPES else "CREATE"