from __future__ import annotations

from pipeline.domain.dev.test.fixtures import *


def test_uiux_agent_generates_structured_artifact(tmp_path: Path) -> None:
    result = develop_uiux_agent_node({
        "uiux_task_spec": {
            "requirement_ids": ["REQ_TODO_001"],
            "target_components": ["TodoListScreen", "TodoEditor"],
            "acceptance_criteria": ["User can create todos"],
            "inputs": ["GET /todos", "POST /todos"],
        },
        "artifact_rag_context": {"apis": [{"endpoint": "GET /todos"}]},
    })

    artifact = result["uiux_artifact"]
    assert artifact["status"] == "ready_for_frontend"
    assert artifact["screens"]
    assert artifact["user_flows"]
    assert artifact["component_tree"]
    assert artifact["frontend_handoff"]["routes"]
    assert "GET /todos" in artifact["frontend_handoff"]["api_client_needs"]
    assert artifact["screens"][0]["requirement_ids"] == ["REQ_TODO_001"]
    assert artifact["screens"][0]["acceptance_criteria"] == ["User can create todos"]


def test_uiux_agent_traces_sa_data_and_components() -> None:
    result = develop_uiux_agent_node({
        "uiux_task_spec": {
            "requirement_ids": ["REQ_TODO_001"],
            "target_components": ["TodoListScreen"],
            "acceptance_criteria": ["User can view todos"],
        },
        "artifact_rag_context": {
            "apis": [{"endpoint": "GET /todos"}],
            "tables": [{"table_name": "todos", "columns": [{"name": "title"}, {"name": "completed"}]}],
            "components": [{"component_name": "TodoList"}],
        },
    })

    artifact = result["uiux_artifact"]
    assert "todos.title" in artifact["screens"][0]["data_dependencies"]
    assert "todos.completed" in artifact["frontend_handoff"]["data_contracts"]
    assert artifact["component_tree"][0]["source_component"] == "TodoList"
