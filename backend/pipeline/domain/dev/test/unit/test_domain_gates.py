from __future__ import annotations

from pipeline.domain.dev.test.fixtures import *
from pipeline.domain.dev.nodes.domain_gates import (
    develop_frontend_domain_gate_node,
    develop_uiux_domain_gate_node,
)


def test_domain_gate_blocks_after_retry_budget() -> None:
    # 1회차 재시도: 상태가 rework로 설정되고 카운트 증가 확인
    first = develop_backend_domain_gate_node(
        {
            "backend_qa_result": {
                "status": "rework",
                "findings": ["API contract missing"],
                "fixes_required": ["Add request schema"],
            },
            "backend_retry_count": 0,
        }
    )
    assert first["backend_domain_gate_result"]["status"] == "rework"
    assert first["backend_retry_count"] == 1
    # 2회차 재시도 (한계 도달 시): 더 이상 루프를 돌지 않고 blocked 처리
    second = develop_backend_domain_gate_node(
        {
            "backend_qa_result": {
                "status": "rework",
                "findings": ["API contract missing"],
                "fixes_required": ["Add request schema"],
            },
            "backend_retry_count": 1,
        }
    )
    assert second["backend_domain_gate_result"]["status"] == "blocked"
    assert second["backend_domain_gate_result"]["blocking_findings"] == ["Add request schema"]


def test_backend_domain_gate_reworks_passed_qa_without_contract_evidence() -> None:
    result = develop_backend_domain_gate_node(
        {
            "apis": [{"endpoint": "POST /api/messages"}],
            "tables": [{"table_name": "messages"}],
            "backend_task_spec": {
                "acceptance_criteria": ["Messages can be created."],
                "approved_stack": {"packages": ["express"]},
            },
            "backend_result": {
                "domain": "backend",
                "requirement_ids": ["REQ_1"],
                "files": ["src/routes.ts"],
                "proposed_changes": ["Implement handler", "Add service"],
                "test_plan": [],
            },
            "backend_qa_result": {"status": "pass", "findings": [], "fixes_required": []},
            "backend_retry_count": 0,
        }
    )["backend_domain_gate_result"]

    assert result["status"] == "rework"
    assert any(not item["ready"] for item in result["evidence_checks"])
    assert any("acceptance_criteria" in item["check"] for item in result["evidence_checks"] if not item["ready"])
    assert any("API endpoints" in finding for finding in result["blocking_findings"])


def test_backend_domain_gate_passes_with_required_evidence() -> None:
    result = develop_backend_domain_gate_node(
        {
            "apis": [{"endpoint": "POST /api/messages"}],
            "tables": [{"table_name": "messages"}],
            "backend_task_spec": {
                "acceptance_criteria": ["Messages can be created."],
                "approved_stack": {"packages": ["express"]},
            },
            "backend_result": {
                "domain": "backend",
                "requirement_ids": ["REQ_1"],
                "files": ["src/routes.ts"],
                "proposed_changes": ["Implement POST /api/messages route", "Persist messages table"],
                "test_plan": ["Messages can be created."],
                "approved_stack": {"packages": ["express"]},
            },
            "backend_qa_result": {"status": "pass", "findings": [], "fixes_required": []},
            "backend_retry_count": 0,
        }
    )["backend_domain_gate_result"]

    assert result["status"] == "pass"
    assert all(item["ready"] for item in result["evidence_checks"])


def test_uiux_domain_gate_requires_fsm_and_handoff_evidence() -> None:
    result = develop_uiux_domain_gate_node(
        {
            "uiux_result": {
                "domain": "uiux",
                "requirement_ids": ["REQ_1"],
                "files": ["LoginScreen"],
                "proposed_changes": ["Design login screen", "Define form states"],
                "test_plan": ["Login has loading and error states."],
            },
            "uiux_task_spec": {
                "acceptance_criteria": ["Login has loading and error states."],
            },
            "uiux_artifact": {
                "screens": [{"id": "login", "name": "Login", "route": "/login", "requirement_ids": ["REQ_1"], "states": ["success"]}],
                "user_flows": [{"steps": ["Open form"], "success_criteria": ["Submit succeeds"]}],
                "component_tree": [{"name": "LoginForm", "source_component": "Auth"}],
                "frontend_handoff": {"routes": ["/login"], "api_client_needs": ["POST /api/login"]},
                "empty_states": ["No account"],
                "error_states": ["Invalid credentials"],
                "accessibility_requirements": ["Labels for inputs"],
            },
            "uiux_qa_result": {"status": "pass", "findings": [], "fixes_required": []},
            "uiux_retry_count": 0,
        }
    )["uiux_domain_gate_result"]

    assert result["status"] == "rework"
    assert any(item["check"] == "fsm_state_coverage" and not item["ready"] for item in result["evidence_checks"])


def test_frontend_domain_gate_requires_route_api_and_state_bindings() -> None:
    result = develop_frontend_domain_gate_node(
        {
            "frontend_result": {
                "domain": "frontend",
                "requirement_ids": ["REQ_1"],
                "files": ["src/App.tsx"],
                "proposed_changes": ["Implement login route", "Bind auth API"],
                "test_plan": ["Login handles API error."],
                "frontend_plan": {
                    "routes": ["/login"],
                    "api_client_needs": ["POST /api/login"],
                    "screen_bindings": [{"route": "/login", "states": ["success"]}],
                },
            },
            "frontend_task_spec": {
                "acceptance_criteria": ["Login handles API error."],
            },
            "frontend_qa_result": {"status": "pass", "findings": [], "fixes_required": []},
            "frontend_retry_count": 0,
        }
    )["frontend_domain_gate_result"]

    assert result["status"] == "rework"
    assert any(item["check"] == "screen_state_bindings" and not item["ready"] for item in result["evidence_checks"])
