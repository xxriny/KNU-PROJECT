"""
Component Scheduler Node — 요구사항(RTM)을 시스템 컴포넌트로 분해
"""
from __future__ import annotations
from pipeline.core.node_base import pipeline_node, NodeContext
from pipeline.core.utils import call_structured, create_context_cache
from pipeline.core.cache_manager import cache_manager
from pipeline.domain.sa.schemas import ComponentSchedulerOutput
from observability.logger import get_logger


logger = get_logger()

RECOVERY_PROMPT = """# Role: High-Granularity System Restorer

## [GOAL: COMPREHENSIVE ARCHITECTURE RECOVERY]
Your goal is to reconstruct the complete system component map. 
- **Be Granular**: For 180+ files, expect at least 10-15 major components.
- **Inference from Names**: Even without full code, use file names to define components. (e.g., `pipelineSlice.js` -> `Pipeline State Manager`).
- **Group by Logic**: Group related files (e.g., `backend/nodes/*.py`) into logical Service Units.

## [Forensic Principles]
- **Evidence-First**: Use the <project_inventory> as your map.
- **Logical Mapping**: Map each component to its corresponding RTM features.
- **Dependency Inference**: If `main.py` exists and `nodes/` exist, infer that `main` depends on `nodes`.
- **NO EMPTY NAMES**: Do NOT use "?" or "Unknown" for names. If a logical name is unclear, use the primary filename or class name (e.g., `rest_handler.py` -> `RestHandlerComponent`).

## Output Rules
- **thinking**: Explain how you grouped the files into these components (In Korean).
- **Output Language**: All specification fields must be written in professional Korean.
- **Literal Naming**: Ensure `nm` (Name) is descriptive and non-empty.
"""

CREATION_PROMPT = """# Role: Senior Component Architect (New Design Mode)

## Overview
Decompose new requirements (RTM) into modular system components.

## Design Principles (Modular Design)
1. **Separation of Concerns**: Each component must have one clear responsibility.
2. **Layer Separation**: Clearly distinguish between Frontend (F) and Backend (B) layers.
3. **Cohesion/Coupling**: Aim for high cohesion and low coupling.

## Output Rules
- **thinking**: Describe your design rationale (In Korean).
- **Output Language**: All specification fields must be written in professional Korean.
"""

UPDATE_PROMPT = """# Role: Senior System Architect (Update Mode)

## [GOAL: INCREMENTAL ARCHITECTURE UPDATE]
You are given a list of EXISTING components from a previous analysis session in <previous_components>.
Your task is:
1. **PRESERVE** all existing components that are still relevant — keep their names, domains, and roles exactly as-is
2. **ADD** new components ONLY for genuinely new RTM requirements not covered by existing ones
3. **MODIFY** existing components ONLY if a requirement explicitly changes their responsibility

## Critical Rules
- The <previous_components> list is authoritative — do NOT rename, merge, or drop components without clear RTM justification
- If a component handles a requirement that still exists, keep it unchanged with the exact same name and domain
- Maintain Frontend (F) / Backend (B) domain separation

## Output Rules
- **thinking**: Explain which components you preserved, added, and modified (In Korean)
- **Output Language**: All specification fields must be written in professional Korean
"""

OUTPUT_GUIDE = """
## Output Format (JSON)
- **thinking (th)**: Evidence-based rationale (Korean).
- **components (cp)**: Domain (dm), Name (nm), Role (rl), Related RTM IDs (rt), Dependencies (dp).
"""


def _build_user_message(merged_project: dict, inventory: dict, action_type: str, snippets: str = "") -> str:
    plan = merged_project.get("plan", {})
    rtm = plan.get("requirements_rtm", [])
    p_rtm = "\n".join(f"{r.get('feature_id', r.get('id'))}:{r.get('description', r.get('desc'))}" for r in rtm)

    inventory_str = ""
    if inventory:
        lines = ["<project_inventory>"]
        for p, items in sorted(inventory.items()):
            lines.append(f"- {p}: {[it.get('name') for it in items]}")
        lines.append("</project_inventory>")
        inventory_str = "\n".join(lines)

    # UPDATE 모드: 이전 컴포넌트 목록을 맨 앞에 배치
    prev_comps_section = ""
    if action_type == "UPDATE":
        prev_comps = merged_project.get("previous_components", [])
        if prev_comps:
            prev_lines = []
            for c in prev_comps:
                name = c.get("component_name") or c.get("name") or c.get("nm", "?")
                domain = c.get("domain") or c.get("dm", "?")
                role = c.get("role") or c.get("rl", "")
                prev_lines.append(f"  - [{domain}] {name}: {role}")
            prev_comps_section = (
                "<previous_components — 반드시 유지하고, 신규 RTM에 필요한 것만 추가/수정>\n"
                + "\n".join(prev_lines)
                + "\n</previous_components>\n\n"
            )

    # 모드에 따른 최종 행동 지침 분기
    if action_type == "CREATE":
        final_instruction = "[지침] 위 요구사항(RTM)을 완벽히 해결하는 새롭고 모듈화된 시스템 컴포넌트를 설계하십시오."
    elif action_type == "UPDATE":
        final_instruction = "[지침/UPDATE] <previous_components>의 모든 컴포넌트를 그대로 유지하되, 신규 RTM에만 필요한 컴포넌트를 추가하고 변경이 명시적으로 필요한 것만 수정하십시오. 기존 구조를 최대한 보존하세요."
    else:
        final_instruction = "[지침/CRITICAL] 제공된 인벤토리의 모든 주요 폴더와 파일을 분석하여, 현재 시스템의 '전체 윤곽'이 드러나도록 최대한 많은(10개 이상) 컴포넌트를 추출하십시오. 파일명만으로도 역할이 명확하다면 과감하게 포함시키십시오."

    return (
        f"{prev_comps_section}"
        f"{inventory_str}\n\n"
        f"{snippets}\n\n"
        f"Strategy: {merged_project.get('merge_strategy', '')}\n"
        f"RTM:\n{p_rtm}\n\n"
        f"{final_instruction}"
    )


@pipeline_node("component_scheduler")
def component_scheduler_node(ctx: NodeContext) -> dict:
    sget = ctx.sget
    logger.info("=== [Node Entry] component_scheduler_node ===")

    merged_project = sget("merged_project", {})
    action_type = sget("action_type", "CREATE")
    run_id = sget("run_id", sget("session_id", "sa_session"))

    inventory = {}
    snippets_text = ""

    user_content = _build_user_message(merged_project, inventory, action_type, snippets_text)

    # 모드에 따른 시스템 프롬프트 선택
    if action_type == "CREATE":
        system_prompt = CREATION_PROMPT + OUTPUT_GUIDE
    elif action_type == "UPDATE":
        system_prompt = UPDATE_PROMPT + OUTPUT_GUIDE
    else:
        system_prompt = RECOVERY_PROMPT + OUTPUT_GUIDE

    res = call_structured(
        api_key=ctx.api_key, model=ctx.model,
        schema=ComponentSchedulerOutput, system_prompt=system_prompt,
        user_msg=user_content,
        compress_prompt=False, # 아키텍처 정밀도를 위해 압축 비활성화
        temperature=0.0
    )

    output = res.parsed
    return {
        "component_scheduler_output": output.model_dump(),
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "component_scheduler", "thinking": output.thinking or ""}],
        "current_step": "component_scheduler_done"
    }
