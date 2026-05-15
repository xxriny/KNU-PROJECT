from __future__ import annotations

from pipeline.domain.dev.test.fixtures import *


def test_uiux_qa_requires_structured_frontend_handoff() -> None:
    result = develop_uiux_qa_agent_node({
        "uiux_result": {
            "status": "draft",
            "domain": "uiux",
            "requirement_ids": ["REQ_1"],
            "proposed_changes": ["one", "two"],
            "files": ["uiux:screen"],
            "test_plan": [],
        },
        "uiux_artifact": {
            "status": "draft",
            "screens": [],
            "user_flows": [],
            "component_tree": [],
            "frontend_handoff": {},
        },
        "uiux_task_spec": {},
    })["uiux_qa_result"]

    assert result["status"] == "rework"
    assert any("screens" in finding for finding in result["findings"])
    assert any("frontend routes" in fix.lower() for fix in result["fixes_required"])


def test_uiux_qa_enforces_policy_and_approved_stack_handoff() -> None:
    result = develop_uiux_qa_agent_node({
        "uiux_result": {
            "status": "draft",
            "domain": "uiux",
            "requirement_ids": ["REQ_1"],
            "proposed_changes": ["Define screen", "Define flow"],
            "files": ["uiux:screen"],
            "test_plan": ["Screen meets requirement."],
            "policy_enforcement": {"status": "failed", "findings": ["UI/UX placeholder policy failed."]},
        },
        "uiux_artifact": {
            "status": "draft",
            "screens": [{
                "id": "screen_1",
                "name": "Projects",
                "purpose": "Show projects",
                "route": "/projects",
                "states": ["loading", "error"],
                "requirement_ids": ["REQ_1"],
                "acceptance_criteria": ["Screen meets requirement."],
            }],
            "user_flows": [{"id": "flow_1", "name": "View", "requirement_ids": ["REQ_1"]}],
            "component_tree": [{"name": "ProjectsScreen", "source_component": "ProjectsScreen"}],
            "empty_states": ["No projects"],
            "error_states": ["Cannot load projects"],
            "accessibility_requirements": ["Keyboard navigation"],
            "frontend_handoff": {"routes": ["/projects"], "api_client_needs": ["GET /projects"]},
        },
        "uiux_task_spec": {
            "acceptance_criteria": ["Screen meets requirement."],
            "approved_stack": {"packages": ["design-tokens"]},
            "generation_policy": {"no_dummy_code": True},
        },
    })["uiux_qa_result"]

    assert result["status"] == "rework"
    assert any("approved_stack" in finding for finding in result["findings"])
    assert any("placeholder policy" in finding.lower() for finding in result["findings"])
