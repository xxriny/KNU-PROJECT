from __future__ import annotations

import json

from pipeline.domain.dev.test.fixtures import *
from pipeline.orchestration.dev_graphs import _route_loop_controller


def test_fallback_handler_creates_sa_review_request_and_project_state(tmp_path: Path) -> None:
    result = develop_fallback_handler_node(
        {
            **_base_state(tmp_path),
            "current_feature_id": "FEAT_001",
            "develop_loop_count": 1,
            "develop_max_retries": 1,
            "integration_qa_result": {
                "status": "blocked",
                "reason": "SA API contract missing for FEAT_001.",
                "findings": ["SA contract missing request schema."],
                "rework_targets": ["backend"],
            },
            "dev_feature_completion": {
                "feature_id": "FEAT_001",
                "status": "blocked",
                "reason": "integration_qa_result.status=blocked",
            },
        }
    )

    fallback = result["dev_fallback_result"]
    sa_review = result["sa_review_request"]

    assert fallback["status"] == "blocked"
    assert fallback["failed_gate"] == "IntegrationQAGate"
    assert fallback["required_action"] == "RETURN_TO_SA_REVIEW"
    assert fallback["auto_pr_blocked"] is True
    assert fallback["rag_update_blocked"] is True
    assert sa_review["status"] == "OPEN"
    assert sa_review["requested_domains"] == ["backend"]
    assert result["develop_next_action"] == "fallback"
    assert result["project_state"]["pipeline_status"] == "BLOCKED"
    assert result["project_state"]["required_action"] == "RETURN_TO_SA_REVIEW"
    assert result["project_state"]["failed_gate"] == "IntegrationQAGate"
    assert result["project_state"]["rag_sync_status"] == "BLOCKED"

    rendered = (tmp_path / "PROJECT_STATE.md").read_text(encoding="utf-8")
    payload = rendered.split("```json", 1)[1].split("```", 1)[0].strip()
    assert json.loads(payload)["required_action"] == "RETURN_TO_SA_REVIEW"


def test_loop_controller_block_routes_to_fallback() -> None:
    loop = develop_loop_controller_node(
        {
            "branch_pr_result": {"status": "blocked", "merge_ready": False},
            "integration_qa_result": {"status": "blocked"},
            "dev_feature_completion": {"status": "blocked"},
        }
    )

    assert loop["develop_next_action"] == "blocked"
    assert _route_loop_controller(loop) == "block"
