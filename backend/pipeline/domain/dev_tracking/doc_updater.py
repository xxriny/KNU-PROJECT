from __future__ import annotations

import os
from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _resolve_github_token(artifact: dict[str, Any]) -> str:
    explicit = str(artifact.get("github_token") or "").strip()
    if explicit:
        return explicit
    return str(os.getenv("NAVIGATOR_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN") or "").strip()


def _build_doc_sync_request(artifact: dict[str, Any]) -> dict[str, Any]:
    pr_context = _as_dict(artifact.get("pr_context"))
    owner = str(pr_context.get("owner") or "")
    repo = str(pr_context.get("repo") or "")
    pr_number = pr_context.get("pr_number")

    page_title = "NAVIGATOR Dev Gap Decisions"
    if pr_number not in (None, ""):
        page_title = f"NAVIGATOR Dev Gap Decisions - PR #{pr_number}"

    return {
        "result_data": {"sa_output": artifact},
        "github_token": _resolve_github_token(artifact),
        "owner": owner,
        "repo": repo,
        "page_title": page_title,
        "project_name": repo or "NAVIGATOR",
    }


def _build_update_metadata(artifact: dict[str, Any]) -> dict[str, Any]:
    pr_context = _as_dict(artifact.get("pr_context"))
    result_payload = _as_dict(artifact.get("result"))
    return {
        "reviewed_by": str(artifact.get("reviewed_by") or ""),
        "approval_reason": str(result_payload.get("reason") or result_payload.get("approval_reason") or ""),
        "decision_note": str(result_payload.get("note") or ""),
        "doc_section": "dev_tracking/pm_approved_gap_decisions",
        "pr_number": pr_context.get("pr_number"),
        "branch_name": pr_context.get("branch_name"),
    }


def _build_dev_gap_doc_update(artifact: dict[str, Any]) -> dict[str, Any]:
    pr_context = _as_dict(artifact.get("pr_context"))
    result_payload = _as_dict(artifact.get("result"))
    approved_gaps = result_payload.get("approved_gaps")
    if not isinstance(approved_gaps, list):
        approved_gaps = artifact.get("gap_report") if isinstance(artifact.get("gap_report"), list) else []
    return {
        "approved_gaps": approved_gaps,
        "spec_outdated": bool(artifact.get("spec_outdated") or result_payload.get("spec_outdated")),
        "branch_created_at": (
            pr_context.get("created_at")
            or pr_context.get("branch_created_at")
            or result_payload.get("branch_created_at")
            or ""
        ),
        "approved_spec_version_lock": str(
            result_payload.get("approved_spec_version_lock")
            or artifact.get("approved_spec_version_lock")
            or ""
        ),
        "decision_status": artifact.get("decision_status", ""),
        "reviewed_by": artifact.get("reviewed_by", ""),
        "pr_context": pr_context,
    }



def run_doc_updater_for_dev_gap_decision(
    artifact: dict[str, Any],
) -> dict[str, Any]:
    """
    PM 승인된 Dev GAP 결정을 설계 문서/위키 동기화 경로로 전달한다.

    무엇:
    - Dev Tracking 승인 결과를 doc_sync 입력 형태로 변환한다.
    - 승인(APPROVED_INTENTIONAL_CHANGE) 상태에서만 문서 동기화를 수행한다.

    왜:
    - PM 승인 플로우에서 문서 반영 책임을 doc_updater 계층으로 명시하기 위함이다.
    """
    artifact = _as_dict(artifact)
    decision_status = str(artifact.get("decision_status") or "")

    if decision_status != "APPROVED_INTENTIONAL_CHANGE":
        return {
            "synced": False,
            "action": "skipped",
            "message": "Rejected or pending Dev GAP decisions are not published to docs.",
            "updater": "doc_updater",
            "decision_status": decision_status,
        }

    try:
        from pipeline.domain.agile.nodes.doc_sync import sync_docs
        req = _build_doc_sync_request({
            **artifact,
            "dev_gap_doc_update": _build_dev_gap_doc_update(artifact),
        })
        max_attempts = int(artifact.get("doc_update_max_attempts") or 2)
        if max_attempts < 1:
            max_attempts = 1
        result = None
        last_error = ""
        attempts = 0
        for _ in range(max_attempts):
            attempts += 1
            try:
                result = sync_docs(**req)
                break
            except Exception as attempt_exc:
                last_error = str(attempt_exc) or type(attempt_exc).__name__
                result = None
        if isinstance(result, dict):
            return {
                **result,
                "updater": "doc_updater",
                "decision_status": decision_status,
                "update_metadata": _build_update_metadata(artifact),
                "request_meta": {
                    "owner": req.get("owner", ""),
                    "repo": req.get("repo", ""),
                    "page_title": req.get("page_title", ""),
                    "project_name": req.get("project_name", ""),
                    "has_github_token": bool(req.get("github_token")),
                    "attempts": attempts,
                    "max_attempts": max_attempts,
                },
            }
        if last_error:
            return {
                "synced": False,
                "action": "error",
                "message": last_error,
                "updater": "doc_updater",
                "decision_status": decision_status,
                "request_meta": {
                    "owner": req.get("owner", ""),
                    "repo": req.get("repo", ""),
                    "page_title": req.get("page_title", ""),
                    "project_name": req.get("project_name", ""),
                    "has_github_token": bool(req.get("github_token")),
                    "attempts": attempts,
                    "max_attempts": max_attempts,
                },
            }
        return {
            "synced": False,
            "action": "error",
            "message": "doc_sync returned non-dict result",
            "updater": "doc_updater",
            "decision_status": decision_status,
        }
    except Exception as exc:
        return {
            "synced": False,
            "action": "error",
            "message": str(exc) or type(exc).__name__,
            "updater": "doc_updater",
            "decision_status": decision_status,
        }
