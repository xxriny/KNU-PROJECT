"""
SA Unified Modeler Node — 컴포넌트를 기반으로 API + DB 스키마를 동시 설계
"""
from __future__ import annotations
from pipeline.core.node_base import pipeline_node, NodeContext
from pipeline.core.utils import call_structured
from pipeline.core.cache_manager import cache_manager
from pipeline.domain.sa.schemas import SAUnifiedModelerOutput
from observability.logger import get_logger

logger = get_logger()

SYSTEM_PROMPT = """
당신은 '수석 시스템 설계자'입니다. 컴포넌트를 분석하여 API 및 DB 스키마를 동시 설계하십시오.

[1. 전수 커버리지 & 린 설계 (MANDATORY)]
- **필수 기능 중심**: 요구사항을 충족하기 위해 '진정으로 필요한' API와 Table만 설계하십시오. 모든 컴포넌트에 기계적으로 CRUD를 만들 필요가 없습니다.
- **도메인 응집도**: 논리적으로 밀접한 데이터는 하나의 테이블에 통합하여 관리하십시오.
- **참조 무결성**: 외래키(FK)로 참조하는 대상 테이블(마스터성)은 반드시 존재해야 합니다.
- **제약 사항 반영**: 요구사항의 '차단', '금지', '검증' 규칙(예: 순환 참조 발생 시 생성 차단)을 API 동작에 반드시 명시하십시오.

[2. 설계 원칙]
- **명칭 일관성(Zero-Tolerance)**: API 필드명과 DB 컬럼명은 반드시 **100% 동일**해야 합니다. (예: API가 password면 DB도 password여야 함. passwordHash로 바꾸는 행위 절대 금지)
- **RESTful**: URI는 명사 복수형. 불필요한 엔드포인트 양산을 지양하십시오.
- **응답 보장**: 모든 API는 반드시 비어있지 않은 응답(res) 필드를 가져야 합니다.
- **정규화**: 중복을 최소화하되, 실무적인 관점에서 적절히 통합하십시오.
- **Thinking**: 한국어 핵심 단어 **5개 이내**.

[3. 출력 규격(JSON)]
{
  "th": "단어 5개",
  "df": {"N": "{f:t}"},
  "ap": [{"ep": "M /p", "rq": "{f:t}", "rs": "{f:t}"}],
  "tb": [{"nm": "T", "cl": "n:t:pk,n:t:fk"}]
}
"""


def _build_user_message(components: list, rtm: list) -> str:
    p_rtm = "\n".join(f"{r.get('id')}:{r.get('desc')}" for r in rtm)

    def _g(obj, k):
        """dict/Pydantic 겸용 필드 추출"""
        if hasattr(obj, 'get'):
            return obj.get(k) or obj.get(k.replace('nm', 'name').replace('rl', 'role').replace('rt', 'rtms'))
        return getattr(obj, k, None) or getattr(obj, k.replace('nm', 'name').replace('rl', 'role').replace('rt', 'rtms'), None)

    p_comp = "\n".join(f"{_g(c, 'nm')}:{_g(c, 'rl')}:{_g(c, 'rt')}" for c in components)
    return (
        f"Comp:\n{p_comp}\n"
        f"RTM:\n{p_rtm}\n\n"
        f"[지침] 위 컴포넌트들을 분석하여, 요구사항을 완벽히 해결하는 데 '필수적인' 최소한의 API와 DB 스키마를 설계하십시오."
    )


@pipeline_node("sa_unified_modeler")
def sa_unified_modeler_node(ctx: NodeContext) -> dict:
    sget = ctx.sget
    logger.info("=== [Node Entry] sa_unified_modeler_node ===")

    components = sget("component_scheduler_output", {}).get("components", [])
    rtm = sget("merged_project", {}).get("plan", {}).get("requirements_rtm", [])
    run_id = sget("run_id", "sa_session")

    user_content = _build_user_message(components, rtm)
    cache_name = cache_manager.get_google_cache(run_id)

    res = call_structured(
        api_key=ctx.api_key, model=ctx.model,
        schema=SAUnifiedModelerOutput, system_prompt=SYSTEM_PROMPT,
        user_msg=user_content, context_cache=cache_name,
        compress_prompt=False, temperature=0.0
    )

    output = res.parsed
    return {
        "sa_unified_modeler_output": output.model_dump(),
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "unified_modeler", "thinking": output.thinking or ""}],
        "current_step": "unified_modeling_done"
    }
