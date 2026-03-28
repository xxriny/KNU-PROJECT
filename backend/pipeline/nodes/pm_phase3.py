"""
노드 3 — 요구사항 추적 매트릭스 (RTM) 기반 구축

Pydantic 구조화 출력 강제 + 데이터 흐름 기반 의존성 매핑.
Self-Correction 재시도 루프로 의존성 상실(Dependency Amnesia) 자가 치유.

[핵심]
- with_structured_output()으로 depends_on 필드를 List[str]로 강제
- 빈 의존성이 50% 초과 시 에러 메시지를 LLM에 피드백하여 재생성
"""

import json
from copy import deepcopy
from pipeline.state import PipelineState, make_sget
from pipeline.schemas import RTMBuilderOutput
from pipeline.utils import call_structured_with_thinking, get_llm
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from version import DEFAULT_MODEL

SYSTEM_PROMPT = """\
당신은 요구사항 추적 매트릭스(RTM) 구축 전문가입니다.
의존성 매핑을 통해 요구사항 간 데이터 흐름을 정의하세요.

[핵심: 의존성 규칙]
1. 데이터를 처리/변환하는 모든 요구사항은 해당 데이터를 생산하는 요구사항에 의존해야 합니다.
   - 데이터 흐름: 수집 → 마이닝/파싱 → 저장 → 분석 → 매칭 → 생성 → 표시
   - 예: "텍스트 마이닝"은 ["데이터 수집"] 요구사항에 의존
2. 최대 20%의 요구사항만 빈 depends_on을 가질 수 있습니다 (인프라 세팅 같은 진정 독립적인 항목만).
3. 순환 의존성 금지. A→B면 B→A는 불가입니다.
4. "test_criteria": 테스트 가능한 수용 기준 (한국어 1문장)을 추가하세요.
5. thinking은 3줄 이내로 데이터 흐름 추론에 집중하세요.
6. depends_on은 반드시 REQ_ID 문자열 목록입니다. 예: ["REQ-001", "REQ-003"]"""


def _validate_dependency_quality(result: RTMBuilderOutput) -> str | None:
    """
    의존성 품질 검증. 문제가 있으면 에러 메시지 반환, 없으면 None.
    이 에러 메시지를 LLM에 피드백하여 자가 수정하게 한다.
    """
    reqs = result.requirements
    total = len(reqs)
    if total == 0:
        return None

    # 1. 빈 의존성 비율 체크
    empty_deps = sum(1 for r in reqs if not r.depends_on)
    empty_ratio = empty_deps / total
    if empty_ratio > 0.5:
        return (
            f"의존성 품질 오류: {empty_deps}/{total} ({empty_ratio:.0%}) 요구사항이 빈 depends_on을 가지고 있습니다. "
            f"최대 20%만 허용됩니다. "
            f"대부분의 요구사항은 데이터 흐름에 따라 최소 하나의 다른 요구사항에 의존해야 합니다. "
            f"예를 들어, 모든 데이터 처리 작업은 데이터 수집 작업에 의존해야 합니다. "
            f"데이터 흐름 체인을 다시 분석하여 누락된 의존성을 추가하세요."
        )

    # 2. 순환 의존성 체크
    dep_map = {r.REQ_ID: set(r.depends_on) for r in reqs}
    for req_id, deps in dep_map.items():
        for dep in deps:
            if dep in dep_map and req_id in dep_map[dep]:
                return (
                    f"순환 의존성 오류: {req_id}이(가) {dep}에 의존하고, "
                    f"동시에 {dep}이(가) {req_id}에 의존합니다. "
                    f"이 순환 의존성의 한 방향을 제거하세요."
                )

    # 3. 존재하지 않는 REQ_ID 참조 체크
    valid_ids = {r.REQ_ID for r in reqs}
    for r in reqs:
        for dep in r.depends_on:
            if dep not in valid_ids:
                return (
                    f"유효하지 않은 참조 오류: {r.REQ_ID}이(가) {dep}에 의존하지만, "
                    f"{dep}은(는) 요구사항 목록에 존재하지 않습니다. "
                    f"존재하는 REQ_ID들만 참조하세요: {sorted(valid_ids)}"
                )

    return None


def rtm_builder_node(state: PipelineState) -> dict:
    sget = make_sget(state)

    reqs = sget("prioritized_requirements", [])
    if not reqs:
        return {
            "rtm_matrix": [],
            "requirements_rtm": [],
            "current_step": "rtm_builder_done",
            "thinking_log": sget("thinking_log", []) + [{"node": "rtm_builder", "thinking": "No requirements."}],
        }

    compact = [
        {"REQ_ID": r.get("REQ_ID"), "category": r.get("category"),
         "description": r.get("description"), "priority": r.get("priority")}
        for r in reqs
    ]
    user_msg = (
        f"다음 요구사항들에 대한 의존성을 매핑하세요. "
        f"주의: 최대 20%만 빈 depends_on을 가질 수 있습니다.\n"
        f"```json\n{json.dumps(compact, ensure_ascii=False)}\n```"
    )

    max_retries = 3

    try:
        # 1차: 구조화 출력 호출 (KeyError 방어 적용)
        api_key = sget("api_key", "")
        model = sget("model", DEFAULT_MODEL)
        
        result, thinking = call_structured_with_thinking(
            api_key=api_key,
            model=model,
            schema=RTMBuilderOutput,
            system_prompt=SYSTEM_PROMPT,
            user_msg=user_msg,
            max_retries=max_retries,
        )

        # 2차: 의존성 품질 검증 + Self-Correction 루프
        for correction_attempt in range(2):
            quality_error = _validate_dependency_quality(result)
            if quality_error is None:
                break  # 품질 통과

            # 방금 LLM이 생성한 (틀린) 결과를 AIMessage로 주입하기 위해 직렬화
            bad_output_json = json.dumps([r.model_dump() for r in result.requirements], ensure_ascii=False)

            correction_msg = (
                f"{quality_error}\n\n"
                f"수정된 출력을 반환하세요."
            )

            llm = get_llm(api_key, model)
            structured_llm = llm.with_structured_output(RTMBuilderOutput)
            
            # 2. 대화 역할 교차(Alternating Roles) 규칙 준수
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=user_msg),
                AIMessage(content=bad_output_json), # LLM의 오답 노트를 명확히 인식시킴
                HumanMessage(content=correction_msg),
            ]

            try:
                result = structured_llm.invoke(messages)
                thinking += f"\n[Self-Correction attempt {correction_attempt + 1}] {quality_error[:80]}..."
            except Exception:
                break  # 재시도 실패 시 현재 결과 사용

        reqs_out = [r.model_dump() for r in result.requirements]

        final_check = _validate_dependency_quality(result)
        if final_check:
            thinking += f"\n[WARNING] {final_check[:100]}"

        return {
            "rtm_matrix": reqs_out,
            "requirements_rtm": reqs_out,
            "thinking_log": sget("thinking_log", []) + [{"node": "rtm_builder", "thinking": thinking}],
            "current_step": "rtm_builder_done",
        }

    except Exception as e:
        # 3. 상태 불변성 보장 (Deepcopy 활용)
        safe_reqs = deepcopy(reqs)
        for r in safe_reqs:
            r.setdefault("depends_on", [])
            r.setdefault("test_criteria", "의존성 파싱 실패로 인한 기본값 할당")
            
        return {
            "rtm_matrix": safe_reqs,
            "requirements_rtm": safe_reqs,
            "thinking_log": sget("thinking_log", []) + [{"node": "rtm_builder", "thinking": f"Structured output failed: {e}"}],
            "current_step": "rtm_builder_done",
        }
