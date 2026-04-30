from __future__ import annotations

import json

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.core.utils import call_structured
from pipeline.domain.dev.schemas import DomainQAPlanningOutput


SYSTEM_PROMPT = """# 역할: Frontend QA Agent
## 목표
- frontend agent 산출물을 검토하고 pass 또는 rework를 결정한다.

## 규칙
- 출력은 반드시 구조화된 JSON만 반환한다.
- domain은 반드시 frontend로 설정한다.
- status는 pass 또는 rework만 사용한다.
- UI 구현 가능성, 상태 흐름, backend 연동 정합성을 우선 검토한다.
- findings는 실제 문제 또는 검토 결과를 작성한다.
- fixes_required는 재작업이 필요할 때 구체적으로 작성한다.
- thinking은 반드시 한국어 핵심 단어 3개 이내로 작성한다.
"""


def _build_user_message(result: dict, spec: dict, project_rag_context: dict, artifact_rag_context: dict) -> str:
    return json.dumps({
        "task_spec": spec,
        "domain_result": result,
        "project_rag_context": project_rag_context,
        "artifact_rag_context": artifact_rag_context,
    }, ensure_ascii=False)


@pipeline_node("develop_frontend_qa_agent")
def develop_frontend_qa_agent_node(ctx: NodeContext) -> dict:
    result = ctx.sget("frontend_result", {}) or {}
    spec = ctx.sget("frontend_task_spec", {}) or {}
    findings = []
    fixes_required = []
    if not result.get("files"):
        findings.append("No frontend targets were identified.")
        fixes_required.append("Specify components or screens for FE implementation.")
    if not result.get("requirement_ids"):
        findings.append("Frontend result is not mapped to requirement IDs.")
        fixes_required.append("Link frontend scope to explicit requirement IDs.")
    if len(result.get("proposed_changes", []) or []) < 2:
        findings.append("Frontend result does not describe enough concrete changes.")
        fixes_required.append("List at least two concrete frontend changes.")
    if len(result.get("test_plan", []) or []) < len(spec.get("acceptance_criteria", []) or []):
        findings.append("Frontend test plan does not cover the declared acceptance criteria.")
        fixes_required.append("Expand the frontend test plan to cover all acceptance criteria.")
    fallback = {
        "status": "rework" if fixes_required else "pass",
        "domain": "frontend",
        "findings": findings,
        "fixes_required": fixes_required,
    }
    if ctx.api_key:
        res = call_structured(
            api_key=ctx.api_key,
            model=ctx.model,
            schema=DomainQAPlanningOutput,
            system_prompt=SYSTEM_PROMPT,
            user_msg=_build_user_message(
                result,
                spec,
                ctx.sget("project_rag_context", {}) or {},
                ctx.sget("artifact_rag_context", {}) or {},
            ),
            max_retries=3,
            temperature=0.1,
            compress_prompt=True,
        )
        planned = res.parsed.model_dump()
        planned["domain"] = "frontend"
        return {"frontend_qa_result": planned, "_thinking": res.parsed.thinking or "frontend-qa, state-flow, integration"}
    return {"frontend_qa_result": fallback, "_thinking": "frontend-scope, ui-sync, integration-readiness"}
