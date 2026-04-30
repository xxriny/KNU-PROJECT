from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.domain.dev.nodes._shared import get_goal, slugify
from pipeline.domain.pm.nodes.pm_db import upsert_pm_artifact


def _artifact_envelope(
    ctx: NodeContext,
    artifact_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    run_id = str(ctx.sget("run_id", "unknown"))
    source_session_id = str(ctx.sget("source_session_id", "") or run_id)
    return {
        "metadata": {
            "phase": "DEV",
            "artifact_type": artifact_type,
            "session_id": source_session_id,
            "develop_run_id": run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "version": "v1.0",
        },
        "goal": get_goal(ctx.sget),
        "content": payload,
    }


def _collect_documents(ctx: NodeContext) -> list[dict[str, Any]]:
    documents = [
        {
            "type": "DEVELOP_MAIN_PLAN",
            "content": ctx.sget("develop_main_plan", {}) or {},
        },
        {
            "type": "DEVELOP_UIUX_RESULT",
            "content": ctx.sget("uiux_result", {}) or {},
        },
        {
            "type": "DEVELOP_BACKEND_RESULT",
            "content": ctx.sget("backend_result", {}) or {},
        },
        {
            "type": "DEVELOP_FRONTEND_RESULT",
            "content": ctx.sget("frontend_result", {}) or {},
        },
        {
            "type": "DEVELOP_GLOBAL_FE_SYNC",
            "content": ctx.sget("global_fe_sync_result", {}) or {},
        },
        {
            "type": "DEVELOP_INTEGRATION_QA",
            "content": ctx.sget("integration_qa_result", {}) or {},
        },
        {
            "type": "DEVELOP_BRANCH_PR_RESULT",
            "content": ctx.sget("branch_pr_result", {}) or {},
        },
    ]
    return [item for item in documents if item["content"]]


@pipeline_node("develop_embedding")
def develop_embedding_node(ctx: NodeContext) -> dict:
    run_id = str(ctx.sget("run_id", "unknown"))
    source_session_id = str(ctx.sget("source_session_id", "") or run_id)
    goal = get_goal(ctx.sget)
    goal_slug = slugify(goal)[:24]
    documents = _collect_documents(ctx)

    persisted_artifacts: list[dict[str, Any]] = []
    errors: list[str] = []

    for index, document in enumerate(documents, 1):
        artifact_type = document["type"]
        chunk_id = f"dev_{source_session_id}_{goal_slug}_{index:02d}_{artifact_type.lower()}"
        try:
            stored_id = upsert_pm_artifact(
                session_id=source_session_id,
                artifact_data=_artifact_envelope(ctx, artifact_type, document["content"]),
                chunk_id=chunk_id,
                artifact_type=artifact_type,
                version="v1.0",
                phase="DEV",
            )
            persisted_artifacts.append(
                {
                    "artifact_type": artifact_type,
                    "chunk_id": stored_id,
                    "collection": "pm_artifact_knowledge",
                }
            )
        except Exception as exc:
            errors.append(f"{artifact_type}: {exc}")

    status = "persisted"
    if errors and persisted_artifacts:
        status = "partial"
    elif errors and not persisted_artifacts:
        status = "failed"

    return {
        "embedding_result": {
            "status": status,
            "session_id": source_session_id,
            "source_session_id": source_session_id,
            "documents": documents,
            "target_collections": ["pm_artifact_knowledge"],
            "persisted_artifacts": persisted_artifacts,
            "errors": errors,
        },
        "_thinking": "dev-artifacts, rag-persist, next-cycle-context",
    }
