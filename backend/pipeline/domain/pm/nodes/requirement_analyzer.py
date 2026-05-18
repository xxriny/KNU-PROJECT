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
# UPDATE 모드 후처리에서 description 앞에 남은 LLM 마커를 흡수하기 위함.
_STATUS_PREFIX_RE = re.compile(r"^\s*\[\s*(신규|수정|변경|유지)\s*\]\s*", re.IGNORECASE)
_STATUS_ALIASES = {
    "신규": "신규",
    "수정": "수정",
    "변경": "수정",  # UPDATE 프롬프트 구버전 호환
    "유지": "유지",
}


def _normalize_feature_ids(
    features: List[Dict[str, Any]],
    preserve_ids: bool = False,
    start_index: int = 1,
) -> List[Dict[str, Any]]:
    """LLM이 반환한 ID를 FEAT_001, FEAT_002, ... 순차 번호로 정규화한다.

    Args:
        preserve_ids: True면 이미 `FEAT_NNN` 형식인 ID는 보존하고, 그렇지 않은 항목만
            `start_index`부터 새 번호를 부여한다. UPDATE 모드에서 기존 항목 위치/ID를
            유지하기 위해 사용한다.
        start_index: preserve_ids=True일 때 새로 부여할 첫 번호.
    """
    if not features:
        return features

    id_map: Dict[str, str] = {}

    if preserve_ids:
        used_numbers: set[int] = set()
        for feat in features:
            original_id = (feat.get("id") or "").strip()
            m = _FEAT_NUMERIC_RE.match(original_id)
            if m:
                used_numbers.add(int(m.group(1)))
        next_idx = start_index
        for feat in features:
            original_id = (feat.get("id") or "").strip()
            m = _FEAT_NUMERIC_RE.match(original_id)
            if m:
                # 기존 ID 보존
                id_map[original_id] = original_id
                continue
            # 비숫자 접미사 → label로 흡수
            existing_label = (feat.get("label") or "").strip()
            if original_id and not existing_label:
                suffix = _FEAT_PREFIX_RE.sub("", original_id).strip(" _-")
                if suffix and not suffix.isdigit():
                    feat["label"] = suffix
            # 사용 중이 아닌 다음 번호 찾기
            while next_idx in used_numbers:
                next_idx += 1
            new_id = f"FEAT_{next_idx:03d}"
            used_numbers.add(next_idx)
            if original_id:
                id_map[original_id] = new_id
            feat["id"] = new_id
            next_idx += 1
    else:
        for idx, feat in enumerate(features, start=1):
            new_id = f"FEAT_{idx:03d}"
            original_id = (feat.get("id") or "").strip()
            existing_label = (feat.get("label") or "").strip()
            if original_id:
                if not _FEAT_NUMERIC_RE.match(original_id):
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


def _absorb_status_prefix(feat: Dict[str, Any]) -> None:
    """description에 남은 `[신규]/[수정]/[변경]/[유지]` 프리픽스를 떼서 change_status로 흡수.

    LLM이 새 스키마(`change_status` 필드)를 채워도 안전하고, 구버전 프리픽스만
    채워도 안전하다. 이미 change_status가 채워져 있으면 우선한다.
    """
    desc = feat.get("desc", "") or ""
    m = _STATUS_PREFIX_RE.match(desc)
    if m:
        feat["desc"] = _STATUS_PREFIX_RE.sub("", desc, count=1).lstrip()
        prefix_status = _STATUS_ALIASES.get(m.group(1).strip())
        if prefix_status and not (feat.get("change_status") or "").strip():
            feat["change_status"] = prefix_status
    # change_status 정규화 (LLM이 영어/한자 등 변형으로 채울 수 있음)
    cs = (feat.get("change_status") or "").strip()
    if cs:
        feat["change_status"] = _STATUS_ALIASES.get(cs, cs)


def _reorder_for_update(
    features: List[Dict[str, Any]],
    previous_features: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """UPDATE 결과를 기존 위치 보존 + 신규 항목은 뒤에 append 순서로 재정렬한다.

    매칭 우선순위: id → label → desc 첫 40자(정규화).
    """
    if not features:
        return features
    if not previous_features:
        return features

    def _key_label(s: str) -> str:
        return (s or "").strip().lower()

    def _key_desc(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").strip())[:40].lower()

    prev_ids = [(p.get("id") or "").strip() for p in previous_features]
    prev_id_set = {pid for pid in prev_ids if pid}
    label_to_prev_idx: Dict[str, int] = {}
    desc_to_prev_idx: Dict[str, int] = {}
    for i, p in enumerate(previous_features):
        lab = _key_label(p.get("label") or "")
        if lab and lab not in label_to_prev_idx:
            label_to_prev_idx[lab] = i
        dk = _key_desc(p.get("desc") or p.get("description") or "")
        if dk and dk not in desc_to_prev_idx:
            desc_to_prev_idx[dk] = i

    position_of: Dict[int, int] = {}  # feature_index → prev_position
    new_features: List[int] = []

    for fi, feat in enumerate(features):
        fid = (feat.get("id") or "").strip()
        matched_prev: int | None = None
        if fid and fid in prev_id_set:
            matched_prev = prev_ids.index(fid)
        if matched_prev is None:
            lab = _key_label(feat.get("label") or "")
            if lab and lab in label_to_prev_idx:
                matched_prev = label_to_prev_idx[lab]
        if matched_prev is None:
            dk = _key_desc(feat.get("desc") or "")
            if dk and dk in desc_to_prev_idx:
                matched_prev = desc_to_prev_idx[dk]
        if matched_prev is not None:
            position_of[fi] = matched_prev
        else:
            new_features.append(fi)

    # 기존 위치 기준으로 정렬, 같은 prev_position 충돌 시 원래 LLM 순서로 안정 정렬
    matched = sorted(position_of.items(), key=lambda kv: (kv[1], kv[0]))
    ordered = [features[fi] for fi, _ in matched] + [features[fi] for fi in new_features]
    return ordered

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
Integrate new user requests (<input_idea>) while preserving the existing RTM (<existing_features>) item-by-item.
You will be given the previous RTM in <existing_features>. Each entry has `id`, `label`, `desc`.

## ABSOLUTE RULES (Incremental Update — NOT a Rewrite)
1. **Preserve Existing IDs and Order**:
   - Every entry from <existing_features> MUST appear in the output with its **exact same `id`** (e.g., if the input has FEAT_007, return FEAT_007 — do not renumber).
   - The output must contain every existing feature unless it is being explicitly removed by the request.
   - You may reword `desc` only if the existing feature is genuinely affected by the change request.
2. **Mark Each Feature's change_status** (set the `change_status` field, NOT a description prefix):
   - `"신규"` — a feature that did not exist in <existing_features> (introduced by <input_idea>).
   - `"수정"` — an existing feature whose description/scope is changed by <input_idea>.
   - `"유지"` — an existing feature unaffected by the change request.
3. **New Feature IDs**:
   - For `change_status="신규"` only, use FEAT_NNN numbers **strictly greater** than the maximum existing FEAT_NNN. Never reuse a removed ID.
4. **No Reordering of Existing Items**:
   - Keep existing features in their original order. Append `"신규"` features at the END.
5. **No [신규]/[수정]/[유지] prefix inside `desc`** — that information belongs in `change_status`.

## Granularity (carry over from CREATE rules)
- Do NOT summarize multiple files into one FEAT.
- Base everything 100% on actual code facts and the change request.
{_ID_RULES_BLOCK}

## Output Rules
- **thinking**: Briefly list which existing FEAT_IDs you classified as 유지/수정 and which new FEAT_IDs you added (In Korean).
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
    previous_features = sget("previous_features", []) or []

    # 모드에 따른 시스템 프롬프트 선택
    system_prompt = _SYSTEM_PROMPT_BY_MODE.get(action_type, CREATE_SYSTEM_PROMPT)

    # 컨텍스트 조립
    parts = []
    if idea:
        parts.append(f"<input_idea>\n{idea}\n</input_idea>")
    if ctx:
        parts.append(f"<project_context>\n{ctx}\n</project_context>")

    # UPDATE 모드 한정: 이전 RTM을 구조화된 형태로 명시 주입
    if action_type == "UPDATE" and previous_features:
        existing_lines = ["<existing_features>"]
        for pf in previous_features:
            if not isinstance(pf, dict):
                continue
            fid = (pf.get("id") or pf.get("feature_id") or pf.get("REQ_ID") or "").strip()
            label = (pf.get("label") or "").strip()
            desc = (
                pf.get("desc")
                or pf.get("description")
                or ""
            ).strip()
            if not fid:
                continue
            existing_lines.append(
                f'- id={fid} | label="{label}" | desc="{desc}"'
            )
        existing_lines.append("</existing_features>")
        if len(existing_lines) > 2:
            parts.append("\n".join(existing_lines))

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
        
        # 결과 추출 및 변환
        features = [f.model_dump() for f in out.features]

        if action_type == "UPDATE" and previous_features:
            # UPDATE 모드: 기존 ID 보존, 신규 항목만 max(existing)+1부터 번호 부여
            existing_max = 0
            for pf in previous_features:
                if isinstance(pf, dict):
                    m = _FEAT_NUMERIC_RE.match((pf.get("id") or "").strip())
                    if m:
                        existing_max = max(existing_max, int(m.group(1)))
            features = _normalize_feature_ids(
                features, preserve_ids=True, start_index=existing_max + 1
            )
            # 프리픽스 흡수 + change_status 정규화
            for f in features:
                _absorb_status_prefix(f)
            # 위치 보존: 기존 항목 원 순서 → 신규는 뒤에
            features = _reorder_for_update(features, previous_features)
        else:
            features = _normalize_feature_ids(features)
            for f in features:
                # CREATE/REVERSE에서는 change_status를 비워둠 (프리픽스가 있더라도 제거)
                _absorb_status_prefix(f)
                f["change_status"] = ""

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
