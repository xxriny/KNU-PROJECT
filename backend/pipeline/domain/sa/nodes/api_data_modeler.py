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

def _build_user_message(components: list, rtm: list) -> str:
    """LLM 메시지 최적화 (토큰 절감)"""
    pruned_components = [{"name": c.get("component_name"), "role": c.get("role")} for c in components]
    pruned_rtm = [{"id": r.get("id"), "desc": r.get("desc")} for r in rtm]
    
    return f"\n    [Component Design] {pruned_components}\n    [Requirements] {pruned_rtm}\n    "

@pipeline_node("api_data_modeler")
def api_data_modeler_node(ctx: NodeContext) -> dict:
    sget = ctx.sget
    components = sget("component_scheduler_output", {}).get("components", [])
    rtm = sget("merged_project", {}).get("plan", {}).get("requirements_rtm", [])
    
    # 1. Prepare optimized user prompt
    user_content = _build_user_message(components, rtm)
    
    # 2. Call LLM
    res = call_structured(
        api_key=ctx.api_key,
        model=ctx.model,
        schema=ApiDataModelerOutput,
        system_prompt=SYSTEM_PROMPT,
        user_msg=user_content
    )
    
    output = res.parsed
    
    return {
        "api_data_modeler_output": output.model_dump(),
        "current_step": "api_data_modeler_done"
    }
