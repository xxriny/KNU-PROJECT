from __future__ import annotations

import json

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.core.utils import call_structured
from pipeline.domain.dev.schemas import DomainAgentPlanningOutput


SYSTEM_PROMPT = """# 역할: Backend Development Agent
## 목표
- task spec과 RAG 컨텍스트를 바탕으로 백엔드 개발 산출물을 만든다.

## 규칙
- 출력은 반드시 구조화된 JSON만 반환한다.
- domain은 반드시 backend로 설정한다.
- proposed_changes는 API/서비스/데이터모델 관점의 구체 항목 3개 이상 작성한다.
- files는 API, service, repository, table 단위로 구체화한다.
- dependencies는 연관 도메인 또는 계약 변경 중심으로 작성한다.
- test_plan은 계약/데이터/회귀 검증을 포함한다.
- thinking은 반드시 한국어 핵심 단어 3개 이내로 작성한다.
"""


def _build_user_message(spec: dict, project_rag_context: dict, artifact_rag_context: dict) -> str:
    return json.dumps({
        "task_spec": spec,
        "project_rag_context": project_rag_context,
        "artifact_rag_context": artifact_rag_context,
    }, ensure_ascii=False)


@pipeline_node("develop_backend_agent")
def develop_backend_agent_node(ctx: NodeContext) -> dict:
    spec = ctx.sget("backend_task_spec", {}) or {}
    targets = spec.get("target_components", []) or []
    fallback_result = {
        "status": "draft",
        "domain": "backend",
        "summary": f"Plan backend implementation against {len(targets)} API/data targets.",
        "requirement_ids": spec.get("requirement_ids", []) or [],
        "proposed_changes": [
            "Define service and API changes per requirement.",
            "Identify data model or persistence updates.",
            "Document contract impacts for frontend integration.",
        ],
        "files": targets[:6] or ["backend:service-layer"],
        "dependencies": ["requirements_rtm", "integration QA"],
        "test_plan": [
            "Verify request/response contract changes.",
            "Verify persistence and domain rule regressions.",
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
        planned["domain"] = "backend"
        planned["requirement_ids"] = planned.get("requirement_ids") or spec.get("requirement_ids", []) or []
        return {"backend_result": planned, "_thinking": res.parsed.thinking or "backend-rag, contracts, plan"}
    return {"backend_result": fallback_result, "_thinking": "api-contracts, domain-logic, data-integrity"}
