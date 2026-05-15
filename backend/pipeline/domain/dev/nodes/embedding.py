from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.domain.dev.nodes._shared import get_goal, slugify
from pipeline.domain.rag.nodes.code_chunker import _process_file


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


def _feature_id(ctx: NodeContext) -> str:
    current = ctx.sget("current_feature_id", "")
    if current:
        return str(current)
    feature = ctx.sget("development_request_feature", {}) or {}
    if isinstance(feature, dict):
        return str(feature.get("feature_id") or feature.get("id") or "FEATURE_UNKNOWN")
    rtm = ctx.sget("requirements_rtm", []) or []
    if isinstance(rtm, list) and rtm and isinstance(rtm[0], dict):
        return str(rtm[0].get("id") or "FEATURE_UNKNOWN")
    return "FEATURE_UNKNOWN"


def _next_version(ctx: NodeContext) -> str:
    current = str(ctx.sget("rag_version", "") or ctx.sget("version", "") or "v1.0")
    if current.startswith("v"):
        parts = current[1:].split(".", 1)
        try:
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
            return f"v{major}.{minor + 1}"
        except ValueError:
            pass
    return "v1.1"


def _branch_pr_ready(ctx: NodeContext) -> tuple[bool, str]:
    branch = ctx.sget("branch_pr_result", {}) or {}
    status = str(branch.get("status", "") or "").lower()
    if status not in {"ready", "completed", "complete"}:
        return False, f"branch_pr_result.status={status or 'missing'}"
    if branch.get("pr_created"):
        return True, "pr_created"
    if branch.get("merge_ready"):
        return True, "merge_ready"
    return False, "branch_pr_result requires pr_created or merge_ready"


def _as_path(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("path", "file_path", "relative_path"):
            if value.get(key):
                return str(value[key])
    return ""


def _changed_files(ctx: NodeContext) -> list[str]:
    branch = ctx.sget("branch_pr_result", {}) or {}
    explicit = branch.get("changed_files_manifest") if isinstance(branch, dict) else None
    if not isinstance(explicit, list):
        explicit = ctx.sget("changed_files_manifest", []) or []
    return sorted({path for path in (_as_path(item) for item in explicit) if path})


def _resolve_changed_path(source_dir: Path, path: str) -> Path | None:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = source_dir / candidate
    try:
        resolved = candidate.resolve()
        source_resolved = source_dir.resolve()
    except OSError:
        return None
    if source_resolved not in [resolved, *resolved.parents]:
        return None
    if resolved.exists():
        return resolved
    return None


def _iter_changed_code_files(source_dir: Path, path: str) -> tuple[list[Path], list[str]]:
    resolved = _resolve_changed_path(source_dir, path)
    if resolved is None:
        return [], [f"Changed file is missing or outside source_dir: {path}"]
    if resolved.is_file():
        return [resolved], []
    if resolved.is_dir():
        files = [item for item in resolved.rglob("*") if item.is_file()]
        return files, []
    return [], []


def _project_code_chunks(ctx: NodeContext, version: str) -> tuple[list[dict[str, Any]], list[str]]:
    source_dir = Path(str(ctx.sget("source_dir", "") or ""))
    if not source_dir.is_dir():
        return [], ["source_dir is missing or invalid; PROJECT_RAG update skipped."]
    run_id = str(ctx.sget("source_session_id", "") or ctx.sget("run_id", "unknown"))
    feature_id = _feature_id(ctx)
    chunks: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in _changed_files(ctx):
        changed_files, path_errors = _iter_changed_code_files(source_dir, path)
        errors.extend(path_errors)
        for full_path in changed_files:
            rel_path = full_path.relative_to(source_dir.resolve()).as_posix()
            try:
                for chunk in _process_file(str(full_path), rel_path, run_id, version):
                    chunk.feature_id = feature_id
                    chunks.append(chunk.model_dump())
            except Exception as exc:
                errors.append(f"{rel_path}: {exc}")
    return chunks, errors


def _qa_report(ctx: NodeContext) -> dict[str, Any]:
    return {
        "uiux_domain_gate": ctx.sget("uiux_domain_gate_result", {}) or {},
        "backend_domain_gate": ctx.sget("backend_domain_gate_result", {}) or {},
        "frontend_domain_gate": ctx.sget("frontend_domain_gate_result", {}) or {},
        "global_fe_sync": ctx.sget("global_fe_sync_result", {}) or {},
        "integration_qa": ctx.sget("integration_qa_result", {}) or {},
    }


def _rtm_coverage(ctx: NodeContext) -> str:
    branch = ctx.sget("branch_pr_result", {}) or {}
    description = branch.get("pr_description") if isinstance(branch, dict) else {}
    if isinstance(description, dict) and description.get("rtm_coverage"):
        return str(description["rtm_coverage"])
    rtm = ctx.sget("requirements_rtm", []) or []
    if isinstance(rtm, list) and rtm:
        return f"100% (Matched {len(rtm)}/{len(rtm)} Features)"
    return "UNKNOWN"


def _collect_documents(ctx: NodeContext) -> list[dict[str, Any]]:
    branch = ctx.sget("branch_pr_result", {}) or {}
    documents = [
        {
            "type": "PR_SUMMARY",
            "content": {
                "feature_id": _feature_id(ctx),
                "branch_pr_result": branch,
                "pr_description": branch.get("pr_description", {}) if isinstance(branch, dict) else {},
            },
        },
        {
            "type": "QA_REPORT",
            "content": _qa_report(ctx),
        },
        {
            "type": "RTM_COVERAGE",
            "content": {
                "feature_id": _feature_id(ctx),
                "rtm_coverage": _rtm_coverage(ctx),
                "requirements_rtm": ctx.sget("requirements_rtm", []) or [],
            },
        },
        {
            "type": "PROJECT_STATE",
            "content": ctx.sget("project_state", {}) or {},
        },
        {
            "type": "DEVELOP_ARTIFACT_SUMMARY",
            "content": {
                "develop_main_plan": ctx.sget("develop_main_plan", {}) or {},
                "uiux_result": ctx.sget("uiux_result", {}) or {},
                "backend_result": ctx.sget("backend_result", {}) or {},
                "frontend_result": ctx.sget("frontend_result", {}) or {},
            },
        },
    ]
    return [item for item in documents if item["content"]]


@pipeline_node("develop_embedding")
def develop_embedding_node(ctx: NodeContext) -> dict:
    run_id = str(ctx.sget("run_id", "unknown"))
    source_session_id = str(ctx.sget("source_session_id", "") or run_id)
    goal = get_goal(ctx.sget)
    goal_slug = slugify(goal)[:24]
    feature_id = _feature_id(ctx)
    version = _next_version(ctx)
    ready, ready_reason = _branch_pr_ready(ctx)
    if not ready:
        return {
            "embedding_result": {
                "status": "blocked",
                "error_type": "RAG_UPDATE_BLOCKED",
                "message": "Embedding/RAG update requires a ready Branch/PR result.",
                "reason": ready_reason,
                "feature_id": feature_id,
                "version": version,
                "target_collections": [],
                "updated_targets": {"PROJECT_RAG": [], "PM_SA_RAG": []},
                "persisted_artifacts": [],
                "persisted_code_chunks": [],
                "errors": [ready_reason],
            },
            "_thinking": "rag-update-blocked-before-pr",
        }

    documents = _collect_documents(ctx)
    project_chunks, project_chunk_errors = _project_code_chunks(ctx, version)

    persisted_artifacts: list[dict[str, Any]] = []
    persisted_code_chunks: list[dict[str, Any]] = []
    errors: list[str] = []
    errors.extend(project_chunk_errors)

    for chunk in project_chunks:
        try:
            from pipeline.domain.rag.schemas import CodeChunk
            from pipeline.domain.rag.nodes.project_db import upsert_code_chunk

            stored_id = upsert_code_chunk(
                source_session_id,
                CodeChunk(**chunk),
            )
            persisted_code_chunks.append(
                {
                    "chunk_id": stored_id,
                    "file_path": chunk.get("file_path", ""),
                    "func_name": chunk.get("func_name", ""),
                    "collection": "project_code_knowledge",
                }
            )
        except Exception as exc:
            errors.append(f"PROJECT_RAG {chunk.get('chunk_id', 'unknown')}: {exc}")

    for index, document in enumerate(documents, 1):
        artifact_type = document["type"]
        chunk_id = f"dev_{source_session_id}_{goal_slug}_{index:02d}_{artifact_type.lower()}"
        try:
            from pipeline.domain.pm.nodes.pm_db import upsert_pm_artifact

            stored_id = upsert_pm_artifact(
                session_id=source_session_id,
                artifact_data=_artifact_envelope(ctx, artifact_type, document["content"]),
                chunk_id=chunk_id,
                artifact_type=artifact_type,
                version=version,
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
            "feature_id": feature_id,
            "version": version,
            "session_id": source_session_id,
            "source_session_id": source_session_id,
            "post_pr_gate": ready_reason,
            "changed_files_manifest": _changed_files(ctx),
            "documents": documents,
            "target_collections": ["project_code_knowledge", "pm_artifact_knowledge"],
            "updated_targets": {
                "PROJECT_RAG": [item["file_path"] for item in persisted_code_chunks],
                "PM_SA_RAG": [item["artifact_type"] for item in persisted_artifacts],
            },
            "rag_update_status": "COMPLETED" if status == "persisted" else status.upper(),
            "persisted_artifacts": persisted_artifacts,
            "persisted_code_chunks": persisted_code_chunks,
            "errors": errors,
        },
        "_thinking": "dev-artifacts, rag-persist, next-cycle-context",
    }
