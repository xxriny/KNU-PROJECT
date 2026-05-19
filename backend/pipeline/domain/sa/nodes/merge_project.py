from __future__ import annotations
import json
from typing import List

from pipeline.core.state import PipelineState, make_sget
from pipeline.core.node_base import pipeline_node, NodeContext
from pipeline.core.utils import call_structured
from pipeline.core.action_type import normalize_action_type
from pipeline.core.framework_detector import detect_framework_evidence
from pipeline.domain.sa.schemas import MergeProjectOutput
from observability.logger import get_logger

logger = get_logger()

# SYSTEM_PROMPT: 요구사항(RTM)과 기존 코드(RAG)를 대조하여 통합 설계 전략을 수립하는 프롬프트
SYSTEM_PROMPT = """# Role: Senior Integration Architect

## Overview
Analyze the gap between the PM-defined requirements (RTM) and the existing project assets (<project_inventory>, <Code Context>). 
Establish a precise strategy to merge new features into the existing system harmoniously.

## Key Guidelines

### 1. Mode-Based Analysis Strategy (MANDATORY)
- **Action Type = CREATE**: New project. Propose the optimal folder structure and initial architecture based on the RTM.
- **Action Type = UPDATE**: Focus on **'Hybrid'** consistency. Define a strategy to inject new features efficiently without breaking existing code. Infer the stack (e.g., React, FastAPI) from the inventory if explicit info is missing.
- **Action Type = REVERSE_ENGINEER**: Diagnose the current state of the code and summarize the gap between the RTM and actual implementation.

### 2. High-Level Architectural Decisions
- **Data Model Scalability**: When expanding features, consider normalization or 1:N relationship strategies rather than just adding fields.
- **Security & Authentication**: Detail strategies for OAuth integration, token validation, and account merging.
- **Error Handling**: Include global response strategies for external API integration or data processing failures.

### 3. Downstream Guidelines
- Your 'Merge Strategy' is the foundation for the Component Scheduler and Unified Modeler. Avoid vague expressions; provide technical, actionable guidance.

## Output Format (JSON)
- **thinking (th)**: Detailed analysis of potential conflicts, design priorities, and architectural trade-offs (In Korean).
- **mode (md)**: Must maintain the same value as the input [Action Type].
- **base_context (bc)**: Summary of current tech stack, core data models, and architectural traits.
- **merge_strategy (ms)**: Conflict resolutions, design guidelines, security policies, and error handling strategies.
"""


def _build_framework_context(source_dir: str) -> str:
    """manifest 기반 framework 단서를 LLM 컨텍스트로 반환."""
    if not source_dir:
        return ""
    try:
        detected, evidence, _ = detect_framework_evidence(source_dir)
        sections: List[str] = []
        if detected:
            sections.append(f"frameworks={detected}")
        if evidence:
            sections.append(f"evidence={evidence[:10]}")
        return "\n---\n".join(sections) if sections else ""
    except Exception as e:
        logger.warning(f"[merge_project] framework detection failed: {e}")
        return ""


def _build_user_message(
    action_type: str,
    input_idea: str,
    rag_context: str,
    rtm: list,
    project_context: str = "",
) -> str:
    """LLM 메시지 조립"""
    pruned_rtm = [
        {
            "id": r.get("feature_id", r.get("id")),
            "desc": r.get("description", r.get("desc")),
            "pri": r.get("priority", r.get("pri")),
        }
        for r in rtm
    ]

    prev_design_section = ""
    if project_context:
        prev_design_section = f"[Previous Design Context]\n{project_context}\n\n"

    return (
        f"{prev_design_section}"
        f"[Action Type] {action_type}\n"
        f"[Input Idea] {input_idea}\n"
        f"[Code Context]\n{rag_context or '(none)'}\n"
        f"[PM Requirements] {pruned_rtm}\n"
    )


@pipeline_node("sa_merge_project")
def sa_merge_project_node(ctx: NodeContext) -> dict:
    sget = ctx.sget
    logger.info("=== [Node Entry] sa_merge_project_node ===")

    input_idea = sget("input_idea", "")
    action_type = normalize_action_type(sget("action_type", "CREATE"))
    source_dir = sget("source_dir", "") or ""

    pm_bundle = sget("pm_bundle", {})
    requirements_rtm = pm_bundle.get("data", {}).get("rtm", []) or sget("features", [])

    if not requirements_rtm:
        logger.warning("No RTM/Features found in state for SA merge.")

    # 1. 프레임워크 컨텍스트 수집 (소스 디렉토리가 있을 때만)
    rag_context = _build_framework_context(source_dir) if action_type != "CREATE" else ""
    inventory = {}

    # UPDATE 모드: 이전 분석 결과(project_context) JSON 파싱 → 이전 설계 추출
    project_context = ""
    previous_components: list = []
    previous_apis: list = []
    previous_tables: list = []
    previous_rtm: list = []

    if action_type == "UPDATE":
        project_context = sget("project_context", "") or ""
        if project_context:
            try:
                json_start = project_context.find('{')
                if json_start >= 0:
                    prev = json.loads(project_context[json_start:])
                    previous_components = prev.get("components", [])
                    previous_apis       = prev.get("apis", [])
                    previous_tables     = prev.get("tables", [])
                    previous_rtm        = prev.get("requirements_rtm", [])
            except Exception:
                pass

        # PM delta RTM에 이전 RTM 중 누락된 항목 병합 → SA에 full RTM 전달
        if previous_rtm:
            existing_ids = {r.get("feature_id") or r.get("id") for r in requirements_rtm}
            for prev_req in previous_rtm:
                prev_id = prev_req.get("feature_id") or prev_req.get("id")
                if prev_id and prev_id not in existing_ids:
                    requirements_rtm.append(prev_req)

    # 2. 메시지 조립
    user_content = _build_user_message(
        action_type, input_idea, rag_context, requirements_rtm, project_context
    )

    # 3. Call LLM for merge strategy
    res = call_structured(
        api_key=ctx.api_key,
        model=ctx.model,
        schema=MergeProjectOutput,
        system_prompt=SYSTEM_PROMPT,
        user_msg=user_content,
        compress_prompt=False,  # 정밀도를 위해 압축 비활성화 (Precision over cost)
    )

    output = res.parsed

    # LLM이 모드를 임의로 바꿨다면 파이프라인의 권위 있는 action_type으로 강제 정합화
    llm_mode = normalize_action_type(output.mode)
    if llm_mode != action_type:
        logger.warning(
            "sa_merge_project: LLM이 mode=%s 를 반환했으나 입력 action_type=%s 로 강제 정렬",
            llm_mode, action_type,
        )

    # 4. Build merged_project contract for downstream
    merged_project = {
        "mode": action_type,
        "base_context": output.base_context,
        "merge_strategy": output.merge_strategy,
        "plan": {
            "requirements_rtm": requirements_rtm,
            "context_spec": sget("context_spec", {}),
        },
        "previous_components": previous_components,
        "previous_apis": previous_apis,
        "previous_tables": previous_tables,
    }

    thinking_msg = output.thinking or "프로젝트 병합 전략 수립 완료"

    return {
        "sa_merge_project_output": {**output.model_dump(), "mode": action_type},
        "merged_project": merged_project,
        "action_type": action_type,
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_merge_project", "thinking": thinking_msg}],
        "current_step": "sa_merge_project_done",
    }
