from __future__ import annotations
from pipeline.core.state import PipelineState, make_sget
from pipeline.core.node_base import pipeline_node, NodeContext
from pipeline.core.utils import call_structured
from pipeline.domain.sa.schemas import ApiModelerOutput

SYSTEM_PROMPT = """
당신은 시스템의 외부 인터페이스를 설계하는 '수석 API 모델러'입니다.
Gemini 2.5 Flash 모델로서, 다음의 **설계 원칙**을 엄격히 준수하십시오.

[1. 핵심 설계 규칙]
1. **타입 매핑 엄격 적용**: 컴포넌트 인터페이스의 dict/객체 타입은 API 스키마에서 빈 객체({}) 또는 명확한 JSON 스키마로, datetime은 ISO8601 string으로 변환 규칙을 엄격히 적용하십시오.
2. **Zero-Null Policy**: 스키마 내부(request/response_schema 등)를 절대로 비워두지 마십시오.
3. **인증 응답**: 인증(로그인 등) API 응답에는 반드시 생성된 세션의 PK(예: session_id)를 포함하십시오.
4. **언어 규칙**: 모든 사고 과정(thinking)은 반드시 한국어로 작성하십시오.

[2. Few-Shot 예시]
- POST /api/v1/orders
  * request_schema: {"cart_id": "string(uuid)", "shipping_address": "string"}
  * response_schema: {"order_id": "string(uuid)", "status": "string", "created_at": "string(iso8601)"}

출력 데이터 규격 (JSON):
{
  "thinking": "컴포넌트 역할을 기반으로 한 API 도출 및 타입 매핑 설계 과정",
  "apis": [
    {
      "endpoint": "POST /api/v1/resource",
      "request_schema": {...},
      "response_schema": {...}
    }
  ]
}
"""

def _to_compact_text(items: list[dict]) -> str:
    if not items: return "없음"
    return "\n".join("- " + ", ".join(f"{k}: {v}" for k, v in item.items() if v) for item in items)

def _build_user_message(components: list, rtm: list) -> str:
    pruned_components = _to_compact_text([{"name": c.get("component_name"), "role": c.get("role")} for c in components])
    pruned_rtm = _to_compact_text([{"id": r.get("id"), "desc": r.get("desc")} for r in rtm])
    
    return f"\n[Component Design]\n{pruned_components}\n\n[Requirements]\n{pruned_rtm}"

from observability.logger import get_logger

logger = get_logger()

@pipeline_node("api_modeler")
def api_modeler_node(ctx: NodeContext) -> dict:
    sget = ctx.sget
    logger.info("=== [Node Entry] api_modeler_node ===")
    components = sget("component_scheduler_output", {}).get("components", [])
    rtm = sget("merged_project", {}).get("plan", {}).get("requirements_rtm", [])

    user_content = _build_user_message(components, rtm)
    
    res = call_structured(
        api_key=ctx.api_key,
        model=ctx.model,
        schema=ApiModelerOutput,
        system_prompt=SYSTEM_PROMPT,
        user_msg=user_content,
        compress_prompt=False
    )
    
    output = res.parsed
    thinking_msg = output.thinking or "API 모델링 완료"
    
    return {
        "api_modeler_output": output.model_dump(),
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "api_modeler", "thinking": thinking_msg}],
        "current_step": "api_modeler_done"
    }
