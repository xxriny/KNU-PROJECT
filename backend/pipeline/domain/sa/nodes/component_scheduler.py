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
3. **언어 규칙**: 모든 사고 과정(thinking)은 반드시 한국어로 작성하십시오. 영어를 사용하지 마십시오.

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

def _to_compact_text(items: list[dict]) -> str:
    """토큰 최적화를 위한 간결 텍스트 변환기"""
    if not items: return "없음"
    return "\n".join("- " + ", ".join(f"{k}: {v}" for k, v in item.items() if v) for item in items)

def _build_user_message(merged_project: dict, feedback_gaps: list[str] = None) -> str:
    """LLM 메시지 최적화 (토큰 절감) 및 피드백 반영"""
    plan = merged_project.get("plan", {})
    rtm = plan.get("requirements_rtm", [])
    pruned_rtm = _to_compact_text([{"id": r.get("id"), "desc": r.get("desc")} for r in rtm])
    
    feedback_section = ""
    if feedback_gaps:
        feedback_section = f"\n[IMPORTANT: FEEDBACK FROM PREVIOUS ANALYSIS]\n이전 설계 분석에서 다음과 같은 결함이 발견되었습니다. 이번 설계에서 반드시 해결하십시오:\n" + "\n".join(f"- {gap}" for gap in feedback_gaps) + "\n"
        
    return f"\n[Merge Strategy]\n{merged_project.get('merge_strategy', '')}\n\n[Requirements]\n{pruned_rtm}\n{feedback_section}"

from observability.logger import get_logger

logger = get_logger()

@pipeline_node("component_scheduler")
def component_scheduler_node(ctx: NodeContext) -> dict:
    sget = ctx.sget
    logger.info("=== [Node Entry] component_scheduler_node ===")
    merged_project = sget("merged_project", {})

    # 1. Feedback & Looping check
    sa_anal_out = sget("sa_analysis_output", {})
    feedback_gaps = sa_anal_out.get("gaps", [])
    sa_loop_count = sget("sa_loop_count", 0)
    
    if feedback_gaps:
        logger.info(f"Retrying component design (Loop:{sa_loop_count}) with {len(feedback_gaps)} gaps.")

    # 2. Prepare optimized user prompt
    user_content = _build_user_message(merged_project, feedback_gaps)
    
    # 3. Call LLM
    res = call_structured(
        api_key=ctx.api_key,
        model=ctx.model,
        schema=ComponentSchedulerOutput,
        system_prompt=SYSTEM_PROMPT,
        user_msg=user_content
    )
    
    output = res.parsed
    thinking_msg = output.thinking or "컴포넌트 설계 완료"
    
    return {
        "component_scheduler_output": output.model_dump(),
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "component_scheduler", "thinking": thinking_msg}],
        "current_step": "component_scheduler_done"
    }
