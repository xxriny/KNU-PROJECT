from __future__ import annotations

from pipeline.domain.dev.test.fixtures import *


def test_feature_queue_selects_highest_priority_ready_feature(tmp_path: Path) -> None:
    result = develop_feature_queue_controller_node({
        **_base_state(tmp_path),
        "requirements_rtm": [
            {"id": "FEAT_003", "description": "Nice-to-have report.", "priority": "Could-have"},
            {"id": "FEAT_001", "description": "Login.", "priority": "Must-have"},
            {
                "id": "FEAT_002",
                "description": "Profile after login.",
                "priority": "Must-have",
                "dependencies": ["FEAT_001"],
            },
        ],
    })

    assert result["current_feature_id"] == "FEAT_001"
    assert result["development_request_feature"]["id"] == "FEAT_001"
    assert result["dev_feature_status"]["FEAT_001"] == "in_progress"
    assert [item["feature_id"] for item in result["dev_feature_queue"]] == ["FEAT_001", "FEAT_002", "FEAT_003"]


def test_feature_queue_skips_completed_dependencies_and_selects_next(tmp_path: Path) -> None:
    result = develop_feature_queue_controller_node({
        **_base_state(tmp_path),
        "requirements_rtm": [
            {"id": "FEAT_001", "description": "Login.", "priority": "Must-have"},
            {
                "id": "FEAT_002",
                "description": "Profile after login.",
                "priority": "Must-have",
                "dependencies": ["FEAT_001"],
            },
            {"id": "FEAT_003", "description": "Report.", "priority": "Could-have"},
        ],
        "dev_feature_status": {"FEAT_001": "completed"},
    })

    assert result["current_feature_id"] == "FEAT_002"
    assert result["dev_feature_status"]["FEAT_002"] == "in_progress"


def test_feature_queue_preserves_explicit_current_feature(tmp_path: Path) -> None:
    result = develop_feature_queue_controller_node({
        **_base_state(tmp_path),
        "current_feature_id": "FEAT_003",
        "requirements_rtm": [
            {"id": "FEAT_001", "description": "Login.", "priority": "Must-have"},
            {"id": "FEAT_003", "description": "Report.", "priority": "Could-have"},
        ],
    })

    assert result["current_feature_id"] == "FEAT_003"
    assert result["development_request_feature"]["id"] == "FEAT_003"
    assert result["dev_feature_status"]["FEAT_003"] == "in_progress"


def test_feature_queue_resumes_active_feature_without_explicit_current(tmp_path: Path) -> None:
    result = develop_feature_queue_controller_node({
        **_base_state(tmp_path),
        "requirements_rtm": [
            {"id": "FEAT_001", "description": "Login.", "priority": "Must-have"},
            {"id": "FEAT_002", "description": "Profile.", "priority": "Should-have"},
        ],
        "dev_feature_status": {"FEAT_001": "in_progress"},
    })

    assert result["current_feature_id"] == "FEAT_001"
    assert result["dev_feature_status"]["FEAT_001"] == "in_progress"
