"""
Requirement Analyzer Node (PRJ-CTOR Phase 1)
사용자 아이디어를 원자 단위의 요구사항(FEAT_XXX)으로 분해하고 MoSCoW 우선순위를 부여합니다.
엄격한 요구사항 엔지니어 페르소나를 사용하여 기술 스택 결정을 금지합니다.
"""

import re
import time
from typing import Dict, Any, List

from pipeline.core.state import PipelineState, make_sget
from pipeline.core.utils import call_structured
from pipeline.domain.pm.schemas import RequirementAnalyzerOutput
from pipeline.domain.rag.nodes.project_db import query_project_code
from observability.logger import get_logger
from version import DEFAULT_MODEL


_FEAT_NUMERIC_RE = re.compile(r"^FEAT_(\d{1,4})$")
_FEAT_PREFIX_RE = re.compile(r"^FEAT[_\-\s]*", re.IGNORECASE)


def _normalize_feature_ids(features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """LLM이 반환한 ID를 FEAT_001, FEAT_002, ... 순차 번호로 강제 정규화한다.

    LLM이 'FEAT_청킹' / 'FEAT_login' 같은 비숫자 접미사를 넣은 경우, 접미사를
    살려 `label` 필드로 옮긴다. `deps` 참조는 매핑 테이블로 재작성한다.
    """
    if not features:
        return features

    id_map: Dict[str, str] = {}

    for idx, feat in enumerate(features, start=1):
        new_id = f"FEAT_{idx:03d}"
        original_id = (feat.get("id") or "").strip()
        existing_label = (feat.get("label") or "").strip()

        if original_id:
            if not _FEAT_NUMERIC_RE.match(original_id):
                # 'FEAT_청킹' → '청킹', 'FEAT-검색' → '검색', 'feat_login' → 'login'
                suffix = _FEAT_PREFIX_RE.sub("", original_id).strip(" _-")
                if suffix and not suffix.isdigit() and not existing_label:
                    feat["label"] = suffix
            id_map[original_id] = new_id

        feat["id"] = new_id

    # deps/dependencies 재작성
    for feat in features:
        for deps_key in ("deps", "dependencies"):
            if deps_key in feat and isinstance(feat[deps_key], list):
                feat[deps_key] = [id_map.get(dep, dep) for dep in feat[deps_key]]

    return features

_ID_RULES_BLOCK = """- ID 형식 (절대 규칙):
  - 반드시 'FEAT_' 뒤에 **3자리 0-패딩 숫자**만 붙인다. 예: FEAT_001, FEAT_002, FEAT_003.
  - 한글·영문 키워드 금지: FEAT_청킹, FEAT_인덱싱, FEAT_login 같은 형태는 **절대** 사용하지 않는다.
  - 출력 features 배열의 순서대로 001부터 순차 부여한다.
  - deps(의존 ID 목록)도 동일한 FEAT_001 형식으로만 표기한다.
- 라벨(label):
  - 기능을 한 단어로 식별하고 싶으면 **별도의 'label' 필드**(예: "청킹", "인덱싱")에 작성한다.
  - label은 짧은 한국어 명사 1~2어절로 작성한다.
  - 절대 ID에 라벨을 섞어 쓰지 않는다."""

CREATE_SYSTEM_PROMPT = f"""# 역할: 방어적 요구사항 분석가 (CREATE 모드)

## 목표
사용자 아이디어를 중복 없는 원자 단위 기능(FEAT_001, FEAT_002, ...)으로 분해한다.

## 규칙
- 린(Lean) 기획: 기능 과분할 금지, 유사 기능은 통합한다.
{_ID_RULES_BLOCK}
- 우선순위: MoSCoW(Must / Should / Could / Won't)를 부여한다.
- 기술 결정 금지: 프레임워크·라이브러리·스택을 명시하지 않는다.

## 출력 규약
- thinking: 한국어 핵심 단어 3개 이내 (문장 금지).
- 모든 명세는 한국어로 작성한다.
"""

UPDATE_SYSTEM_PROMPT = f"""# 역할: 증분 요구사항 분석가 (UPDATE 모드)

## 목표
기존 시스템에 추가하거나 변경해야 할 기능을 원자 단위(FEAT_001, FEAT_002, ...)로 분해한다.

## 규칙
- 컨텍스트 활용: 사용자 메시지의 <existing_system_analysis> / <project_context> 블록을 우선 참고하여 기존 기능을 식별한다.
- 중복 회피: 기존에 이미 존재하는 기능은 신규 FEAT로 만들지 않는다.
- 변경 vs 신규 구분: description 앞에 마커를 붙인다 — 신규 추가는 '[신규] ', 기존 기능의 확장·수정은 '[변경] '.
- 영향 신호 전달: thinking은 '마커/영역' 형태의 핵심 단어 2~3개로 작성한다(예: '신규/계정', '변경/검색'). 실제 충돌 해결은 후속 SA 단계의 책임이며, PM은 신호만 남긴다.
- 린(Lean) 기획: 기능 과분할 금지, 유사 기능은 통합한다.
{_ID_RULES_BLOCK}
- 우선순위: MoSCoW(Must / Should / Could / Won't)를 부여한다.
- 기술 결정 금지: 프레임워크·라이브러리·스택을 명시하지 않는다.

## 출력 규약
- thinking: 위 영향 신호 형식을 따른다 (문장 금지).
- 모든 명세는 한국어로 작성한다.
"""

REVERSE_SYSTEM_PROMPT = f"""# 역할: 리버스 엔지니어 (REVERSE_ENGINEER 모드)

## 목표
스캔된 코드베이스에서 실제로 구현된 기능을 FEAT_001, FEAT_002, ... 단위로 추출한다.

## 규칙
- 환각 금지: 코드에 존재하지 않는 기능은 작성하지 않는다.
{_ID_RULES_BLOCK}
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
    rag_status = sget("rag_index_status", {}) or {}

    # 모드에 따른 시스템 프롬프트 선택
    system_prompt = _SYSTEM_PROMPT_BY_MODE.get(action_type, CREATE_SYSTEM_PROMPT)

    # 컨텍스트 조립
    parts = []
    if idea:
        parts.append(f"<input_idea>\n{idea}\n</input_idea>")
    if ctx:
        parts.append(f"<project_context>\n{ctx}\n</project_context>")

    # UPDATE/REVERSE 모드 + RAG 인덱스 존재 시 ChromaDB에서 직접 청크를 검색해 첨부.
    if action_type in ("UPDATE", "REVERSE_ENGINEER") and rag_status.get("has_index"):
        rag_session_id = rag_status.get("session_id") or sget("session_id", "")
        queries: List[str] = []
        if idea:
            queries.append(idea)
        queries.append("데이터 모델 엔티티 ORM 스키마 테이블")
        queries.append("API 엔드포인트 라우터 컨트롤러")
        chunks: List[Dict[str, Any]] = []
        seen_chunk_ids: set[str] = set()
        for q in queries:
            try:
                results = query_project_code(q, session_id=rag_session_id, n_results=4)
            except Exception as e:
                logger.warning(f"[requirement_analyzer] RAG 검색 실패 (q={q[:30]!r}): {e}")
                continue
            for c in results:
                cid = c.get("chunk_id")
                if cid and cid not in seen_chunk_ids:
                    seen_chunk_ids.add(cid)
                    chunks.append(c)
        if chunks:
            snippet_lines = []
            for c in chunks[:8]:
                sim = c.get("similarity", 0)
                snippet_lines.append(
                    f"- {c.get('file_path', '')}::{c.get('func_name', '')} (sim={sim:.2f})\n"
                    f"  {(c.get('content_text', '') or '')[:300]}"
                )
            snippet_block = "\n".join(snippet_lines)
            parts.append(
                f"<existing_system_analysis>\n"
                f"RAG 인덱스(청크 {rag_status.get('chunk_count', 0)}개)에서 검색한 관련 코드:\n"
                f"{snippet_block}\n"
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
        
        # 결과 추출 및 변환 + ID 정규화 (FEAT_001, FEAT_002, ... 순차 부여)
        features = [f.model_dump() for f in out.features]
        features = _normalize_feature_ids(features)
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
