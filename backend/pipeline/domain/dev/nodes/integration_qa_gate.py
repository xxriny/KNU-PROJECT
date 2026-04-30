from __future__ import annotations

import json

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.core.utils import call_structured
from pipeline.domain.dev.schemas import IntegrationQAPlanningOutput


SYSTEM_PROMPT = """# 역할: Integration QA Agent
## 목표
- UI/UX, frontend, backend 산출물을 통합 관점에서 검토한다.
- pass 또는 rework 대상 도메인을 결정한다.

## 규칙
- 출력은 반드시 구조화된 JSON만 반환한다.
- status는 pass, rework_uiux, rework_frontend, rework_backend 중 하나만 사용한다.
- reason은 통합 판단 근거를 한 문장으로 작성한다.
- findings는 실제 통합 리스크나 검토 결과를 작성한다.
- rework_targets는 uiux, frontend, backend 중 필요한 것만 포함한다.
- API 계약, 화면 구현 가능성, shared component, 데이터 흐름 정합성을 우선 검토한다.
- thinking은 반드시 한국어 핵심 단어 3개 이내로 작성한다.
"""


def _build_user_message(
    *,
    uiux_result: dict,
    backend_result: dict,
    frontend_result: dict,
    uiux_qa_result: dict,
    backend_qa_result: dict,
    frontend_qa_result: dict,
    project_rag_context: dict,
    artifact_rag_context: dict,
) -> str:
    return json.dumps({
        "uiux_result": uiux_result,
        "backend_result": backend_result,
        "frontend_result": frontend_result,
        "uiux_qa_result": uiux_qa_result,
        "backend_qa_result": backend_qa_result,
        "frontend_qa_result": frontend_qa_result,
        "project_rag_context": project_rag_context,
        "artifact_rag_context": artifact_rag_context,
    }, ensure_ascii=False)


@pipeline_node("develop_integration_qa_gate")
def develop_integration_qa_gate_node(ctx: NodeContext) -> dict:
    backend = ctx.sget("backend_result", {}) or {}
    frontend = ctx.sget("frontend_result", {}) or {}
    uiux = ctx.sget("uiux_result", {}) or {}

    findings = []
    rework_targets = []
    status = "pass"
    reason = "Domain outputs are integration-ready."

    if not backend.get("files"):
        findings.append("Backend scope is empty.")
        rework_targets.append("backend")
    if not frontend.get("files"):
        findings.append("Frontend scope is empty.")
        rework_targets.append("frontend")
    if not uiux.get("files"):
        findings.append("UI/UX handoff scope is empty.")
        rework_targets.append("uiux")

    if rework_targets:
        status = f"rework_{rework_targets[0]}"
        reason = "Integration QA found missing domain scope."

    fallback = {
        "status": status,
        "reason": reason,
        "findings": findings,
        "rework_targets": rework_targets,
    }

    if ctx.api_key:
        res = call_structured(
            api_key=ctx.api_key,
            model=ctx.model,
            schema=IntegrationQAPlanningOutput,
            system_prompt=SYSTEM_PROMPT,
            user_msg=_build_user_message(
                uiux_result=uiux,
                backend_result=backend,
                frontend_result=frontend,
                uiux_qa_result=ctx.sget("uiux_qa_result", {}) or {},
                backend_qa_result=ctx.sget("backend_qa_result", {}) or {},
                frontend_qa_result=ctx.sget("frontend_qa_result", {}) or {},
                project_rag_context=ctx.sget("project_rag_context", {}) or {},
                artifact_rag_context=ctx.sget("artifact_rag_context", {}) or {},
            ),
            max_retries=3,
            temperature=0.1,
            compress_prompt=True,
        )
        return {
            "integration_qa_result": res.parsed.model_dump(),
            "_thinking": res.parsed.thinking or "integration-qa, contracts, release-readiness",
        }

    return {
        "integration_qa_result": fallback,
        "_thinking": "cross-domain-contracts, integration-scope, release-readiness",
    }
