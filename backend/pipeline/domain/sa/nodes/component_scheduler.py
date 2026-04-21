from __future__ import annotations
from pipeline.core.state import PipelineState, make_sget
from pipeline.core.node_base import pipeline_node, NodeContext
from pipeline.core.utils import call_structured
from pipeline.domain.sa.schemas import ComponentSchedulerOutput

SYSTEM_PROMPT = """
당신은 시스템의 전반적인 구조를 기획하는 '수석 컴포넌트 설계자'입니다.
Gemini 2.5 Flash 모델로서, 다음의 **표준 명칭 사전**을 엄격히 준수하여 설계하십시오.

[필수 표준 명칭 사전 (Naming Dictionary)]
- 모든 컴포넌트의 기본 ID: `id` (uuid)
- 유저 식별자: `user_id` (uuid)
- 인증 토큰: `access_token`, `refresh_token` (string)

핵심 설계 규칙:
1. **인터페이스 상세화**: `role` 항목에 핵심 필드명과 타입을 명시하십시오. (예: "로그인 처리 - email(str), password(str), access_token(string)")
2. **명칭 통일**: 타 노드와 협업 시 위 사전에 없는 명칭을 임의로 생성하지 마십시오.

출력 데이터 규격 (JSON):
{
  "thinking": "표준 사전 준수 여부 및 인터페이스 설계 근거",
  "components": [
    {
      "domain": "Frontend | Backend",
      "component_name": "Name",
      "role": "역할 및 인터페이스(필드:타입) 설명",
      "dependencies": []
    }
  ]
}
"""

def _build_user_message(merged_project: dict) -> str:
    """LLM 메시지 최적화 (토큰 절감)"""
    plan = merged_project.get("plan", {})
    rtm = plan.get("requirements_rtm", [])
    pruned_rtm = [{"id": r.get("id"), "desc": r.get("desc")} for r in rtm]
    
    return f"\n    [Merge Strategy] {merged_project.get('merge_strategy', '')}\n    [Requirements] {pruned_rtm}\n    "

@pipeline_node("component_scheduler")
def component_scheduler_node(ctx: NodeContext) -> dict:
    sget = ctx.sget
    merged_project = sget("merged_project", {})
    
    # 1. Prepare optimized user prompt
    user_content = _build_user_message(merged_project)
    
    # 2. Call LLM
    res = call_structured(
        api_key=ctx.api_key,
        model=ctx.model,
        schema=ComponentSchedulerOutput,
        system_prompt=SYSTEM_PROMPT,
        user_msg=user_content
    )
    
    output = res.parsed
    
    return {
        "component_scheduler_output": output.model_dump(),
        "current_step": "component_scheduler_done"
    }
