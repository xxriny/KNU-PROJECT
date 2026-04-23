from __future__ import annotations
from pipeline.core.state import PipelineState, make_sget
from pipeline.core.node_base import pipeline_node, NodeContext
from pipeline.core.utils import call_structured
from pipeline.domain.sa.schemas import ApiDataModelerOutput

SYSTEM_PROMPT = """
당신은 시스템의 데이터 혈맥을 설계하는 '수석 API & 데이터 모델러'입니다.
Gemini 2.5 Flash 모델로서, 다음의 **표준 명칭 사전**과 **설계 원칙**을 엄격히 준수하십시오.

[1. 필수 표준 명칭 사전 (Naming Dictionary)]
- 모든 테이블/API의 기본 키: `id` (uuid)
- 유저 식별자 외래키: `user_id` (uuid)
- 인증 토큰: `access_token`, `refresh_token` (string)
- 생성/수정일: `created_at`, `updated_at` (timestamp)
- 모든 명칭은 **snake_case**만 허용합니다. (예: userId -> user_id)

[2. Few-Shot 예시: 장바구니-주문 도메인]
- DB 테이블 설계:
  * `users`: id(PK), email, password, ...
  * `carts`: id(PK), user_id(FK -> users), status, ...
  * `orders`: id(PK), user_id(FK -> users), cart_id(FK -> carts), total_price, ...
- API 설계:
  * `POST /api/v1/orders`: 요청 시 `cart_id` 필수, 응답 시 생성된 `order_id` 포함.

[3. 핵심 설계 규칙]
1. **Zero-Null Policy**: 스키마 내부(request/response_schema 등)를 절대로 비워두지 마십시오.
2. **타입 정합성**: 모든 ID는 UUID, 모든 토큰은 String을 사용하십시오.
3. **참조 무결성**: 외래키(`_id`로 끝나는 필드)를 정의할 때는 반드시 대응하는 테이블이 `tables` 목록에 존재해야 합니다.
4. **언어 규칙**: 모든 사고 과정(thinking)은 반드시 한국어로 작성하십시오.

출력 데이터 규격 (JSON):
{
  "thinking": "표준 사전 준수 및 테이블-API 간 정합성 설계 과정",
  "apis": [...],
  "tables": [...]
}
"""

def _to_compact_text(items: list[dict]) -> str:
    """토큰 최적화를 위한 간결 텍스트 변환기"""
    if not items: return "없음"
    return "\n".join("- " + ", ".join(f"{k}: {v}" for k, v in item.items() if v) for item in items)

def _build_user_message(components: list, rtm: list) -> str:
    """LLM 메시지 최적화 (토큰 절감)"""
    pruned_components = _to_compact_text([{"name": c.get("component_name"), "role": c.get("role")} for c in components])
    pruned_rtm = _to_compact_text([{"id": r.get("id"), "desc": r.get("desc")} for r in rtm])
    
    return f"\n[Component Design]\n{pruned_components}\n\n[Requirements]\n{pruned_rtm}"

from observability.logger import get_logger

logger = get_logger()

@pipeline_node("api_data_modeler")
def api_data_modeler_node(ctx: NodeContext) -> dict:
    sget = ctx.sget
    logger.info("=== [Node Entry] api_data_modeler_node ===")
    components = sget("component_scheduler_output", {}).get("components", [])
    rtm = sget("merged_project", {}).get("plan", {}).get("requirements_rtm", [])

    # 1. Prepare optimized user prompt
    user_content = _build_user_message(components, rtm)
    
    # 3. Call LLM
    res = call_structured(
        api_key=ctx.api_key,
        model=ctx.model,
        schema=ApiDataModelerOutput,
        system_prompt=SYSTEM_PROMPT,
        user_msg=user_content,
        compress_prompt=False # 압축 모델 한계로 인한 데이터 유실 방지를 위해 비활성화
    )
    
    output = res.parsed
    thinking_msg = output.thinking or "API 및 데이터 모델링 완료"
    
    return {
        "api_data_modeler_output": output.model_dump(),
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "api_data_modeler", "thinking": thinking_msg}],
        "current_step": "api_data_modeler_done"
    }
