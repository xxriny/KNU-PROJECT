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

## Domain-Specific Mapping Guidelines
- **Auth/Login features** → bcrypt/passlib (password hashing), python-jose/PyJWT (tokens), authlib/OAuth2 (OAuth)
- **Database features** → SQLAlchemy/Prisma (ORM), alembic (migrations), sqlmodel (schema)
- **API features** → FastAPI/Flask/Express (framework), pydantic (validation)
- **Frontend state** → React/Zustand/Redux, axios (HTTP client)

## Anti-Patterns (NEVER map these)
- Auth/Login features → DB modeling tools (e.g., @dbml/core, prisma-dbml-generator, dbdiagram)
- API interface modification features → @dbml/core. **NOTE: @dbml/core is a SQL schema visualization/documentation tool, NOT an API development library.** For API interface or schema changes, use the backend framework (FastAPI, Flask, Express) or validation libraries (Pydantic, zod, marshmallow).
- DB schema features → Auth libraries (e.g., PyJWT, bcrypt)
- Unrelated features → Framework itself (e.g., React is a platform, not a feature-specific library)

## Output Rules
- **thinking (th)**: Describe your design rationale and suitability for the project scale (In Korean).
- **Output Language**: All specification fields must be written in professional Korean.
"""

UPDATE_PROMPT = """# Role: Lead Technical Architect (Update Mode)

## Overview
You are given an existing project's dependency files (<source_code_dependency_evidence>) and new RTM requirements.
Map existing features to detected libraries, and propose appropriate NEW libraries for NEW features.

## Mapping Rules
1. **Existing features**: Map to libraries found in <source_code_dependency_evidence>
2. **New features**: Propose the most appropriate standard library. Use industry best practices.
3. **Domain Suitability**: Match the RIGHT library type to the feature domain.

## Domain-Specific Mapping Guidelines
- **Auth/Login features** → bcrypt/passlib (password hashing), python-jose/PyJWT (tokens), authlib/OAuth2 (OAuth)
- **Database features** → SQLAlchemy/Prisma (ORM), alembic (migrations), sqlmodel (schema)
- **API features** → FastAPI/Flask/Express (framework), pydantic (validation)
- **Frontend state** → React/Zustand/Redux, axios (HTTP client)

## Anti-Patterns (NEVER map these)
- Auth/Login features → DB modeling tools (e.g., @dbml/core, prisma-dbml-generator, dbdiagram)
- API interface modification features → @dbml/core. **NOTE: @dbml/core is a SQL schema visualization/documentation tool, NOT an API development library.** For API interface or schema changes, use the backend framework (FastAPI, Flask, Express) or validation libraries (Pydantic, zod, marshmallow).
- DB schema features → Auth libraries (e.g., PyJWT, bcrypt)
- Unrelated features → Framework itself (e.g., React is a platform, not a feature-specific library)

## Output Rules
- **thinking (th)**: Explain which features used existing deps vs. newly proposed libraries (In Korean).
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
    
    # 2. 소스 디렉토리에서 의존성 파일 직접 읽기 (ChromaDB 없이)
    snippets_text = ""
    source_dir = sget("source_dir", "")
    if source_dir and action_type != "CREATE":
        import os
        dep_files = ["package.json", "requirements.txt", "pyproject.toml", "package-lock.json"]
        found_lines = ["<source_code_dependency_evidence>"]
        for fname in dep_files:
            fpath = os.path.join(source_dir, fname)
            try:
                if os.path.isfile(fpath):
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(8000)
                    found_lines.append(f"File: {fname}\nContent:\n{content}")
            except Exception:
                pass
        if len(found_lines) > 1:
            found_lines.append("</source_code_dependency_evidence>")
            snippets_text = "\n".join(found_lines)

    base_rag_context = "Guardian crawling results below."
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

    # 3. 사용자 메시지 조립
    feature_ids = [f.get("id") for f in features]
    user_msg = f"""{snippets_text}

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
        elif action_type == "UPDATE":
            system_prompt = UPDATE_PROMPT + OUTPUT_GUIDE
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
        
        # 6. 자가 치유 로직 — 누락이 전체의 30% 초과일 때만 2차 LLM 호출
        # (소수 누락은 정상 범주로 처리하여 불필요한 38초 지연 방지)
        mapped_ids = {item.f_id for item in out.m}
        missing_ids = set(feature_ids) - mapped_ids
        heal_threshold = max(1, int(len(feature_ids) * 0.3))

        if missing_ids and len(missing_ids) > heal_threshold:
            logger.warning(f"Detected {len(missing_ids)} missing mappings (>{heal_threshold}). Initiating self-healing...")
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
            if missing_ids:
                logger.info(f"[stack_planner] {len(missing_ids)}개 누락은 허용 범위({heal_threshold}개 이하). 자가치유 생략.")
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
