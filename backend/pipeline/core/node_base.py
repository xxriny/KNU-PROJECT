"""
Pipeline Node Base — 공통 노드 보일러플레이트 추출 (R-008)
모든 파이프라인 노드가 공유하는 sget 초기화, thinking_log 누적,
current_step 설정, try-except 패턴을 데코레이터로 통합.
"""

from __future__ import annotations
from dataclasses import dataclass
from functools import wraps
from typing import Any

from pipeline.core.state import PipelineState, make_sget
from observability.logger import get_logger
from version import DEFAULT_MODEL


@dataclass
class NodeContext:
    """노드 함수에 전달되는 실행 컨텍스트."""
    state: PipelineState
    sget: Any          # make_sget(state) curried accessor
    api_key: str = ""
    model: str = DEFAULT_MODEL
    node_name: str = ""

    @property
    def thinking_log(self) -> list:
        return self.sget("thinking_log", []) or []


def pipeline_node(node_name: str):
    """
    파이프라인 노드 보일러플레이트를 제거하는 데코레이터.

    사용법::

        @pipeline_node("sa_phase6")
        def sa_phase6_node(ctx: NodeContext) -> dict:
            # ctx.sget, ctx.api_key, ctx.model 사용 가능
            # 반환값의 thinking_log/current_step은 자동 설정됨
            return {"sa_phase6": output}

    자동 처리 항목:
    - make_sget(state) 초기화
    - api_key, model 추출
    - thinking_log 누적 (반환 dict에 ``_thinking`` 키가 있으면 자동 추가)
    - current_step 설정
    - **최후방 안전망** try-except (노드 내부에서 잡지 못한 예외만 포착)
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(state: PipelineState) -> dict:
            sget = make_sget(state)
            ctx = NodeContext(
                state=state,
                sget=sget,
                api_key=sget("api_key", ""),
                model=sget("model", DEFAULT_MODEL),
                node_name=node_name,
            )
            try:
                result = fn(ctx)
                if not isinstance(result, dict):
                    result = {}

                thinking_text = result.pop("_thinking", None)
                if thinking_text is not None and "thinking_log" not in result:
                    result["thinking_log"] = ctx.thinking_log + [
                        {"node": node_name, "thinking": thinking_text}
                    ]

                if "current_step" not in result:
                    result["current_step"] = f"{node_name}_done"

                return result

            except Exception as e:
                get_logger().exception(f"{node_name} failed")
                return {
                    "error": f"{node_name} 실패: {e}",
                    "thinking_log": ctx.thinking_log + [
                        {"node": node_name, "thinking": f"오류: {e}"}
                    ],
                    "current_step": "error",
                }

        # @wraps(fn) copies fn's annotations (e.g. ctx: NodeContext). LangGraph
        # coerces node input from the first parameter's type — must stay PipelineState.
        wrapper.__annotations__ = {"state": PipelineState, "return": dict}
        return wrapper
    return decorator
