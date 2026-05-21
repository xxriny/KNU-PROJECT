from __future__ import annotations

from typing import Any


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
    pr_context = artifact.get("pr_context") if isinstance(artifact, dict) else {}
    if not isinstance(pr_context, dict):
        pr_context = {}

    owner = str(pr_context.get("owner") or "")
    repo = str(pr_context.get("repo") or "")
    decision_status = str(artifact.get("decision_status") or "")

    if decision_status != "APPROVED_INTENTIONAL_CHANGE":
        return {
            "synced": False,
            "action": "skipped",
            "message": "Rejected or pending Dev GAP decisions are not published to docs.",
        }

    try:
        from pipeline.domain.agile.nodes.doc_sync import sync_docs

        return sync_docs(
            result_data={"sa_output": artifact},
            github_token="",
            owner=owner,
            repo=repo,
            page_title="NAVIGATOR Dev Gap Decisions",
            project_name=repo or "NAVIGATOR",
        )
    except Exception as exc:
        return {
            "synced": False,
            "action": "error",
            "message": str(exc) or type(exc).__name__,
        }

