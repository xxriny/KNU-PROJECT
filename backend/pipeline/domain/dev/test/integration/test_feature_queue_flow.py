from __future__ import annotations

from pipeline.domain.dev.test.fixtures import *
from pipeline.orchestration.dev_graphs import _route_loop_controller


def test_feature_queue_cycles_completed_feature_into_next_main_agent_scope(tmp_path: Path, monkeypatch) -> None:
    import pipeline.domain.dev.nodes.main_agent as main_agent

    monkeypatch.setattr(main_agent, "_load_project_rag_context", lambda *args, **kwargs: {"chunks": []})
    monkeypatch.setattr(main_agent, "_load_artifact_rag_context", lambda *args, **kwargs: {"artifacts": []})

    state = {
        **_base_state(tmp_path),
        "requirements_rtm": [
            {"id": "FEAT_001", "description": "User can log in.", "priority": "Must-have"},
            {
                "id": "FEAT_002",
                "description": "User can view profile after login.",
                "priority": "Must-have",
                "dependencies": ["FEAT_001"],
            },
        ],
        "components": [
            {"name": "LoginPage", "rtms": ["FEAT_001"]},
            {"name": "ProfilePage", "rtms": ["FEAT_002"]},
        ],
        "apis": [
            {"endpoint": "POST /api/auth/login", "requirement_ids": ["FEAT_001"]},
            {"endpoint": "GET /api/profile", "requirement_ids": ["FEAT_002"]},
        ],
        "tables": [
            {"table_name": "sessions", "requirement_ids": ["FEAT_001"]},
            {"table_name": "profiles", "requirement_ids": ["FEAT_002"]},
        ],
    }

    first_queue = develop_feature_queue_controller_node(state)
    assert first_queue["current_feature_id"] == "FEAT_001"

    first_main = develop_main_agent_node({**state, **first_queue})
    assert first_main["develop_main_plan"]["current_feature_id"] == "FEAT_001"
    assert first_main["requirements_rtm"] == [{"id": "FEAT_001", "description": "User can log in.", "priority": "Must-have"}]
    assert first_main["apis"] == [{"endpoint": "POST /api/auth/login", "requirement_ids": ["FEAT_001"]}]

    completion = develop_feature_completion_node({
        **state,
        **first_queue,
        **first_main,
        "branch_pr_result": {"status": "ready", "merge_ready": True},
        "integration_qa_result": {"status": "pass"},
    })
    assert completion["dev_feature_status"]["FEAT_001"] == "completed"
    assert completion["dev_feature_completion"]["has_next_feature"] is True

    loop = develop_loop_controller_node({
        **state,
        **first_queue,
        **first_main,
        **completion,
        "branch_pr_result": {"status": "ready", "merge_ready": True},
    })
    assert loop["develop_next_action"] == "next_feature"
    assert _route_loop_controller(loop) == "next_feature"

    second_queue = develop_feature_queue_controller_node({
        **state,
        **completion,
        **loop,
        "current_feature_id": "",
    })
    assert second_queue["current_feature_id"] == "FEAT_002"
    assert second_queue["dev_feature_status"]["FEAT_001"] == "completed"
    assert second_queue["dev_feature_status"]["FEAT_002"] == "in_progress"

    second_main = develop_main_agent_node({**state, **second_queue})
    assert second_main["develop_main_plan"]["current_feature_id"] == "FEAT_002"
    assert second_main["requirements_rtm"] == [
        {
            "id": "FEAT_002",
            "description": "User can view profile after login.",
            "priority": "Must-have",
            "dependencies": ["FEAT_001"],
        }
    ]
    assert second_main["frontend_task_spec"]["target_components"] == ["ProfilePage"]
    assert second_main["apis"] == [{"endpoint": "GET /api/profile", "requirement_ids": ["FEAT_002"]}]
    assert second_main["tables"] == [{"table_name": "profiles", "requirement_ids": ["FEAT_002"]}]


def test_feature_queue_does_not_select_feature_with_blocked_dependency(tmp_path: Path) -> None:
    state = {
        **_base_state(tmp_path),
        "requirements_rtm": [
            {"id": "FEAT_001", "description": "Login.", "priority": "Must-have"},
            {
                "id": "FEAT_002",
                "description": "Profile after login.",
                "priority": "Must-have",
                "dependencies": ["FEAT_001"],
            },
        ],
        "dev_feature_status": {"FEAT_001": "blocked"},
        "blocked_feature_ids": ["FEAT_001"],
    }

    result = develop_feature_queue_controller_node(state)

    assert result["current_feature_id"] == ""
    assert result["development_request_feature"] == {}
    assert result["dev_feature_status"]["FEAT_001"] == "blocked"
    assert "FEAT_002" not in result["dev_feature_status"]


def test_feature_queue_skips_blocked_dependency_and_selects_independent_feature(tmp_path: Path, monkeypatch) -> None:
    import pipeline.domain.dev.nodes.main_agent as main_agent

    monkeypatch.setattr(main_agent, "_load_project_rag_context", lambda *args, **kwargs: {"chunks": []})
    monkeypatch.setattr(main_agent, "_load_artifact_rag_context", lambda *args, **kwargs: {"artifacts": []})

    state = {
        **_base_state(tmp_path),
        "requirements_rtm": [
            {"id": "FEAT_001", "description": "Login.", "priority": "Must-have"},
            {
                "id": "FEAT_002",
                "description": "Profile after login.",
                "priority": "Must-have",
                "dependencies": ["FEAT_001"],
            },
            {"id": "FEAT_003", "description": "Show help center.", "priority": "Should-have"},
        ],
        "components": [
            {"name": "ProfilePage", "rtms": ["FEAT_002"]},
            {"name": "HelpCenterPage", "rtms": ["FEAT_003"]},
        ],
        "apis": [
            {"endpoint": "GET /api/profile", "requirement_ids": ["FEAT_002"]},
            {"endpoint": "GET /api/help", "requirement_ids": ["FEAT_003"]},
        ],
        "tables": [
            {"table_name": "profiles", "requirement_ids": ["FEAT_002"]},
            {"table_name": "help_articles", "requirement_ids": ["FEAT_003"]},
        ],
        "dev_feature_status": {"FEAT_001": "blocked"},
        "blocked_feature_ids": ["FEAT_001"],
    }

    result = develop_feature_queue_controller_node(state)
    assert result["current_feature_id"] == "FEAT_003"
    assert result["dev_feature_status"]["FEAT_001"] == "blocked"
    assert result["dev_feature_status"]["FEAT_003"] == "in_progress"
    assert "FEAT_002" not in result["dev_feature_status"]

    main_result = develop_main_agent_node({**state, **result})
    assert main_result["develop_main_plan"]["current_feature_id"] == "FEAT_003"
    assert main_result["requirements_rtm"] == [
        {"id": "FEAT_003", "description": "Show help center.", "priority": "Should-have"}
    ]
    assert main_result["frontend_task_spec"]["target_components"] == ["HelpCenterPage"]
    assert main_result["apis"] == [{"endpoint": "GET /api/help", "requirement_ids": ["FEAT_003"]}]
    assert main_result["tables"] == [{"table_name": "help_articles", "requirement_ids": ["FEAT_003"]}]
