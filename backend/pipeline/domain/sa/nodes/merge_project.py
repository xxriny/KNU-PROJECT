from __future__ import annotations
from typing import Any, Dict, List

from pipeline.core.state import PipelineState, make_sget
from pipeline.core.node_base import pipeline_node, NodeContext
from pipeline.core.utils import call_structured
from pipeline.core.action_type import normalize_action_type
from pipeline.domain.rag.framework_detector import detect_framework_evidence
from pipeline.domain.rag.nodes.project_db import query_project_code, get_session_inventory
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


def _build_rag_context(action_type: str, input_idea: str, source_dir: str, session_id: str) -> str:
    """ChromaDB에서 직접 검색한 청크 + manifest 기반 framework 단서를 합쳐 LLM 컨텍스트로 반환."""
    if action_type == "CREATE" or not session_id:
        return ""

    queries: List[str] = [
        "엔티티 데이터 모델 ORM 테이블 스키마",
        "API 라우터 엔드포인트 컨트롤러 핸들러",
        "핵심 비즈니스 로직 및 서비스 레이어"
    ]
    if input_idea:
        queries.insert(0, input_idea)

    chunks: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for q in queries:
        try:
            results = query_project_code(q, session_id=session_id, n_results=4)
        except Exception:
            continue
        for c in results:
            cid = c.get("chunk_id")
            if cid and cid not in seen:
                seen.add(cid)
                chunks.append(c)

    snippet_lines = [
        f"[{c.get('file_path', '')}::{c.get('func_name', '')}] {(c.get('content_text', '') or '')[:300]}"
        for c in chunks[:12]
    ]

    detected, evidence, _ = detect_framework_evidence(source_dir)

    sections: List[str] = []
    if detected:
        sections.append(f"frameworks={detected}")
    if evidence:
        sections.append(f"evidence={evidence[:10]}")
    if snippet_lines:
        sections.append("code_snippets:\n" + "\n".join(snippet_lines))

    return "\n---\n".join(sections) if sections else ""


def _build_user_message(
    action_type: str,
    input_idea: str,
    rag_context: str,
    rtm: list,
    inventory: dict
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
    
    inventory_str = ""
    if inventory:
        lines = ["<project_inventory>"]
        for p, items in sorted(inventory.items()):
            lines.append(f"- {p}: {[it.get('name') for it in items[:10]]}")
        lines.append("</project_inventory>")
        inventory_str = "\n".join(lines)

    return (
        f"{inventory_str}\n\n"
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
    rag_status = sget("rag_index_status", {}) or {}
    rag_session_id = rag_status.get("session_id") or sget("session_id", "") or ""

    pm_bundle = sget("pm_bundle", {})
    requirements_rtm = pm_bundle.get("data", {}).get("rtm", []) or sget("features", [])

    if not requirements_rtm:
        logger.warning("No RTM/Features found in state for SA merge.")

    # 1. 인벤토리 및 RAG 컨텍스트 수집 (CREATE 모드가 아닐 때만)
    inventory = {}
    rag_context = ""
    if action_type != "CREATE" and rag_status.get("has_index"):
        try:
            inventory = get_session_inventory(rag_session_id)
        except:
            pass
        rag_context = _build_rag_context(action_type, input_idea, source_dir, rag_session_id)

    # 2. 메시지 조립
    user_content = _build_user_message(action_type, input_idea, rag_context, requirements_rtm, inventory)

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
    }

    thinking_msg = output.thinking or "프로젝트 병합 전략 수립 완료"

    return {
        "sa_merge_project_output": {**output.model_dump(), "mode": action_type},
        "merged_project": merged_project,
        "action_type": action_type,
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_merge_project", "thinking": thinking_msg}],
        "current_step": "sa_merge_project_done",
    }
