"""
SA Unified Modeler Node — 컴포넌트를 기반으로 API + DB 스키마를 동시 설계
"""
from __future__ import annotations
from pipeline.core.node_base import pipeline_node, NodeContext
from pipeline.core.utils import call_structured
from pipeline.core.cache_manager import cache_manager
from pipeline.domain.sa.schemas import SAUnifiedModelerOutput
from observability.logger import get_logger

from pipeline.domain.rag.nodes.project_db import query_project_code, get_session_inventory

logger = get_logger()

# RECOVERY_PROMPT: 분석 및 복구 모드 (지능형 아키텍처 복원)
RECOVERY_PROMPT = """# Role: Intelligent System Architecture Restorer

## [GOAL: BEST-EFFORT RECONSTRUCTION]
Your goal is to reconstruct the API and DB architecture of the project. 
Even if the provided `<existing_code_forensic_evidence>` is sparse, use the `<project_inventory>` (file names, function names) to infer the structure. 

## 1. API Reconstruction:
- **Direct Evidence**: Use snippets like `@app.get` if available.
- **Inference from Inventory**: If snippets are missing, look at files like `rest_handler.py`, `router.py`, or `main.py`. 
- If a file has a function `create_user`, infer an endpoint like `POST /user` or `POST /api/user`. 
- **Be Bold**: It is better to provide a "likely" API list than an empty one.

## 2. Database Reconstruction:
- **Direct Evidence**: Use `Column`, `Table`, or `get_or_create_collection`.
- **Inference from Stack**: If the stack is 'ChromaDB', infer collections based on the main entities (e.g., `project_code`, `chat_history`).
- If you see `models.py` with `User` class, reconstruct a `users` table with standard columns (id, name, etc.).

## Output Rules
- **thinking**: Explain your reconstruction logic—whether it was direct evidence or inference from file names (In Korean).
- **Output Language**: All specification fields must be written in professional Korean.
- **NO EMPTY RESULTS**: Unless the project is completely empty, provide the most plausible API/DB map based on the available technical clues.
"""

# CREATION_PROMPT: 신규 설계 모드 (요구사항을 바탕으로 베스트 프랙티스 설계)
CREATION_PROMPT = """# Role: Senior System Architect (New Design Mode)

## Overview
Analyze requirements (RTM) and design scalable, standard API and DB schemas. Since there is no existing code, follow industry best practices.

## Design Principles
1. **Standard Naming**: Use clear, intuitive snake_case.
2. **RESTful Standard**: Define resource-based URIs and appropriate HTTP methods.
3. **Data Normalization**: Minimize redundancy and ensure integrity.

## Output Rules
- **thinking**: Describe the logical rationale behind your design (In Korean).
- **Output Language**: All specification fields must be written in professional Korean.
"""

# 공통 출력 규약 (JSON 구조 정의)
OUTPUT_GUIDE = """
## Output Format (JSON)
- **thinking (th)**: Critical logic and evidence (Korean).
- **definitions (df)**: Mapping between Frontend components and APIs.
- **apis (ap)**: Endpoints (ep), Request schema (rq), Response schema (rs).
- **tables (tb)**: Table name (nm) and Columns (cl).
"""


def _build_user_message(components: list, rtm: list, inventory: dict, action_type: str, snippets: str = "") -> str:
    p_rtm = "\n".join(f"{r.get('feature_id', r.get('id'))}:{r.get('description', r.get('desc'))}" for r in rtm)

    def _g(obj, k):
        if hasattr(obj, 'get'):
            return obj.get(k) or obj.get(k.replace('nm', 'name').replace('rl', 'role').replace('rt', 'rtms'))
        return getattr(obj, k, None) or getattr(obj, k.replace('nm', 'name').replace('rl', 'role').replace('rt', 'rtms'), None)

    p_comp = "\n".join(f"{_g(c, 'nm')}:{_g(c, 'rl')}:{_g(c, 'rt')}" for c in components)
    
    inventory_lines = []
    if inventory:
        inventory_lines.append("<project_inventory>")
        for path, items in sorted(inventory.items()):
            formatted_items = [f"{it.get('name')}({it.get('summary', '')[:50]})" for it in items[:10]]
            inventory_lines.append(f"- {path}: {formatted_items}")
        inventory_lines.append("</project_inventory>")
    
    # Select final instruction based on mode
    if action_type == "CREATE":
        final_instruction = "[Instruction] Based on the components and RTM above, perform a professional API and DB design that perfectly satisfies the requirements."
    elif action_type == "UPDATE":
        final_instruction = "[Instruction/Hybrid] For parts already implemented in the inventory/snippets, extract them 100% as-is (Literal Mapping). For NEW requirements (RTM), design new API/DB structures following the existing architecture patterns. Integrate both."
    else:
        final_instruction = "[Instruction/CRITICAL] Based ONLY on the facts in the inventory and snippets, extract the 'actually existing' API and DB structures 100% as-is. NEVER hallucinate missing parts. No Hallucination!"

    return (
        f"{' '.join(inventory_lines)}\n\n"
        f"{snippets}\n\n"
        f"Comp:\n{p_comp}\n"
        f"RTM:\n{p_rtm}\n\n"
        f"{final_instruction}"
    )


@pipeline_node("sa_unified_modeler")
def sa_unified_modeler_node(ctx: NodeContext) -> dict:
    sget = ctx.sget
    logger.info("=== [Node Entry] sa_unified_modeler_node ===")

    components = sget("component_scheduler_output", {}).get("components", [])
    rtm = (sget("merged_project", {}).get("plan", {}).get("requirements_rtm", []) or 
           sget("features", []) or sget("pm_bundle", {}).get("data", {}).get("rtm", []))
    run_id = sget("run_id", sget("session_id", "sa_session"))
    action_type = sget("action_type", "CREATE")

    inventory = {}
    snippets_text = ""
    
    if action_type != "CREATE":
        # 1. Get Inventory
        try:
            inventory = get_session_inventory(run_id)
        except:
            pass
            
        # 2. Enhanced RAG Search (Forensic Queries)
        try:
            # SQL, NoSQL, and VectorDB patterns
            queries = [
                "SQLAlchemy Base declarative_base Column ForeignKey",
                "FastAPI APIRouter rest_router app.get app.post route",
                "ChromaDB Collection get_or_create_collection PersistentClient",
                "Pydantic BaseModel schema Field",
                "create table insert into .sql",
                "def get_config scan_folder_endpoint analyze idea_chat", # Actual NAVIGATOR API hints
                "class CodeChunk(BaseModel) metadatas metadatas" # DB internal hints
            ]
            all_chunks = []
            seen_ids = set()
            
            # [CRITICAL FIX] Use the correct session_id (folder hash) to search project_db, NOT run_id
            search_session_id = sget("session_id", run_id)
            
            for q in queries:
                res_chunks = query_project_code(q, session_id=search_session_id, n_results=15, api_key=ctx.api_key)
                for c in res_chunks:
                    cid = c.get("chunk_id")
                    if cid and cid not in seen_ids:
                        seen_ids.add(cid)
                        all_chunks.append(c)
            
            if all_chunks:
                lines = ["<existing_code_forensic_evidence>"]
                for c in all_chunks[:25]:
                    lines.append(f"File: {c.get('file_path')}\nContent: {c.get('content_text', '')[:1000]}")
                lines.append("</existing_code_forensic_evidence>")
                snippets_text = "\n".join(lines)
            else:
                logger.warning(f"[sa_unified_modeler] ZERO chunks found for session_id={search_session_id}. RAG index might be empty.")
                snippets_text = "\n[SYSTEM NOTE: No source code evidence found in RAG. If this is unexpected, please ensure 'Inference' or 'Ingest' was performed for this project.]\n"
        except Exception as e:
            logger.warning(f"[sa_unified_modeler] Forensic RAG search failed: {e}")

    user_content = _build_user_message(components, rtm, inventory, action_type, snippets_text)
    cache_name = cache_manager.get_google_cache(run_id)

    if action_type == "CREATE":
        system_prompt = CREATION_PROMPT + OUTPUT_GUIDE
    else:
        system_prompt = RECOVERY_PROMPT + OUTPUT_GUIDE

    res = call_structured(
        api_key=ctx.api_key, model=ctx.model,
        schema=SAUnifiedModelerOutput, system_prompt=system_prompt,
        user_msg=user_content, context_cache=cache_name,
        compress_prompt=False,
        temperature=0.0
    )

    output = res.parsed
    return {
        "sa_unified_modeler_output": output.model_dump(),
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "unified_modeler", "thinking": output.thinking or ""}],
        "current_step": "unified_modeling_done"
    }
