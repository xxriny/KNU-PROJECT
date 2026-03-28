"""
PipelineExecutor — 전송 프로토콜 독립적인 파이프라인 실행 서비스 (R-018)
REST와 WebSocket 핸들러 모두 이 클래스를 통해 파이프라인을 실행한다.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable

from result_shaping.result_shaper import shape_result


@dataclass
class PipelineResult:
    """파이프라인 실행 결과."""
    success: bool
    data: dict = field(default_factory=dict)
    error: str | None = None


def execute_pipeline(
    pipeline,
    state_payload: dict,
    pipeline_type: str,
    result_mutator: Callable[[dict], Any] | None = None,
) -> PipelineResult:
    """동기 파이프라인 실행 (REST용).

    invoke → error 검사 → shape_result → pipeline_type 설정 → mutator 적용.
    """
    try:
        result = pipeline.invoke(state_payload)
        if result.get("error"):
            return PipelineResult(success=False, error=result["error"])

        shaped = shape_result(result)
        shaped["pipeline_type"] = pipeline_type
        if result_mutator:
            result_mutator(shaped)
        return PipelineResult(success=True, data=shaped)

    except Exception as e:
        return PipelineResult(success=False, error=str(e))
