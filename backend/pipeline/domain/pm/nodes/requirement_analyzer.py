"""
Requirement Analyzer Node (PRJ-CTOR Phase 1)
사용자 아이디어를 원자 단위의 요구사항(FEAT_XXX)으로 분해하고 MoSCoW 우선순위를 부여합니다.
엄격한 요구사항 엔지니어 페르소나를 사용하여 기술 스택 결정을 금지합니다.
"""

import time
from typing import Dict, Any

from pipeline.core.state import PipelineState, make_sget
from pipeline.core.utils import call_structured
from pipeline.domain.pm.schemas import RequirementAnalyzerOutput
from observability.logger import get_logger
from version import DEFAULT_MODEL

SYSTEM_PROMPT = """# 역할: 방어적 요구사항 분석가
## 목표: 시스템 안정성을 위해 '엣지 케이스'를 30% 이상 포함한 원자 단위 기능 도출.
## 규칙:
- ID: 'FEAT_XXX' 형식 고수.
- MoSCoW: 보안/안정성/유효성 검사는 반드시 Must-have(MH)로 분류.
- 방어적 설계: 3가지 실패 시나리오를 상상하고 이를 방어하는 기능 정의.
- 명세: 유효성 검사, 타임아웃, 재시도, 데이터 부재 대응 포함. 기술 스택 언급 금지.
- 언어 규칙: 모든 분석 내용과 사고 과정(thinking)은 반드시 한국어로 상세히 작성하십시오.
## 예시:
- 입력: "사용자 로그인"
  - ❌ Bad: 로그인 로직만 나열.
  - ✅ Good: 로그인(MH), 계정잠금(MH), 데이터검증(MH), 세션정책(SH).
"""

REVERSE_SYSTEM_PROMPT = """# 역할: 리버스 엔지니어
## 목표: 코드에서 'FEAT_XXX' 형태의 요구사항 추출. 환각 금지.
## 규칙:
- ID: 'FEAT_XXX' 형식 고수.
- 원칙: 오직 코드에 존재하는 기능만 기술.
- 명세: 순수 비즈니스 로직(What) 위주. 기술 스택 제외.
- 언어 규칙: 모든 분석 내용과 사고 과정(thinking)은 반드시 한국어로 상세히 작성하십시오.
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
        res = call_structured(
            api_key=api_key,
            model=model,
            schema=RequirementAnalyzerOutput,
            system_prompt=system_prompt,
            user_msg=user_content,
            max_retries=3,
            temperature=0.1
        )
        out = res.parsed
        usage = res.usage
        retry_count = res.retry_count
        latency_ms = int((time.perf_counter() - t0) * 1000)
        
        # 결과 추출 및 변환
        features = [f.model_dump() for f in out.features]
        thinking = out.th or "요구사항 원자화 분석 완료"
        
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
            "total_retries": sget("total_retries", 0) + retry_count,
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
