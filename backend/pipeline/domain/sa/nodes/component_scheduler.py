"""
Component Scheduler Node — 요구사항(RTM)을 시스템 컴포넌트로 분해
"""
from __future__ import annotations
from pipeline.core.node_base import pipeline_node, NodeContext
from pipeline.core.utils import call_structured, create_context_cache
from pipeline.core.cache_manager import cache_manager
from pipeline.domain.sa.schemas import ComponentSchedulerOutput
from observability.logger import get_logger

logger = get_logger()

SYSTEM_PROMPT = """
당신은 '수석 컴포넌트 설계자'입니다. 다음 규칙을 엄격히 준수하십시오.

[1. 표준 명칭]
- 기본 ID: `id` (uuid) | 참조 식별자: `대상_id` (uuid)
- 토큰: `access_token`, `refresh_token` (string)

[2. 설계 규칙]
- **린(Lean) 설계**: 요구사항 1개당 무조건 1개의 컴포넌트가 아닙니다. 유사한 도메인은 하나로 통합하여 복잡도를 낮추십시오.
- **핵심 집중**: 비즈니스 가치가 높은 핵심 도메인 위주로 컴포넌트를 구성하십시오.
- **보안/역설계**: 특수 요구사항 시 도메인 본질(예: user_id 대신 public_key) 반영.
- **snake_case**: 영문 snake_case만 사용.
- **Thinking**: 한국어 핵심 단어 **5개 이내**.

[3. 출력 규격(JSON)]
{"th": "단어 5개", "cp": [{"dm": "F|B", "nm": "Name", "rl": "역할", "rt": "REQ-01,REQ-02", "dp": "Dep1,Dep2"}]}
"""


def _build_user_message(merged_project: dict) -> str:
    plan = merged_project.get("plan", {})
    rtm = plan.get("requirements_rtm", [])
    p_rtm = "\n".join(f"{r.get('id')}:{r.get('desc')}" for r in rtm)
    return f"Strategy: {merged_project.get('merge_strategy', '')}\nRTM:\n{p_rtm}"


@pipeline_node("component_scheduler")
def component_scheduler_node(ctx: NodeContext) -> dict:
    sget = ctx.sget
    logger.info("=== [Node Entry] component_scheduler_node ===")

    merged_project = sget("merged_project", {})
    user_content = _build_user_message(merged_project)
    run_id = sget("run_id", "sa_session")

    # Context Cache 생성 시도 (1024 토큰 이상일 때만 활성화)
    cache_name = cache_manager.get_google_cache(run_id)
    if not cache_name:
        plan = merged_project.get("plan", {})
        rtm_text = "\n".join(f"{r.get('id')}:{r.get('desc')}" for r in plan.get("requirements_rtm", []))
        cache_name = create_context_cache(
            api_key=ctx.api_key, model=ctx.model,
            system_instruction=SYSTEM_PROMPT, contents=[rtm_text]
        )
        if cache_name:
            cache_manager.cache_google_context(run_id, cache_name, len(rtm_text) // 2)

    res = call_structured(
        api_key=ctx.api_key, model=ctx.model,
        schema=ComponentSchedulerOutput, system_prompt=SYSTEM_PROMPT,
        user_msg=user_content, context_cache=cache_name,
        compress_prompt=False, temperature=0.0
    )

    output = res.parsed
    return {
        "component_scheduler_output": output.model_dump(),
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "component_scheduler", "thinking": output.thinking or ""}],
        "current_step": "component_scheduler_done"
    }
