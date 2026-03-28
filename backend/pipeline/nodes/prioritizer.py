import json
from copy import deepcopy
from pipeline.state import PipelineState, sget
from pipeline.schemas import PrioritizerOutput
from pipeline.utils import call_structured_with_thinking

SYSTEM_PROMPT = """\
당신은 요구사항 우선순위 산정(Prioritizer) 전문가입니다.

<goal>
제공된 원자적 요구사항(raw_requirements) 목록을 분석하여 MoSCoW 원칙에 따라 우선순위와 근거를 추가하세요.
</goal>

<critical_rules>
1. [절대 준수] 입력받은 요구사항의 개수와 REQ_ID는 100% 그대로 유지해야 합니다. 의미가 중복되어 보이더라도 절대 임의로 병합(Merge)하거나 삭제(Delete)하지 마세요. 당신의 역할은 오직 '우선순위 평가'뿐입니다.
2. MoSCoW 우선순위 부여: 각 요구사항에 대해 Must-have | Should-have | Could-have 중 하나를 반드시 선택하세요.
3. 우선순위 산정 근거: 각 결정에 대해 한 문장으로 된 한국어 근거(rationale)를 작성하세요.
4. 내부 추론: thinking 필드의 내용은 3줄 이내로 간결하게 작성하세요.
</critical_rules>
"""

def prioritizer_node(state: PipelineState) -> dict:
    reqs = sget(state, "raw_requirements", [])
    if not reqs:
        return {
            "prioritized_requirements": [],
            "current_step": "prioritizer_done",
            "thinking_log": sget(state, "thinking_log", []) + [{"node": "prioritizer", "thinking": "요구사항이 없습니다."}],
        }

    compact = [{"REQ_ID": r.get("REQ_ID"), "category": r.get("category"),
                "description": r.get("description")} for r in reqs]

    user_msg = f"다음 요구사항들에 대해 우선순위를 산정하세요 (절대 삭제/병합 금지):\n```json\n{json.dumps(compact, ensure_ascii=False)}\n```"

    try:
        result, thinking = call_structured_with_thinking(
            api_key=sget(state, "api_key", ""),
            model=sget(state, "model", "gemini-2.5-flash"),
            schema=PrioritizerOutput,
            system_prompt=SYSTEM_PROMPT,
            user_msg=user_msg,
            max_retries=3,
        )

        reqs_out = [r.model_dump() for r in result.requirements]

        return {
            "prioritized_requirements": reqs_out,
            "thinking_log": sget(state, "thinking_log", []) + [{"node": "prioritizer", "thinking": thinking}],
            "current_step": "prioritizer_done",
        }
    except Exception as e:
        safe_reqs = deepcopy(reqs)
        for r in safe_reqs:
            r.setdefault("priority", "Should-have")
            r.setdefault("rationale", "구조화 출력 실패 후 기본값 자동 할당")
        return {
            "prioritized_requirements": safe_reqs,
            "thinking_log": sget(state, "thinking_log", []) + [{"node": "prioritizer", "thinking": f"구조화 출력 실패: {e}"}],
            "current_step": "prioritizer_done",
        }