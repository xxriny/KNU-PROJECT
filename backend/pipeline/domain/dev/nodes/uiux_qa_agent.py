from __future__ import annotations

import json

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.core.utils import call_structured
from pipeline.domain.dev.schemas import DomainQAPlanningOutput


SYSTEM_PROMPT = """# 역할: UI/UX QA Agent
## 목표
- UI/UX agent 산출물을 검토하고 pass 또는 rework를 결정한다.

## 규칙
- 출력은 반드시 구조화된 JSON만 반환한다.
- domain은 반드시 uiux로 설정한다.
- status는 pass 또는 rework만 사용한다.
- findings는 확인된 문제 또는 확인 결과를 작성한다.
- fixes_required는 재작업이 필요할 때만 구체적으로 작성한다.
- 요구사항, 화면 흐름, shared component 일관성을 우선 검토한다.
- thinking은 반드시 한국어 핵심 단어 3개 이내로 작성한다.
"""


def _build_user_message(result: dict, spec: dict, project_rag_context: dict, artifact_rag_context: dict) -> str:
    return json.dumps({
        "task_spec": spec,
        "domain_result": result,
        "project_rag_context": project_rag_context,
        "artifact_rag_context": artifact_rag_context,
    }, ensure_ascii=False)


@pipeline_node("develop_uiux_qa_agent")
def develop_uiux_qa_agent_node(ctx: NodeContext) -> dict:
    result = ctx.sget("uiux_result", {}) or {}
    spec = ctx.sget("uiux_task_spec", {}) or {}
    findings = []
    fixes_required = []
    if not result.get("files"):
        findings.append("No UI/UX target files or areas were identified.")
        fixes_required.append("Specify target screens or shared components.")
    if not result.get("requirement_ids"):
        findings.append("UI/UX result is not mapped to requirement IDs.")
        fixes_required.append("Link UI/UX scope to explicit requirement IDs.")
    if len(result.get("proposed_changes", []) or []) < 2:
        findings.append("UI/UX result does not describe enough concrete changes.")
        fixes_required.append("List at least two concrete UI/UX changes.")
    if len(result.get("test_plan", []) or []) < len(spec.get("acceptance_criteria", []) or []):
        findings.append("UI/UX test plan does not cover the declared acceptance criteria.")
        fixes_required.append("Expand the UI/UX test plan to cover all acceptance criteria.")
    fallback = {
        "status": "rework" if fixes_required else "pass",
        "domain": "uiux",
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
        planned["domain"] = "uiux"
        return {"uiux_qa_result": planned, "_thinking": res.parsed.thinking or "uiux-qa, flow, consistency"}
    return {"uiux_qa_result": fallback, "_thinking": "uiux-coverage, ui-contract, implementation-handoff"}
