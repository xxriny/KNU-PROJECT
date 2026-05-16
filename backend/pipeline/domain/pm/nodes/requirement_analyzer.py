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

# ID 형식 정의 (절대 규칙): FEAT_001 형식 강제
_ID_RULES_BLOCK = """- ID Format (Absolute Rule):
  - Use 'FEAT_' followed by a **3-digit zero-padded number**. E.g., FEAT_001, FEAT_002.
  - Never use keywords in IDs (e.g., FEAT_Login is FORBIDDEN).
- Label:
  - Write a short identifier in the 'label' field (e.g., "Login", "Chunking").
  - Use 1-2 Korean nouns for labels."""

# CREATE 모드: 사용자의 아이디어를 바탕으로 새로운 요구사항 명세를 설계하는 프롬프트
CREATE_SYSTEM_PROMPT = f"""# Role: Lead Requirement Engineer (CREATE Mode)

## Overview
Analyze user ideas and decompose them into atomic, technically implementable features (FEAT_XXX).
Your goal is to create specifications detailed enough for immediate development.

## Guidelines
1. **File-to-Feature Forensic Mapping (STRICT)**: 
   - Every major source file identified in the `<project_inventory>` MUST correspond to at least one unique FEAT ID. 
   - **DO NOT GROUP**: For example, `folder_connector.py` (File Scan) and `ast_scanner.py` (AST Analysis) MUST be separate FEATs. Grouping them is a CRITICAL FAILURE.
   - The total number of FEATs should be proportional to the number of source files. For a project with 50+ files, expect 15-30 FEATs.
2. **Atomic Logic Rule**: 
   - Each FEAT must describe only ONE atomic action. 
   - If a description contains multiple verbs or conjunctions (and, &, 및, ~하고), you MUST split it into multiple IDs.
3. **Evidence-Based Density**:
   - Use the `<project_inventory>` as a checklist. If you miss a file, you missed a feature.
   - Do NOT summarize. Every technical nuance (e.g., specific algorithms like LLMLingua, specific databases like ChromaDB) deserves its own FEAT.

## Output Rules
- **thinking**: Compare your FEAT list against the `<project_inventory>`. Did you group any files? If so, ungroup them now. (In Korean).
- **Output Language**: All specification fields must be written in professional Korean.
"""

# UPDATE 모드: 기존 코드를 보존하면서 신규 아이디어를 통합하는 하이브리드 프롬프트
UPDATE_SYSTEM_PROMPT = f"""# Role: Incremental Design Expert (UPDATE Mode)

## Overview
Integrate new user requests (<input_idea>) while maintaining 1:1 mapping with the existing system (<project_inventory>, <existing_system_analysis>).

## Guidelines (Hybrid Two-Track)
1. **[Existing Features] (Literal Mapping & No Compression)**:
   - Identify existing code with **high granularity**. Do not summarize multiple files into one FEAT.
   - Base everything 100% on actual file names and code facts. 
   - No Hallucination, but also **No Over-summarization**.
2. **[New Features] (Detailed Design)**:
   - For new requirements, design detailed FEATs instead of one large block.
3. **Change Markers**: 
   - New features: Prefix description with **'[신규] '**.
   - Modified existing features: Prefix description with **'[변경] '**.
   - Unchanged existing features: Prefix description with **'[유지] '**.
{_ID_RULES_BLOCK}

## Output Rules
- **thinking**: Justify the granularity level and mapping evidence (In Korean).
- **Output Language**: All specification fields must be written in professional Korean.
"""

# REVERSE 모드: 현재 구현된 코드를 바탕으로 기능 지도(RTM)를 100% 복구하는 프롬프트
REVERSE_SYSTEM_PROMPT = f"""# Role: Strict Software Reverse Engineer (REVERSE_ENGINEER Mode)

## Overview
Recover a high-precision functional map (RTM) from the CURRENTLY IMPLEMENTED system.

## Guidelines
1. **High-Precision Recovery (No Compression)**: 
   - DO NOT group different modules or functions. If `chunker.py` and `retriever.py` exist, they must be separate FEATs.
   - Recover the specification at the **function/class level** if they represent distinct technical features.
2. **Zero-Hallucination**: 
   - If it's not in the code, it's not in the RTM.
3. **1:1 Evidence Mapping**: 
   - Every FEAT must trace to a specific, granular code location.
{_ID_RULES_BLOCK}

## Output Rules
- **thinking**: Verify that each FEAT is a single technical unit and not a summary of multiple features (In Korean).
- **Output Language**: All specification fields must be written in professional Korean.
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

    # UPDATE/REVERSE_ENGINEER 모드: source_dir에서 직접 파일 구조 스캔 (ChromaDB 없이)
    source_dir = sget("source_dir", "") or ""
    if action_type != "CREATE" and source_dir:
        import os as _os
        inventory_lines = ["<project_inventory>"]
        file_count = 0
        for root, dirs, files in _os.walk(source_dir):
            # 불필요한 디렉토리 건너뜀
            dirs[:] = [d for d in dirs if d not in ("node_modules", ".git", "__pycache__", ".venv", "dist", "build")]
            for fname in files:
                if fname.endswith((".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java")):
                    rel_path = _os.path.relpath(_os.path.join(root, fname), source_dir)
                    inventory_lines.append(f"- {rel_path}")
                    file_count += 1
                    if file_count >= 200:
                        break
            if file_count >= 200:
                break
        if file_count > 0:
            inventory_lines.append("</project_inventory>")
            parts.append("\n".join(inventory_lines))
            
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
            compress_prompt=False # 인벤토리 유실 방지를 위해 압축 비활성화
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
