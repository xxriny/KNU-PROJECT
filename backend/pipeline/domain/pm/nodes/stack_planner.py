"""
Stack Planner Node
분석된 요구사항(Features)을 승인된 기술 스택(RAG)과 매핑하여 기술 설계를 확정합니다.
"기술 스택 가디언" 페르소나를 사용하여 프로젝트의 기술적 일관성을 책임집니다.
"""

from typing import List, Dict, Any, Optional
from pipeline.core.state import PipelineState, make_sget
from pipeline.core.utils import call_structured
from pipeline.domain.pm.schemas import StackPlannerOutput
from observability.logger import get_logger
from version import DEFAULT_MODEL

logger = get_logger()

from pipeline.domain.rag.nodes.project_db import get_session_inventory

logger = get_logger()

# RECOVERY_PROMPT: 분석 및 복구 모드 (설정 파일을 통한 기술 스택 100% 복구)
RECOVERY_PROMPT = """# Role: Strict Technology Forensic Auditor (Recovery Mode)

## [CRITICAL: Source of Truth - Configuration Files ONLY]
**You must ONLY report technologies explicitly declared in the following files. NEVER guess.**
1. **Frontend**: Audit `package.json`'s `dependencies`. 
2. **Backend**: Audit `requirements.txt` or `poetry.lock`.
3. **Internal Modules**: Use `pathlib`, `ast`, `os` ONLY if they are the primary tools for the feature.

## [Uncoupled Technology Inventory (gs)]
- **global_stacks (gs)**: This is your primary inventory. List EVERY package/library found in `package.json` or `requirements.txt` here. 
- Do NOT limit this to what is mapped to RTM. If it's in the config file, it belongs in `gs`.
- For each entry in `gs`, provide the exact file/line as `evidence`.

## [Feature Mapping (m)]
- Map RTM features to the technologies in `gs`. 
- If a feature doesn't have a specific package, map it to the core language/framework (e.g., FastAPI, React).

## [No Guessing / No Beautification]
- **Zero-Tolerance for Hallucination**: Reporting a package based on "typical use" (e.g., guessing `react-router` for navigation) without evidence in config files is a CRITICAL FAILURE.
- **Identify Hidden Stacks**: Look for `@xyflow/react`, `framer-motion`, etc., which are often overlooked but present in config files.

## Output Rules
- **thinking**: List the configuration file (e.g., `package.json` line X) used as evidence for each stack (In Korean).
- **Output Language**: All specification fields must be written in professional Korean.
"""

# CREATION_PROMPT: 신규 설계 모드 (베스트 프랙티스 기반 스택 제안)
CREATION_PROMPT = """# Role: Lead Technical Architect (New Design Mode)

## Overview
Propose the optimal modern technology stack that satisfies the project requirements.

## Selection Principles (Lean & Modern)
1. **YAGNI Principle**: Avoid heavy libraries; select only essential tools.
2. **Modern Standards**: Prioritize stable, industry-standard modern tech stacks.
3. **Domain Suitability**: Map the best libraries to Frontend, Backend, and DB layers.

## Output Rules
- **thinking (th)**: Describe your design rationale and suitability for the project scale (In Korean).
- **Output Language**: All specification fields must be written in professional Korean.
"""

# 공통 출력 규약 (JSON 구조 정의)
OUTPUT_GUIDE = """
## Output Format (JSON)
- **thinking (th)**: Analysis/Design rationale (Korean).
- **stack_mapping (m)**: Map every feature ID (f_id) to the technology used/recommended.
- **global_stacks (gs)**: List ALL technologies detected in the config files (uncoupled from RTM features).
"""

def stack_planner_node(state: PipelineState) -> Dict[str, Any]:
    sget = make_sget(state)
    logger.info("=== [Node Entry] stack_planner_node ===")
    
    # 1. 기본 데이터 수집
    current_loop = sget("loop_count", 0)
    features = sget("features", [])
    action_type = sget("action_type", "CREATE")
    run_id = sget("run_id", sget("session_id", "stack_session"))
    
    # 2. 인벤토리 및 RAG 컨텍스트 준비
    inventory = {}
    snippets_text = ""
    if action_type != "CREATE":
        search_session_id = sget("session_id", run_id)
        try:
            inventory = get_session_inventory(search_session_id)
            
            # [HYBRID EXTRACTION]
            # Priority 1: Deterministic Targeting (via Forensic Profiler)
            from pipeline.domain.rag.nodes.project_db import get_file_chunks, query_project_code
            
            seen_ids = set()
            all_chunks = []
            
            # 1. ForensicProfiler 결과 활용
            forensic_profile = sget("forensic_profile", {})
            
            target_files = []
            if forensic_profile:
                # [DYNAMIC] CONFIG 및 DB 정보를 합쳐 기술 스택의 결정적 증거 확보
                target_files = [path for path, role in forensic_profile.items() if role in ("CONFIG", "DB", "UTIL")]
                logger.info(f"[stack_planner] Priority 1 (Forensic): {len(target_files)} config/db files.")
            else:
                # [MINIMAL FALLBACK]
                config_patterns = ["package", "requirements", "lock", "docker", "setup", "pyproject"]
                target_files = [path for path in inventory.keys() if any(p in path.lower() for p in config_patterns)]
            
            for t_file in target_files:
                direct_chunks = get_file_chunks(t_file, session_id=search_session_id)
                for c in direct_chunks:
                    cid = c.get("chunk_id")
                    if cid and cid not in seen_ids:
                        seen_ids.add(cid)
                        all_chunks.append(c)

            # Priority 2: Semantic RAG Search (supplementary)
            queries = ["requirements.txt dependencies version package.json", "database connection string config"]
            for q in queries:
                try:
                    # [FIX] NO LIMITS: Increase n_results for update/reverse modes
                    n_res = 50 if action_type in ("UPDATE", "REVERSE_ENGINEER") else 15
                    res_chunks = query_project_code(q, session_id=search_session_id, n_results=n_res, api_key=sget("api_key", ""))
                    for c in res_chunks:
                        cid = c.get("chunk_id")
                        if cid and cid not in seen_ids:
                            seen_ids.add(cid)
                            all_chunks.append(c)
                except Exception as e:
                    logger.warning(f"[stack_planner] Semantic RAG failed: {e}")
            
            if all_chunks:
                lines = ["<source_code_dependency_evidence>"]
                limit = 1000 if action_type in ("UPDATE", "REVERSE_ENGINEER") else 60
                for c in all_chunks[:limit]:
                    lines.append(f"File: {c.get('file_path')}\nContent: {c.get('content_text', '')}")
                lines.append("</source_code_dependency_evidence>")
                snippets_text = "\n".join(lines)
        except Exception as e:
            logger.warning(f"[stack_planner] RAG search failed: {e}")

    base_rag_context = sget("stack_rag_context", "No approved stacks found in RAG.")
    guardian_out = sget("guardian_output", {})
    new_knowledge = ""
    if guardian_out.get("status") == "APPROVED" and guardian_out.get("final_data"):
        data = guardian_out["final_data"]
        new_knowledge = f"\n[NEWLY DISCOVERED] {data['name']}: {data['description']} (v{data['version']})"
    
    integrated_context = base_rag_context + new_knowledge
    
    if not features:
        return {
            "stack_planner_output": {"thinking": "분석할 기능이 없습니다.", "stack_mapping": []},
            "loop_count": current_loop + 1
        }

    # 3. 인벤토리 포맷팅
    inventory_str = ""
    if inventory:
        lines = ["<project_inventory>"]
        for p, items in sorted(inventory.items()):
            # [FIX] Remove truncation to see all functions
            lines.append(f"- {p}: {[it.get('name') for it in items]}")
        lines.append("</project_inventory>")
        inventory_str = "\n".join(lines)

    # 4. 사용자 메시지 조립
    feature_ids = [f.get("id") for f in features]
    user_msg = f"""{inventory_str}
{snippets_text}

### [요구사항 기능 목록 (총 {len(features)}개)]
{features}

### [APPROVED_STACK_FROM_RAG]
{integrated_context}

위의 <source_code_dependency_evidence>와 <project_inventory>를 가장 우선적인 진실(Source of Truth)로 삼아 각 기능에 대한 기술 스택을 매핑하십시오.
증거 자료에 없는 기술을 임의로 상상해서 답변하는 것은 금지됩니다.
"""

    try:
        # 모드에 따른 시스템 프롬프트 선택
        if action_type == "CREATE":
            system_prompt = CREATION_PROMPT + OUTPUT_GUIDE
        else:
            system_prompt = RECOVERY_PROMPT + OUTPUT_GUIDE

        res = call_structured(
            api_key=sget("api_key", ""),
            model=sget("model", DEFAULT_MODEL),
            schema=StackPlannerOutput,
            system_prompt=system_prompt,
            user_msg=user_msg,
            compress_prompt=False, # 정밀도 유지를 위해 압축 비활성화
            temperature=0.1
        )
        out = res.parsed
        total_retries = res.retry_count
        
        # 6. 자가 치유 로직 (누락 체크)
        mapped_ids = {item.f_id for item in out.m}
        missing_ids = set(feature_ids) - mapped_ids
        
        if missing_ids:
            logger.warning(f"Detected {len(missing_ids)} missing mappings. Initiating self-healing...")
            missing_features = [f for f in features if f.get("id") in missing_ids]
            healing_user_msg = f"다음 누락된 기능들에 대해 추가로 기술 스택을 매핑하십시오:\n{missing_features}"
            
            res_heal = call_structured(
                api_key=sget("api_key", ""),
                model=sget("model", DEFAULT_MODEL),
                schema=StackPlannerOutput,
                system_prompt=system_prompt,
                user_msg=healing_user_msg,
                compress_prompt=False,
            )
            out_heal = res_heal.parsed
            total_retries += res_heal.retry_count
            
            # 병합 및 중복 제거
            final_mapping_dict = {item.f_id: item for item in out.m + out_heal.m if item.f_id in feature_ids}
            out.m = list(final_mapping_dict.values())
        else:
            final_mapping_dict = {item.f_id: item for item in out.m if item.f_id in feature_ids}
            out.m = list(final_mapping_dict.values())

        # 7. 크롤러 입력 생성
        pending_items = [item for item in out.m if item.status == "PENDING_CRAWL"]
        next_crawler_inputs = [{"target": "npm" if item.dom == "Frontend" else "pypi", "query": item.query or item.pkg} for item in pending_items]

        return {
            "stack_planner_output": out.model_dump(),
            "next_crawler_inputs": next_crawler_inputs,
            "loop_count": current_loop + 1,
            "stack_rag_context": integrated_context, 
            "thinking_log": (sget("thinking_log", []) or []) + [{"node": "stack_planner", "thinking": out.th}],
            "total_retries": sget("total_retries", 0) + total_retries
        }
        
    except Exception as e:
        logger.exception("stack_planner_node failure")
        return {"error": f"Stack Planning 중 오류 발생: {e}", "current_step": "error"}
