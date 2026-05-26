from __future__ import annotations

import os
from typing import Any, Callable

from .artifacts import (
    build_approved_code_chunk_artifacts,
    build_dev_gap_decision_artifact,
    persist_dev_knowledge_artifact,
)
from .doc_updater import run_doc_updater_for_dev_gap_decision


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _post_dev_gap_decision_comment(
    task: dict[str, Any],
    decision_status: str,
    reviewed_by: str,
    run_gh: Callable[[list[str], str, str | None], tuple[int, str, str]],
) -> dict[str, Any]:
    # PM 결정 결과를 PR 대화에도 남긴다. gh 실패는 승인/거절 자체를 막지 않고 WARN으로만 반환한다.
    payload = _as_dict(task.get("payload"))
    pr_context = _as_dict(payload.get("pr_context"))
    pr_number = pr_context.get("pr_number")
    source_dir = str(payload.get("source_dir") or os.getcwd())
    if not pr_number:
        return {
            "status": "SKIPPED",
            "comment_created": False,
            "reason": "pr_number missing",
        }

    if decision_status == "APPROVED_INTENTIONAL_CHANGE":
        title = "PM approved this intentional implementation change."
        next_line = "NAVIGATOR will treat the detected GAP as an approved product decision."
    else:
        title = "PM rejected this implementation change."
        next_line = "NAVIGATOR requires the implementation to be corrected before this PR can proceed."

    reviewer_line = f"\n\nReviewed by: {reviewed_by}" if reviewed_by else ""
    body = f"## NAVIGATOR Dev Tracking Decision\n\n{title}\n\n{next_line}{reviewer_line}"
    code, out, err = run_gh(["pr", "comment", str(pr_number), "--body", body], source_dir, None)
    return {
        "status": "PASS" if code == 0 else "WARN",
        "comment_created": code == 0,
        "pr_number": pr_number,
        "decision_status": decision_status,
        "error": err if code != 0 else "",
        "stdout": out if code == 0 else "",
    }


def run_dev_gap_decision_followup(
    task: dict[str, Any],
    decision_status: str,
    reviewed_by: str = "",
    result_payload: dict[str, Any] | None = None,
    shared_db: Any = None,
    run_gh: Callable[[list[str], str, str | None], tuple[int, str, str]] | None = None,
) -> dict[str, Any]:
    # 승인/거절 이후 후속 처리를 노드와 분리해서 실행한다.
    artifact = build_dev_gap_decision_artifact(task, decision_status, reviewed_by, result_payload)
    payload = _as_dict(task.get("payload"))
    pr_context = _as_dict(artifact.get("pr_context"))
    owner = str(pr_context.get("owner") or "")
    repo = str(pr_context.get("repo") or "")
    github_token = (
        str(payload.get("github_token") or "").strip()
        or str(os.getenv("NAVIGATOR_GITHUB_TOKEN") or "").strip()
        or str(os.getenv("GITHUB_TOKEN") or "").strip()
    )

    # author: xxrin
    # 무엇: PM 승인 후 문서 반영을 doc_updater 계층으로 위임한다.
    # 왜: PM 승인 플로우의 문서 반영 책임을 명시적으로 분리해 유지보수성을 높이기 위함이다.
    doc_sync_result: dict[str, Any] = run_doc_updater_for_dev_gap_decision(
        {
            **artifact,
            "github_token": github_token,
            "pr_context": {
                **_as_dict(artifact.get("pr_context")),
                "owner": owner,
                "repo": repo,
            },
        }
    )

    if run_gh is None:
        def _missing_gh(args: list[str], cwd: str, input_text: str | None = None) -> tuple[int, str, str]:
            return 1, "", "gh runner is not configured"

        run_gh = _missing_gh

    code_chunk_artifacts = build_approved_code_chunk_artifacts(
        task,
        decision_status,
        reviewed_by,
        result_payload,
    )
    code_chunk_results = [
        persist_dev_knowledge_artifact(code_artifact, shared_db)
        for code_artifact in code_chunk_artifacts
    ]
    stored_code_chunks = [
        result for result in code_chunk_results
        if result.get("stored")
    ]

    return {
        "status": "PASS",
        "artifact": artifact,
        "rag_metadata": {
            **persist_dev_knowledge_artifact(artifact, shared_db),
            "write_enabled": True,
            "artifact_type": artifact["artifact_type"],
            "task_id": artifact.get("task_id"),
            "decision_status": decision_status,
        },
        "code_chunk_upsert": {
            # author: xxrin
            # 실제 벡터 DB가 제거된 현재 구조에서는 승인된 코드 청크만 append-only artifact로 남겨 후속 RAG 어댑터 입력으로 사용한다.
            "write_enabled": decision_status == "APPROVED_INTENTIONAL_CHANGE",
            "code_chunks_upserted": bool(stored_code_chunks),
            "stored_count": len(stored_code_chunks),
            "attempted_count": len(code_chunk_artifacts),
            "artifact_type": "APPROVED_CODE_CHUNK",
            "policy": (
                "approved_pm_decision_only"
                if decision_status == "APPROVED_INTENTIONAL_CHANGE"
                else "blocked_non_approved_decision"
            ),
            "errors": [
                result.get("error")
                for result in code_chunk_results
                if result.get("error")
            ],
        },
        "doc_sync": doc_sync_result,
        "pr_comment": _post_dev_gap_decision_comment(task, decision_status, reviewed_by, run_gh),
    }
