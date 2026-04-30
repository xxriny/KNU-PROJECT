from __future__ import annotations

import json

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.core.utils import call_structured
from pipeline.domain.dev.schemas import DomainAgentPlanningOutput


SYSTEM_PROMPT = """# 역할: UI/UX Development Agent
## 목표
- 메인 에이전트가 준 task spec과 RAG 컨텍스트를 바탕으로 UI/UX 개발 산출물을 만든다.

## 규칙
- 출력은 반드시 구조화된 JSON만 반환한다.
- domain은 반드시 uiux로 설정한다.
- summary는 구현 가능한 UI/UX 작업 설명이어야 한다.
- proposed_changes는 구체적인 변경 항목 3개 이상 작성한다.
- files는 화면/컴포넌트/디자인 핸드오프 단위로 작성한다.
- test_plan은 사용자 흐름과 상태 검증 기준을 포함한다.
- thinking은 반드시 한국어 핵심 단어 3개 이내로 작성한다.
"""


def _build_user_message(spec: dict, project_rag_context: dict, artifact_rag_context: dict) -> str:
    return json.dumps({
        "task_spec": spec,
        "project_rag_context": project_rag_context,
        "artifact_rag_context": artifact_rag_context,
    }, ensure_ascii=False)


@pipeline_node("develop_uiux_agent")
def develop_uiux_agent_node(ctx: NodeContext) -> dict:
    spec = ctx.sget("uiux_task_spec", {}) or {}
    targets = spec.get("target_components", []) or []
    fallback_result = {
        "status": "draft",
        "domain": "uiux",
        "summary": f"Prepare UI/UX adjustments for {len(targets)} target components.",
        "requirement_ids": spec.get("requirement_ids", []) or [],
        "proposed_changes": [
            "Align screen structure with updated requirement flow.",
            "Normalize shared component naming and states.",
            "Document FE handoff notes for implementable UI behavior.",
        ],
        "files": [f"uiux:{target}" for target in targets[:6]] or ["uiux:global-design"],
        "dependencies": ["frontend implementation", "shared component contracts"],
        "test_plan": [
            "Validate primary user flow coverage.",
            "Check component state variations and edge states.",
        ],
    }
    if ctx.api_key:
        res = call_structured(
            api_key=ctx.api_key,
            model=ctx.model,
            schema=DomainAgentPlanningOutput,
            system_prompt=SYSTEM_PROMPT,
            user_msg=_build_user_message(spec, ctx.sget("project_rag_context", {}) or {}, ctx.sget("artifact_rag_context", {}) or {}),
            max_retries=3,
            temperature=0.1,
            compress_prompt=True,
        )
        planned = res.parsed.model_dump()
        planned["domain"] = "uiux"
        planned["requirement_ids"] = planned.get("requirement_ids") or spec.get("requirement_ids", []) or []
        return {"uiux_result": planned, "_thinking": res.parsed.thinking or "uiux-rag, handoff, plan"}
    return {"uiux_result": fallback_result, "_thinking": "uiux-plan, handoff, shared-components"}
