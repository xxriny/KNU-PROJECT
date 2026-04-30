from __future__ import annotations

import json

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.core.utils import call_structured
from pipeline.domain.dev.schemas import GlobalFESyncPlanningOutput


SYSTEM_PROMPT = """# 역할: Global FE Sync Gate
## 목표
- UI/UX 결과와 Frontend 결과의 정합성을 검토한다.
- pass 또는 재작업 대상을 결정한다.

## 규칙
- 출력은 반드시 구조화된 JSON만 반환한다.
- status는 pass, rework_uiux, rework_frontend 중 하나만 사용한다.
- reason은 FE sync 판단 근거를 한 문장으로 작성한다.
- shared_components는 실제로 맞물리는 공통 컴포넌트/대상만 적는다.
- sync_actions는 재정렬이 필요할 때 구체적으로 작성한다.
- UI intent, shared component naming, frontend wiring 정합성을 우선 검토한다.
- thinking은 반드시 한국어 핵심 단어 3개 이내로 작성한다.
"""


def _build_user_message(
    *,
    uiux_result: dict,
    frontend_result: dict,
    uiux_task_spec: dict,
    frontend_task_spec: dict,
    project_rag_context: dict,
    artifact_rag_context: dict,
) -> str:
    return json.dumps({
        "uiux_result": uiux_result,
        "frontend_result": frontend_result,
        "uiux_task_spec": uiux_task_spec,
        "frontend_task_spec": frontend_task_spec,
        "project_rag_context": project_rag_context,
        "artifact_rag_context": artifact_rag_context,
    }, ensure_ascii=False)


@pipeline_node("develop_global_fe_sync_gate")
def develop_global_fe_sync_gate_node(ctx: NodeContext) -> dict:
    uiux = ctx.sget("uiux_result", {}) or {}
    frontend = ctx.sget("frontend_result", {}) or {}

    def _normalize(items: list) -> set[str]:
        normalized = set()
        for item in items or []:
            text = str(item)
            normalized.add(text.split(":", 1)[-1] if ":" in text else text)
        return normalized

    ui_files = _normalize(uiux.get("files", []) or [])
    fe_files = _normalize(frontend.get("files", []) or [])
    overlap = sorted(ui_files & fe_files)

    sync_actions = []
    status = "pass"
    reason = "UI/UX and frontend plans are aligned."

    if not overlap and ui_files and fe_files:
        status = "rework_frontend"
        reason = "UI/UX handoff and frontend scope do not share explicit targets."
        sync_actions.append("Align frontend targets with UI/UX shared component scope.")

    fallback = {
        "status": status,
        "reason": reason,
        "shared_components": overlap,
        "sync_actions": sync_actions,
    }

    if ctx.api_key:
        res = call_structured(
            api_key=ctx.api_key,
            model=ctx.model,
            schema=GlobalFESyncPlanningOutput,
            system_prompt=SYSTEM_PROMPT,
            user_msg=_build_user_message(
                uiux_result=uiux,
                frontend_result=frontend,
                uiux_task_spec=ctx.sget("uiux_task_spec", {}) or {},
                frontend_task_spec=ctx.sget("frontend_task_spec", {}) or {},
                project_rag_context=ctx.sget("project_rag_context", {}) or {},
                artifact_rag_context=ctx.sget("artifact_rag_context", {}) or {},
            ),
            max_retries=3,
            temperature=0.1,
            compress_prompt=True,
        )
        return {
            "global_fe_sync_result": res.parsed.model_dump(),
            "_thinking": res.parsed.thinking or "fe-sync, shared-components, alignment",
        }

    return {
        "global_fe_sync_result": fallback,
        "_thinking": "uiux-frontend-sync, shared-components, scope-alignment",
    }
