from __future__ import annotations
from pipeline.core.state import PipelineState, make_sget
from pipeline.core.node_base import pipeline_node, NodeContext
from pipeline.core.utils import call_structured
from pipeline.domain.sa.schemas import ApiDataModelerOutput

SYSTEM_PROMPT = """
당신은 시스템의 데이터 혈맥을 설계하는 '수석 API & 데이터 모델러'입니다.
Gemini 2.5 Flash 모델로서, 다음의 **표준 명칭 사전**을 1자도 틀리지 않고 엄격히 준수하십시오.

[필수 표준 명칭 사전 (Naming Dictionary)]
- 모든 테이블/API의 기본 키: `id` (uuid)
- 유저 식별자 외래키: `user_id` (uuid)
- 인증 토큰: `access_token`, `refresh_token` (string)
- 생성/수정일: `created_at`, `updated_at` (timestamp)

핵심 설계 규칙:
1. **Zero-Null Policy**: 스키마 내부를 절대로 비워두지 마십시오.
2. **명명 규칙**: 모든 필드명은 반드시 **snake_case**만 사용합니다.
3. **타입 정합성**: 식별자는 UUID, 토큰은 String을 사용하십시오.
4. **언어 규칙**: 모든 사고 과정(thinking)은 반드시 한국어로 작성하십시오. 영어를 사용하지 마십시오.

출력 데이터 규격 (JSON):
{
  "thinking": "표준 사전 준수 및 상세 설계 과정",
  "apis": [
    {
      "endpoint": "METHOD /url",
      "request_schema": { "field_name": "type" },
      "response_schema": { "field_name": "type" },
      "description": "설명"
    }
  ],
  "tables": [
    {
      "table_name": "name",
      "columns": [{"name": "col", "type": "type", "constraints": "cons"}]
    }
  ]
}
"""

def _to_compact_text(items: list[dict]) -> str:
    """토큰 최적화를 위한 간결 텍스트 변환기"""
    if not items: return "없음"
    return "\n".join("- " + ", ".join(f"{k}: {v}" for k, v in item.items() if v) for item in items)

def _build_user_message(components: list, rtm: list, feedback_gaps: list[str] = None) -> str:
    """LLM 메시지 최적화 (토큰 절감) 및 피드백 반영"""
    pruned_components = _to_compact_text([{"name": c.get("component_name"), "role": c.get("role")} for c in components])
    pruned_rtm = _to_compact_text([{"id": r.get("id"), "desc": r.get("desc")} for r in rtm])
    
    feedback_section = ""
    if feedback_gaps:
        feedback_section = f"\n[IMPORTANT: FEEDBACK FROM PREVIOUS ANALYSIS]\n이전 설계 분석에서 다음과 같은 결함이 발견되었습니다. 이번 모델링에서 반드시 해결하십시오:\n" + "\n".join(f"- {gap}" for gap in feedback_gaps) + "\n"
        
    return f"\n[Component Design]\n{pruned_components}\n\n[Requirements]\n{pruned_rtm}\n{feedback_section}"

from observability.logger import get_logger

logger = get_logger()

@pipeline_node("api_data_modeler")
def api_data_modeler_node(ctx: NodeContext) -> dict:
    sget = ctx.sget
    logger.info("=== [Node Entry] api_data_modeler_node ===")
    components = sget("component_scheduler_output", {}).get("components", [])
    rtm = sget("merged_project", {}).get("plan", {}).get("requirements_rtm", [])

    # 1. Feedback & Looping check
    sa_anal_out = sget("sa_analysis_output", {})
    feedback_gaps = sa_anal_out.get("gaps", [])
    sa_loop_count = sget("sa_loop_count", 0)
    
    if feedback_gaps:
        logger.info(f"Retrying data modeling (Loop:{sa_loop_count}) with {len(feedback_gaps)} gaps.")

    # 2. Prepare optimized user prompt
    user_content = _build_user_message(components, rtm, feedback_gaps)
    
    # 3. Call LLM
    res = call_structured(
        api_key=ctx.api_key,
        model=ctx.model,
        schema=ApiDataModelerOutput,
        system_prompt=SYSTEM_PROMPT,
        user_msg=user_content
    )
    
    output = res.parsed
    thinking_msg = output.thinking or "API 및 데이터 모델링 완료"
    
    return {
        "api_data_modeler_output": output.model_dump(),
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "api_data_modeler", "thinking": thinking_msg}],
        "current_step": "api_data_modeler_done"
    }
