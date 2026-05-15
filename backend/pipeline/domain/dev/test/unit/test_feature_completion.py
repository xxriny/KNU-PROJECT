from __future__ import annotations

from pipeline.domain.dev.test.fixtures import *
from pipeline.orchestration.dev_graphs import _route_loop_controller


def test_feature_completion_marks_current_feature_completed_and_detects_next(tmp_path: Path) -> None:
    completion = develop_feature_completion_node({
        **_base_state(tmp_path),
        "current_feature_id": "FEAT_001",
        "dev_feature_queue": [
            {"feature_id": "FEAT_001", "status": "in_progress", "dependencies": []},
            {"feature_id": "FEAT_002", "status": "pending", "dependencies": ["FEAT_001"]},
        ],
        "dev_feature_status": {"FEAT_001": "in_progress"},
        "branch_pr_result": {"status": "ready", "merge_ready": True},
        "integration_qa_result": {"status": "pass"},
    })

    assert completion["dev_feature_status"]["FEAT_001"] == "completed"
    assert completion["completed_feature_ids"] == ["FEAT_001"]
    assert completion["blocked_feature_ids"] == []
    assert completion["dev_feature_completion"]["has_next_feature"] is True

    loop = develop_loop_controller_node({
        **_base_state(tmp_path),
        **completion,
        "branch_pr_result": {"status": "ready", "merge_ready": True},
    })
    assert loop["develop_next_action"] == "next_feature"
    assert _route_loop_controller(loop) == "next_feature"


def test_feature_completion_marks_blocked_feature(tmp_path: Path) -> None:
    completion = develop_feature_completion_node({
        **_base_state(tmp_path),
        "current_feature_id": "FEAT_001",
        "dev_feature_queue": [{"feature_id": "FEAT_001", "status": "in_progress", "dependencies": []}],
        "dev_feature_status": {"FEAT_001": "in_progress"},
        "branch_pr_result": {"status": "blocked", "merge_ready": False},
        "integration_qa_result": {"status": "blocked"},
    })

    assert completion["dev_feature_status"]["FEAT_001"] == "blocked"
    assert completion["completed_feature_ids"] == []
    assert completion["blocked_feature_ids"] == ["FEAT_001"]
    assert completion["dev_feature_completion"]["has_next_feature"] is False

    loop = develop_loop_controller_node({
        **_base_state(tmp_path),
        **completion,
        "branch_pr_result": {"status": "blocked", "merge_ready": False},
        "integration_qa_result": {"status": "blocked"},
    })
    assert loop["develop_next_action"] == "blocked"


def test_loop_controller_completes_when_no_pending_feature_remains(tmp_path: Path) -> None:
    completion = develop_feature_completion_node({
        **_base_state(tmp_path),
        "current_feature_id": "FEAT_001",
        "dev_feature_queue": [{"feature_id": "FEAT_001", "status": "in_progress", "dependencies": []}],
        "dev_feature_status": {"FEAT_001": "in_progress"},
        "branch_pr_result": {"status": "ready", "merge_ready": True},
        "integration_qa_result": {"status": "pass"},
    })

    loop = develop_loop_controller_node({
        **_base_state(tmp_path),
        **completion,
        "branch_pr_result": {"status": "ready", "merge_ready": True},
    })

    assert completion["dev_feature_completion"]["has_next_feature"] is False
    assert loop["develop_next_action"] == "complete"
