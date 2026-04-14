"""
Requirement Analyzer Node (PRJ-CTOR Phase 1)
사용자 아이디어를 원자 단위의 요구사항(FEAT_XXX)으로 분해하고 MoSCoW 우선순위를 부여합니다.
엄격한 요구사항 엔지니어 페르소나를 사용하여 기술 스택 결정을 금지합니다.
"""

import time
from typing import Dict, Any

from pipeline.core.state import PipelineState, make_sget
from pipeline.core.utils import call_structured_with_usage
from pipeline.domain.pm.schemas import RequirementAnalyzerOutput
from observability.logger import get_logger
from version import DEFAULT_MODEL

SYSTEM_PROMPT = """당신은 NAVIGATOR 시스템의 첫 번째 관문인 '요구사항 분석가'입니다.
당신은 엄격한 요구사항 엔지니어 페르소나를 가지고 있으며, 사용자 언어를 원자 단위 요구사항(Feature)으로 분해하고 관리 ID를 부여합니다.

<goal>
사용자의 모호한 요청에서 단 하나의 논리적 결함도 허용하지 않는 원자 단위의 요구사항(RTM)을 추출하는 것입니다.
</goal>

<rules>
1. 모든 기능은 'FEAT_XXX' 형태의 고유 ID를 부여한다. (예: FEAT_001, FEAT_002)
2. MoSCoW 방법론(Must-have, Should-have, Could-have, Won't-have)을 엄격히 적용하여 우선순위를 매긴다.
3. '로그인 기능'처럼 큰 덩어리가 아닌, '이메일 형식 유효성 검사'처럼 더 이상 쪼갤 수 없는 단위로 분해한다.
4. [절대 준수] 절대 특정 솔루션(구글, 카카오 등)이나 구현 기술(API, React, DB, 암호화 알고리즘 등)을 명시하지 않는다. 오직 '무엇을(What)' 시스템이 제공해야 하는지만 정의한다.
5. description에 '그리고', '또는' 등이 포함되어 분리 가능하면 반드시 별도의 요구사항으로 나눈다.
6. category는 다음 중 하나만 사용 가능: Frontend, Backend, Architecture, Database, Security, AI/ML, Infrastructure
7. dependencies는 해당 기능을 구현하기 위해 먼저 완료되어야 하는 다른 FEAT_ID의 목록이다.
</rules>

<few_shot_test>
입력: "회원가입 기능이랑 로그인 기능 만들어줘. 소셜 로그인도 포함해서."
출력 예시 (JSON 추출 대상):
- FEAT_001: 일반 사용자 이메일 회원가입 정보 처리 (Backend), Must-have
- FEAT_002: 이메일 주소 기등록 여부 검증 (Backend), Must-have
- FEAT_003: 사용자 비밀번호 보안 처리 및 저장 (Security), Must-have
- FEAT_004: 외부 소셜 계정을 활용한 인증 연동 (Backend), Should-have
</few_shot_test>
"""

REVERSE_SYSTEM_PROMPT = """당신은 수석 소프트웨어 리버스 엔지니어입니다.
현재 소스 코드에서 실제로 구현된 기능들을 'FEAT_XXX' 형태의 원자 요구사항으로 역공학하여 추출하세요.

<rules>
1. [절대 준수] 새로운 기능을 상상하지 마세요. 오직 코드에 존재하는 기능만 기술하세요.
2. 모든 기능은 'FEAT_XXX' 형태의 ID를 부여합니다.
3. MoSCoW 우선순위는 코드의 중요도에 따라 부여합니다.
4. 기술 스택(어떤 라이브러리를 썼는지 등)을 언급하지 말고, 순수 비즈니스/시스템 기능 로직(What)만 추출하세요.
</rules>
"""

def requirement_analyzer_node(state: PipelineState) -> Dict[str, Any]:
    sget = make_sget(state)
    logger = get_logger()
    logger.info("=== [Node Entry] requirement_analyzer_node ===")
    logger.info(f"Input Keys: {list(state.keys()) if hasattr(state, 'keys') else 'N/A'}")
    
    api_key = sget("api_key", "")
    model = sget("model", DEFAULT_MODEL)
    idea = sget("input_idea", "") or ""
    ctx = sget("project_context", "") or ""
    action_type = (sget("action_type", "CREATE") or "CREATE").strip().upper()
    system_scan = sget("system_scan", {}) or {}
    
    # 모드에 따른 시스템 프롬프트 선택
    system_prompt = REVERSE_SYSTEM_PROMPT if action_type == "REVERSE_ENGINEER" else SYSTEM_PROMPT
    
    # 컨텍스트 조립
    parts = []
    if idea:
        parts.append(f"<input_idea>\n{idea}\n</input_idea>")
    if ctx:
        parts.append(f"<project_context>\n{ctx}\n</project_context>")
    if system_scan:
        # 역공학 모드 등에서 참조할 기존 분석 정보
        summary = system_scan.get("architecture_assessment", "")
        funcs = system_scan.get("sample_functions", []) or []
        if summary or funcs:
            parts.append(f"<existing_system_analysis>\nSummary: {summary}\nScanned Functions: {len(funcs)}\n</existing_system_analysis>")
            
    user_content = "\n\n".join(parts)
    if not user_content:
        return {"error": "분석할 입력(아이디어 또는 컨텍스트)이 없습니다.", "current_step": "requirement_analyzer"}

    t0 = time.perf_counter()
    try:
        out, usage = call_structured_with_usage(
            api_key=api_key,
            model=model,
            schema=RequirementAnalyzerOutput,
            system_prompt=system_prompt,
            user_msg=user_content,
            max_retries=3,
            temperature=0.1
        )
        latency_ms = int((time.perf_counter() - t0) * 1000)
        
        # 결과 추출 및 변환
        features = [f.model_dump() for f in out.features]
        thinking = out.thinking or "요구사항 원자화 분석 완료"
        
        # 메타데이터 업데이트 (호환성 유지)
        metadata = sget("metadata", {}) or {}
        metadata.update({
            "status": "Success",
            "total_features": len(features),
            "latency_ms": latency_ms,
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0)
        })

        return {
            "raw_requirements": features,  # 기존 하위 호환을 위해 raw_requirements에도 유지
            "features": features,           # 신규 규격
            "metadata": metadata,
            "thinking_log": (sget("thinking_log", []) or []) + [{"node": "requirement_analyzer", "thinking": thinking}],
            "current_step": "requirement_analyzer_done",
            "action_type": action_type
        }

    except Exception as e:
        logger.exception("requirement_analyzer_node failed")
        return {
            "error": f"요구사항 분석 실패: {str(e)}",
            "thinking_log": (sget("thinking_log", []) or []) + [{"node": "requirement_analyzer", "thinking": f"오류 발생: {e}"}],
            "current_step": "error"
        }
