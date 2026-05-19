"""
Forensic Profiler Node — 프로젝트 전체 구조를 분석하고 각 파일의 아키텍처 역할을 태깅
"""
from __future__ import annotations
from pipeline.core.node_base import pipeline_node, NodeContext
from pipeline.core.utils import call_structured
from pipeline.domain.sa.schemas import ForensicProfilerOutput
from observability.logger import get_logger

logger = get_logger()

SYSTEM_PROMPT = """# Role: Forensic Architecture Profiler

## Goal
Analyze the project inventory (file paths, function names, docstrings) and classify each file into a specific architectural role. 
This classification will be used by downstream nodes to target their forensic analysis.

## Architectural Roles
- **DB**: Database schemas, models, migrations, or storage logic (e.g., SQLAlchemy Base, ChromaDB collection).
- **API**: REST/GraphQL handlers, routers, or endpoint definitions (e.g., FastAPI routes, Flask views).
- **SERVICE**: Business logic, core service layers, or complex algorithm containers.
- **UI**: Frontend components, pages, views, or layout definitions.
- **STORE**: Global state management, contexts, or frontend data stores (e.g., Redux slices, React context).
- **CONFIG**: Configuration files, environment setups, or package manifests (e.g., package.json, requirements.txt).
- **UTIL**: Helper functions, constants, or generic utility modules.

## Analysis Principle
- Use **function names** and **docstrings** as the primary evidence.
- If a file contains `get_or_create_collection`, tag it as **DB**.
- If a file contains `@app.get` or `Router`, tag it as **API**.
- If a file is in a `components/` folder, tag it as **UI**.

## Output Rules
- **thinking**: Explain your classification rationale for major file clusters (In Korean).
- **profiles**: Provide the path and the determined role for EVERY important file in the inventory.
"""

@pipeline_node("forensic_profiler")
def forensic_profiler_node(ctx: NodeContext) -> dict:
    sget = ctx.sget
    logger.info("=== [Node Entry] forensic_profiler_node ===")

    run_id = sget("run_id", sget("session_id", "sa_session"))
    search_session_id = sget("session_id", run_id)
    action_type = sget("action_type", "CREATE")

    # RAG 제거 후 인벤토리 없음 → 빈 결과 반환
    inventory = {}

    if not inventory:
        return {"forensic_profile": {}, "current_step": "forensic_profiler_done"}

    # 인벤토리를 LLM이 이해하기 쉬운 형태로 변환 (Dense Index)
    inventory_lines = []
    for path, items in sorted(inventory.items()):
        func_info = ", ".join([f"{it.get('name')}({it.get('docstring', '')[:50]})" for it in items])
        inventory_lines.append(f"- {path}: {func_info}")
    
    inventory_str = "\n".join(inventory_lines)

    res = call_structured(
        api_key=ctx.api_key, model=ctx.model,
        schema=ForensicProfilerOutput, system_prompt=SYSTEM_PROMPT,
        user_msg=f"<project_inventory>\n{inventory_str}\n</project_inventory>\n\n위 인벤토리를 분석하여 모든 파일의 역할을 분류하십시오.",
        temperature=0.0
    )

    output = res.parsed
    
    # 결과를 딕셔너리 형태로 변환하여 상태에 저장 (조회 속도 최적화)
    profile_map = {p.path: p.role for p in output.profiles}

    return {
        "forensic_profile": profile_map,
        "forensic_profiler_output": output.model_dump(),
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "forensic_profiler", "thinking": output.thinking}],
        "current_step": "forensic_profiler_done"
    }
