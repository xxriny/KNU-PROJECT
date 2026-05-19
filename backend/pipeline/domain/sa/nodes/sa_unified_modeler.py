"""
SA Unified Modeler Node — 컴포넌트를 기반으로 API + DB 스키마를 동시 설계
"""
from __future__ import annotations
from pipeline.core.node_base import pipeline_node, NodeContext
from pipeline.core.utils import call_structured
from pipeline.core.cache_manager import cache_manager
from pipeline.domain.sa.schemas import SAUnifiedModelerOutput
from observability.logger import get_logger


logger = get_logger()

# RECOVERY_PROMPT: 분석 및 복구 모드 (지능형 아키텍처 복원)
RECOVERY_PROMPT = """# Role: Intelligent System Architecture Restorer

## [GOAL: BEST-EFFORT RECONSTRUCTION]
Your goal is to reconstruct the API and DB architecture of the project. 
Even if the provided `<existing_code_forensic_evidence>` is sparse, use the `<project_inventory>` (file names, function names) to infer the structure. 

## 1. API Reconstruction:
- **Source of Truth**: Priority 1: `<existing_code_forensic_evidence>`. Priority 2: `<project_inventory>`.
- **Search Patterns**: Look for decorators like `@app.get`, `@app.post`, `@router.`, or framework-specific markers (FastAPI, Flask, Express).
- **Direct Extraction**: Audit files identified as API handlers in the inventory. You MUST extract every endpoint defined by a decorator or a clear routing function.
- **Payload Recovery**: Infer the request schema from function arguments/type hints and the response schema from return statements.
- **Inference from Logic**: If snippets are missing but a file is named `rest_handler.py`, infer logical endpoints based on its function names (e.g., `get_user_profile` -> `GET /api/user/profile`).
- **Completeness**: Every API endpoint existing in the source code must be documented. Omission of an existing API is a critical failure.

## 2. Database Reconstruction (Forensic Audit):
- **Source of Truth**: Priority 1: `<existing_code_forensic_evidence>`. Priority 2: `<project_inventory>`.
- **Search Patterns**: Look for `Table(Base)`, `__tablename__`, `get_or_create_collection("...")`, `PersistentClient`, or `sqlite3.connect`.
- **Detect ALL Entities**: Audit ALL files identified as database/model containers in the inventory. If a file contains storage logic (add, get, delete, query), it MUST be reported as a table/collection.
- **Literal Mapping**: Use the EXACT names for tables and collections found in the code (e.g., the `name` parameter in `get_or_create_collection`).
- **Inference from Functions**: If the schema is implicit (NoSQL/Vector), infer columns from function arguments (e.g., `add_item(name, age)` -> columns `name`, `age`).
- **Completeness**: Ensure EVERY database entity mentioned in the evidence is included in the output. Missing a database found in the code is a critical error.

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

UPDATE_PROMPT = """# Role: Senior System Architect (Update Mode)

## [GOAL: INCREMENTAL API & DB UPDATE]
You are given the PREVIOUS API and DB design from a prior analysis session in <previous_api_db_design>.
Your task is:
1. **PRESERVE** all existing APIs and tables that remain relevant — exact same endpoints, table names, and schemas
2. **ADD** new APIs/tables ONLY for genuinely new RTM requirements
3. **MODIFY** existing endpoints/tables ONLY if requirements explicitly change them

## Critical Rules
- The <previous_api_db_design> is authoritative — do NOT rename, drop, or restructure items without clear RTM justification
- **EVERY table listed in <previous_api_db_design> MUST appear in your output**, even if the new RTM does not mention it
- **MANDATORY ADD**: For every NEW RTM feature not covered by existing tables, you MUST CREATE a new table. "Preserve existing" does NOT mean "only preserve" — both preservation AND addition are required.
- New APIs must follow the existing naming conventions (path style, HTTP methods)
- New tables must follow the existing schema patterns (naming, column types)
- Ensure new features integrate properly with existing tables via foreign keys
- **FK RULE**: If any column defines a FOREIGN KEY referencing another table (e.g., FOREIGN_KEY(users.id)), that referenced table MUST be explicitly defined as a separate table entry in your output with all required columns (id, etc.)
- **NEVER generate duplicate endpoints** — normalize all path parameters to {param} style (FastAPI standard)

## Output Rules
- **thinking**: Describe which APIs/tables you preserved, added, and modified (In Korean)
- **Output Language**: All specification fields must be written in professional Korean
"""

# 공통 출력 규약 (JSON 구조 정의)
OUTPUT_GUIDE = """
## Output Format (JSON)
- **thinking (th)**: Critical logic and evidence (Korean).
- **definitions (df)**: Mapping between Frontend components and APIs.
- **apis (ap)**: Endpoints (ep), Request schema (rq), Response schema (rs).
- **tables (tb)**: Table name (nm) and Columns (cl).
"""


def _build_user_message(components: list, rtm: list, inventory: dict, action_type: str,
                        snippets: str = "",
                        previous_apis: list = None, previous_tables: list = None) -> str:
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
            formatted_items = [f"{it.get('name')}({it.get('summary', '')[:50]})" for it in items]
            inventory_lines.append(f"- {path}: {formatted_items}")
        inventory_lines.append("</project_inventory>")

    # UPDATE 모드: 이전 API/DB 설계를 맨 앞에 배치
    prev_design_section = ""
    if action_type == "UPDATE":
        _prev_apis = previous_apis or []
        _prev_tables = previous_tables or []
        if _prev_apis or _prev_tables:
            lines = ["<previous_api_db_design — 반드시 유지하고, 신규 RTM에 필요한 것만 추가/수정>"]
            if _prev_apis:
                lines.append("[APIs]")
                for api in _prev_apis:
                    ep = api.get("endpoint", "?")
                    lines.append(f"  - {ep}")
            if _prev_tables:
                lines.append("[Tables]")
                for tbl in _prev_tables:
                    name = tbl.get("table_name") or tbl.get("name", "?")
                    cols = tbl.get("columns", [])
                    if cols:
                        col_strs = []
                        for col in cols:
                            if isinstance(col, dict):
                                col_name = col.get("name", "")
                                col_type = col.get("type", "")
                                col_const = col.get("constraints", "")
                                col_strs.append(f"{col_name}:{col_type}:{col_const}" if col_const else f"{col_name}:{col_type}")
                            elif isinstance(col, str):
                                col_strs.append(col)
                        lines.append(f"  - {name} ({', '.join(col_strs[:8])})")
                    else:
                        lines.append(f"  - {name}")
            lines.append("</previous_api_db_design>")
            prev_design_section = "\n".join(lines) + "\n\n"

    # Select final instruction based on mode
    if action_type == "CREATE":
        final_instruction = "[Instruction] Based on the components and RTM above, perform a professional API and DB design that perfectly satisfies the requirements."
    elif action_type == "UPDATE":
        final_instruction = "[Instruction/UPDATE] PRESERVE all APIs and tables from <previous_api_db_design>. Only ADD new APIs/tables for new RTM requirements. Only MODIFY existing ones if explicitly required by new requirements. The previous architecture is authoritative."
    else:
        final_instruction = "[Instruction/CRITICAL] Based ONLY on the facts in the inventory and snippets, extract the 'actually existing' API and DB structures 100% as-is. NEVER hallucinate missing parts. No Hallucination!"

    return (
        f"{prev_design_section}"
        f"{' '.join(inventory_lines)}\n\n"
        f"{snippets}\n\n"
        f"Comp:\n{p_comp}\n"
        f"RTM:\n{p_rtm}\n\n"
        f"{final_instruction}"
    )


def _expand_for_frontend(components: list, apis: list, tables: list) -> dict:
    """약어 필드 → 프론트엔드 풀네임 변환 (기존 sa_advisor 기능 흡수)"""
    expanded_comps = []
    for c in components:
        # Pydantic 모델인 경우 dict로 변환
        c_dict = c.model_dump(by_alias=True) if hasattr(c, "model_dump") else c
        expanded_comps.append({
            "component_name": c_dict.get("nm") or c_dict.get("name"),
            "role": c_dict.get("rl") or c_dict.get("role"),
            "domain": {"F": "Frontend", "B": "Backend"}.get(c_dict.get("dm"), c_dict.get("domain", "Backend")),
            "dependencies": [d.strip() for d in (c_dict.get("dp") or c_dict.get("deps", "")).split(",") if d.strip()],
            "rtms": c_dict.get("rt") or c_dict.get("rtms"),
        })

    expanded_apis = []
    for a in apis:
        a_dict = a.model_dump(by_alias=True) if hasattr(a, "model_dump") else a
        expanded_apis.append({
            "endpoint": a_dict.get("endpoint") or a_dict.get("ep"),
            "request_schema": a_dict.get("req") or a_dict.get("rq"),
            "response_schema": a_dict.get("res") or a_dict.get("rs"),
            "description": a_dict.get("endpoint") or a_dict.get("ep"),
        })

    expanded_tables = []
    for t in tables:
        t_dict = t.model_dump(by_alias=True) if hasattr(t, "model_dump") else t
        cols_raw = t_dict.get("cl") or t_dict.get("columns", "")
        columns = []
        if isinstance(cols_raw, str):
            for col_str in cols_raw.split(","):
                parts = col_str.strip().split(":")
                columns.append({
                    "name": parts[0] if len(parts) > 0 else "",
                    "type": parts[1] if len(parts) > 1 else "string",
                    "constraints": parts[2] if len(parts) > 2 else "",
                })
        else:
            columns = cols_raw
        expanded_tables.append({
            "table_name": t_dict.get("nm") or t_dict.get("table_name"),
            "columns": columns,
        })

    return {"components": expanded_comps, "apis": expanded_apis, "tables": expanded_tables}


@pipeline_node("sa_unified_modeler")
def sa_unified_modeler_node(ctx: NodeContext) -> dict:
    sget = ctx.sget
    logger.info("=== [Node Entry] sa_unified_modeler_node ===")

    components_out = sget("component_scheduler_output", {}).get("components", [])
    rtm = (sget("merged_project", {}).get("plan", {}).get("requirements_rtm", []) or 
           sget("features", []) or sget("pm_bundle", {}).get("data", {}).get("rtm", []))
    run_id = sget("run_id", sget("session_id", "sa_session"))
    action_type = sget("action_type", "CREATE")

    inventory = {}
    snippets_text = ""

    # UPDATE 모드: merged_project에서 이전 API/테이블 읽기
    merged_project_data = sget("merged_project", {})
    previous_apis   = merged_project_data.get("previous_apis", [])
    previous_tables = merged_project_data.get("previous_tables", [])

    user_content = _build_user_message(
        components_out, rtm, inventory, action_type, snippets_text,
        previous_apis=previous_apis, previous_tables=previous_tables
    )
    cache_name = cache_manager.get_google_cache(run_id)

    if action_type == "CREATE":
        system_prompt = CREATION_PROMPT + OUTPUT_GUIDE
    elif action_type == "UPDATE":
        system_prompt = UPDATE_PROMPT + OUTPUT_GUIDE
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
    apis = output.apis
    tables = output.tables
    
    # [FIX] Assemble SA bundle and expand for frontend (sa_advisor replacement)
    expanded_data = _expand_for_frontend(components_out, apis, tables)
    sa_arch_bundle = {
        "phase": "SA",
        "metadata": {"version": "v1.0", "session_id": run_id},
        "data": expanded_data,
    }

    return {
        "sa_unified_modeler_output": output.model_dump(),
        "sa_arch_bundle": sa_arch_bundle,
        "sa_output": {"status": "PASS", "data": expanded_data}, # UI 탭 활성화를 위한 폴백
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "unified_modeler", "thinking": output.thinking or ""}],
        "current_step": "unified_modeling_done"
    }
