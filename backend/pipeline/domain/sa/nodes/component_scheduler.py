"""
Component Scheduler Node — 요구사항(RTM)을 시스템 컴포넌트로 분해
"""
from __future__ import annotations
from pipeline.core.node_base import pipeline_node, NodeContext
from pipeline.core.utils import call_structured, create_context_cache
from pipeline.core.cache_manager import cache_manager
from pipeline.domain.sa.schemas import ComponentSchedulerOutput
from observability.logger import get_logger

from pipeline.domain.rag.nodes.project_db import get_session_inventory

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

## Output Rules
- **thinking**: Explain how you grouped the files into these components (In Korean).
- **Output Language**: All specification fields must be written in professional Korean.
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

OUTPUT_GUIDE = """
## Output Format (JSON)
- **thinking (th)**: Evidence-based rationale (Korean).
- **components (cp)**: Domain (dm), Name (nm), Role (rl), Related RTM IDs (rt), Dependencies (dp).
"""


def _build_user_message(merged_project: dict, inventory: dict, action_type: str) -> str:
    plan = merged_project.get("plan", {})
    rtm = plan.get("requirements_rtm", [])
    p_rtm = "\n".join(f"{r.get('feature_id', r.get('id'))}:{r.get('description', r.get('desc'))}" for r in rtm)
    
    inventory_str = ""
    if inventory:
        lines = ["<project_inventory>"]
        for p, items in sorted(inventory.items()):
            # [FIX] Increase visibility: show up to 20 items per folder to give more context
            lines.append(f"- {p}: {[it.get('name') for it in items[:20]]}")
        lines.append("</project_inventory>")
        inventory_str = "\n".join(lines)
        
    # 모드에 따른 최종 행동 지침 분기
    if action_type == "CREATE":
        final_instruction = "[지침] 위 요구사항(RTM)을 완벽히 해결하는 새롭고 모듈화된 시스템 컴포넌트를 설계하십시오."
    elif action_type == "UPDATE":
        final_instruction = "[지침/Hybrid] 기존 인벤토리 파일들을 논리적 단위로 묶어 컴포넌트로 추출하고, 신규 RTM을 위한 컴포넌트도 추가하십시오."
    else:
        final_instruction = "[지침/CRITICAL] 제공된 인벤토리의 모든 주요 폴더와 파일을 분석하여, 현재 시스템의 '전체 윤곽'이 드러나도록 최대한 많은(10개 이상) 컴포넌트를 추출하십시오. 파일명만으로도 역할이 명확하다면 과감하게 포함시키십시오."

    return (
        f"{inventory_str}\n\n"
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

    # 인벤토리 수집 (CREATE 제외)
    inventory = {}
    if action_type != "CREATE":
        try:
            inventory = get_session_inventory(run_id)
        except:
            pass

    user_content = _build_user_message(merged_project, inventory, action_type)

    # 모드에 따른 시스템 프롬프트 선택
    if action_type == "CREATE":
        system_prompt = CREATION_PROMPT + OUTPUT_GUIDE
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
