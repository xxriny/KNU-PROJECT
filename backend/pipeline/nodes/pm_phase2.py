"""
노드 2 — 비즈니스 우선순위 산정 (Prioritizer)

Pydantic 구조화 출력 강제 + MoSCoW 우선순위 + MECE 검증.
"""

import json
from copy import deepcopy
from pipeline.state import PipelineState, sget as state_sget
from pipeline.schemas import PrioritizerOutput
from pipeline.utils import call_structured_with_thinking

SYSTEM_PROMPT = """\
당신은 MECE 검증을 수행하는 요구사항 우선순위 산정(Prioritizer) 전문가입니다.

[규칙]
1. MoSCoW 우선순위 부여: 각 요구사항에 대해 Must-have | Should-have | Could-have 중 하나를 반드시 선택하세요.
2. 우선순위 산정 근거: 각 결정에 대해 한 문장으로 된 한국어 근거(rationale)를 작성하세요.
3. MECE 검증 (중복 제거 및 원자성 보장):
   - 두 요구사항이 의미상 크게 중복되는 경우, 하나로 병합(MERGE)하고 불필요한 요구사항은 삭제(DELETE)하세요.
   - 병합할 때는 더 구체적이고 원자적인(Atomic) 요구사항의 REQ_ID를 남기세요.
   - [중요] 요구사항이 삭제되더라도 남은 REQ_ID들의 번호를 다시 매기거나 순서를 당기지 마세요. 원본 ID는 추적성을 위해 반드시 그대로 보존되어야 합니다.
4. 내부 추론: thinking 필드의 내용은 3줄 이내로 간결하게 작성하세요."""


def prioritizer_node(state: PipelineState) -> dict:
    # 안전한 상태 접근 헬퍼 (TypedDict / 일반 dict 모두 호환)
    def sget(key, default=None):
        return state_sget(state, key, default)

    reqs = sget("raw_requirements", [])
    if not reqs:
        return {
            "prioritized_requirements": [],
            "current_step": "prioritizer_done",
            "thinking_log": sget("thinking_log", []) + [{"node": "prioritizer", "thinking": "요구사항이 없습니다."}],
        }

    compact = [{"REQ_ID": r.get("REQ_ID"), "category": r.get("category"),
                "description": r.get("description")} for r in reqs]

    user_msg = f"다음 요구사항들에 대해 우선순위를 산정하고 MECE 검증을 수행하세요:\n```json\n{json.dumps(compact, ensure_ascii=False)}\n```"

    try:
        result, thinking = call_structured_with_thinking(
            api_key=sget("api_key", ""),
            model=sget("model", "gemini-2.5-flash"),
            schema=PrioritizerOutput,
            system_prompt=SYSTEM_PROMPT,
            user_msg=user_msg,
            max_retries=3,
        )

        reqs_out = [r.model_dump() for r in result.requirements]

        return {
            "prioritized_requirements": reqs_out,
            "thinking_log": sget("thinking_log", []) + [{"node": "prioritizer", "thinking": thinking}],
            "current_step": "prioritizer_done",
        }
    except Exception as e:
        # 최종 폴백: 원본 복사 후 기본 우선순위 부여 (원본 state 불변성 보장)
        safe_reqs = deepcopy(reqs)
        for r in safe_reqs:
            r.setdefault("priority", "Should-have")
            r.setdefault("rationale", "구조화 출력 실패 후 기본값 자동 할당")
        return {
            "prioritized_requirements": safe_reqs,
            "thinking_log": sget("thinking_log", []) + [{"node": "prioritizer", "thinking": f"구조화 출력 실패: {e}"}],
            "current_step": "prioritizer_done",
        }


