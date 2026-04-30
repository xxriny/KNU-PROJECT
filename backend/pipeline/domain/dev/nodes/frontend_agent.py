from __future__ import annotations

import json

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.core.utils import call_structured
from pipeline.domain.dev.schemas import DomainAgentPlanningOutput


SYSTEM_PROMPT = """# 역할: Frontend Development Agent
## 목표
- task spec과 RAG 컨텍스트를 바탕으로 프론트엔드 개발 산출물을 만든다.

## 규칙
- 출력은 반드시 구조화된 JSON만 반환한다.
- domain은 반드시 frontend로 설정한다.
- proposed_changes는 컴포넌트/상태/연동 관점의 구체 항목 3개 이상 작성한다.
- files는 화면, 컴포넌트, 상태, API 연결 단위로 구체화한다.
- dependencies는 UI/UX handoff와 backend contract를 반영한다.
- test_plan은 렌더링, 상태 흐름, API 연동 검증을 포함한다.
- thinking은 반드시 한국어 핵심 단어 3개 이내로 작성한다.
"""


def _build_user_message(spec: dict, project_rag_context: dict, artifact_rag_context: dict) -> str:
    return json.dumps({
        "task_spec": spec,
        "project_rag_context": project_rag_context,
        "artifact_rag_context": artifact_rag_context,
    }, ensure_ascii=False)


@pipeline_node("develop_frontend_agent")
def develop_frontend_agent_node(ctx: NodeContext) -> dict:
    spec = ctx.sget("frontend_task_spec", {}) or {}
    targets = spec.get("target_components", []) or []
    fallback_result = {
        "status": "draft",
        "domain": "frontend",
        "summary": f"Plan frontend implementation for {len(targets)} components.",
        "requirement_ids": spec.get("requirement_ids", []) or [],
        "proposed_changes": [
            "Connect UI states to updated data flow.",
            "Map screen behavior to concrete components.",
            "Prepare integration points with backend contracts.",
        ],
        "files": [f"frontend:{target}" for target in targets[:6]] or ["frontend:app-shell"],
        "dependencies": ["uiux handoff", "backend contract updates"],
        "test_plan": [
            "Validate screen/component render paths.",
            "Validate API integration and error state handling.",
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
        planned["domain"] = "frontend"
        planned["requirement_ids"] = planned.get("requirement_ids") or spec.get("requirement_ids", []) or []
        return {"frontend_result": planned, "_thinking": res.parsed.thinking or "frontend-rag, wiring, plan"}
    return {"frontend_result": fallback_result, "_thinking": "component-wiring, state-flow, integration-points"}
