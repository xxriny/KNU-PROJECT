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

CREATE_SYSTEM_PROMPT = """# 역할: 방어적 요구사항 분석가 (CREATE 모드)

## 목표
사용자 아이디어를 중복 없는 원자 단위 기능(FEAT_XXX)으로 분해한다.

## 규칙
- 린(Lean) 기획: 기능 과분할 금지, 유사 기능은 통합한다.
- ID 형식: 'FEAT_XXX' 형식을 고수한다.
- 우선순위: MoSCoW(Must / Should / Could / Won't)를 부여한다.
- 기술 결정 금지: 프레임워크·라이브러리·스택을 명시하지 않는다.

## 출력 규약
- thinking: 한국어 핵심 단어 3개 이내 (문장 금지).
- 모든 명세는 한국어로 작성한다.
"""

UPDATE_SYSTEM_PROMPT = """# 역할: 증분 요구사항 분석가 (UPDATE 모드)

## 목표
기존 시스템에 추가하거나 변경해야 할 기능을 원자 단위(FEAT_XXX)로 분해한다.

## 규칙
- 컨텍스트 활용: 사용자 메시지의 <existing_system_analysis> / <project_context> 블록을 우선 참고하여 기존 기능을 식별한다.
- 중복 회피: 기존에 이미 존재하는 기능은 신규 FEAT로 만들지 않는다.
- 변경 vs 신규 구분: description 앞에 라벨을 붙인다 — 신규 추가는 '[신규] ', 기존 기능의 확장·수정은 '[변경] '.
- 영향 신호 전달: thinking은 '라벨/영역' 형태의 핵심 단어 2~3개로 작성한다(예: '신규/계정', '변경/검색'). 실제 충돌 해결은 후속 SA 단계의 책임이며, PM은 신호만 남긴다.
- 린(Lean) 기획: 기능 과분할 금지, 유사 기능은 통합한다.
- ID 형식: 'FEAT_XXX' 형식을 고수한다.
- 우선순위: MoSCoW(Must / Should / Could / Won't)를 부여한다.
- 기술 결정 금지: 프레임워크·라이브러리·스택을 명시하지 않는다.

## 출력 규약
- thinking: 위 영향 신호 형식을 따른다 (문장 금지).
- 모든 명세는 한국어로 작성한다.
"""

REVERSE_SYSTEM_PROMPT = """# 역할: 리버스 엔지니어 (REVERSE_ENGINEER 모드)

## 목표
스캔된 코드베이스에서 실제로 구현된 기능을 FEAT_XXX 단위로 추출한다.

## 규칙
- 환각 금지: 코드에 존재하지 않는 기능은 작성하지 않는다.
- ID 형식: 'FEAT_XXX' 형식을 고수한다.
- 명세 범위: 비즈니스 로직(What) 위주로 기술한다. 기술 스택·프레임워크 식별자는 제외한다.

## 출력 규약
- thinking: 한국어로 핵심 추론 근거를 상세히 기술한다.
- 모든 분석 내용은 한국어로 작성한다.
"""

_SYSTEM_PROMPT_BY_MODE = {
    "CREATE": CREATE_SYSTEM_PROMPT,
    "UPDATE": UPDATE_SYSTEM_PROMPT,
    "REVERSE_ENGINEER": REVERSE_SYSTEM_PROMPT,
}

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
    system_prompt = _SYSTEM_PROMPT_BY_MODE.get(action_type, CREATE_SYSTEM_PROMPT)
    
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
    else:
        # RAG Ingest 결과 확인 (Stage 1 대체 대응)
        rag_out = sget("rag_ingest_output", {}) or {}
        if rag_out:
            parts.append(
                f"<existing_system_analysis>\n"
                f"Status: Code base indexed via RAG\n"
                f"Chunks Ingested: {rag_out.get('chunks_ingested', 0)}\n"
                f"</existing_system_analysis>"
            )
            
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
            temperature=0.1,
            compress_prompt=True # Phase 3: Prompt Compression enabled
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
