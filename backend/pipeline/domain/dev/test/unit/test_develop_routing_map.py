from __future__ import annotations

from pipeline.orchestration.dev_graphs import (
    _develop_prerequisite_blocker,
    _route_after_main_agent,
    _route_after_uiux_gate,
    _route_branch_pr_orchestrator,
    get_develop_routing_map,
)


def test_develop_routing_map_includes_feature_queue_nodes() -> None:
    routing = get_develop_routing_map()
    next_nodes = routing["next_nodes"]

    assert routing["first_node"] == "dev_task_planner"
    assert next_nodes["dev_task_planner"] == ["develop_feature_queue_controller"]
    assert next_nodes["develop_feature_queue_controller"] == ["develop_main_agent"]
    assert "develop_feature_completion" in next_nodes["develop_embedding"]
    assert "develop_feature_queue_controller" in next_nodes["develop_loop_controller"]
    assert "develop_fallback_handler" in next_nodes["develop_loop_controller"]


def test_develop_routing_map_matches_virtual_and_blocker_handoffs() -> None:
    next_nodes = get_develop_routing_map()["next_nodes"]

    assert next_nodes["develop_uiux_domain_gate"] == [
        "develop_after_uiux_gate",
        "develop_uiux_agent",
        "develop_backend_runtime_blocker",
    ]
    assert next_nodes["develop_after_uiux_gate"] == [
        "develop_backend_agent",
        "develop_frontend_agent",
        "develop_prerequisite_blocker",
    ]
    assert next_nodes["develop_main_agent"] == [
        "develop_uiux_agent",
        "develop_backend_agent",
        "develop_frontend_agent",
        "develop_prerequisite_blocker",
    ]
    assert next_nodes["develop_branch_pr_orchestrator"] == [
        "develop_embedding",
        "develop_feature_completion",
    ]
    assert next_nodes["develop_integration_qa_gate"] == [
        "develop_branch_pr_orchestrator",
        "develop_rework_dispatcher",
        "develop_frontend_runtime_blocker",
    ]
    assert next_nodes["develop_rework_dispatcher"] == [
        "develop_uiux_agent",
        "develop_backend_agent",
        "develop_frontend_agent",
        "develop_frontend_runtime_blocker",
    ]
    assert next_nodes["develop_prerequisite_blocker"] == ["develop_feature_completion"]
    assert next_nodes["develop_backend_runtime_blocker"] == ["develop_feature_completion"]
    assert next_nodes["develop_frontend_runtime_blocker"] == ["develop_feature_completion"]
    assert next_nodes["develop_feature_completion"] == ["develop_loop_controller"]
    assert next_nodes["develop_fallback_handler"] == []


def test_direct_pr_shortcuts_route_to_prerequisite_blocker() -> None:
    state = {"develop_main_plan": {"selected_domains": []}}

    assert _route_after_main_agent(state) == "block"
    assert _route_after_uiux_gate(state) == "block"


def test_branch_pr_embedding_route_requires_ready_pr_state() -> None:
    assert _route_branch_pr_orchestrator({"branch_pr_result": {"status": "ready", "merge_ready": True}}) == "embed"
    assert _route_branch_pr_orchestrator({"branch_pr_result": {"status": "ready", "pr_created": True}}) == "embed"
    assert _route_branch_pr_orchestrator({"branch_pr_result": {"status": "blocked", "merge_ready": False}}) == "skip"
    assert _route_branch_pr_orchestrator({"branch_pr_result": {"status": "ready", "merge_ready": False}}) == "skip"


def test_prerequisite_blocker_records_project_state(tmp_path) -> None:
    result = _develop_prerequisite_blocker(
        {
            "run_id": "run-blocked",
            "source_dir": str(tmp_path),
            "current_feature_id": "FEAT_BLOCKED",
        }
    )

    assert result["integration_qa_result"]["status"] == "blocked"
    assert result["branch_pr_result"]["status"] == "blocked"
    assert result["dev_message_log"][0]["message_type"] == "GATE_RESULT"
    assert result["project_state"]["current_feature_id"] == "FEAT_BLOCKED"
    assert result["project_state"]["next_action"] == "BLOCKED_PREREQUISITE"
    assert (tmp_path / "PROJECT_STATE.md").is_file()
