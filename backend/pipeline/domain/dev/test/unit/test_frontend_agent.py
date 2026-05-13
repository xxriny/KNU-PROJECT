from __future__ import annotations

from pipeline.domain.dev.test.fixtures import *


def test_frontend_agent_uses_uiux_artifact_and_sa_contracts() -> None:
    state = {
        "frontend_task_spec": {
            "requirement_ids": ["REQ_TODO_001"],
            "target_components": ["TodoListScreen"],
        },
        "uiux_artifact": {
            "screens": [
                {
                    "name": "TodoListScreen",
                    "route": "/todo-list-screen",
                    "states": ["default", "loading", "empty", "error"],
                    "api_dependencies": ["GET /todos"],
                    "data_dependencies": ["todos.title"],
                }
            ],
            "frontend_handoff": {
                "routes": ["/todo-list-screen"],
                "api_client_needs": ["GET /todos", "POST /todos"],
                "data_contracts": ["todos.title", "todos.completed"],
                "state_management_notes": ["Use explicit loading/error states."],
            },
        },
        "apis": [{"endpoint": "GET /todos"}],
        "tables": [{"table_name": "todos", "columns": [{"name": "title"}]}],
        "backend_codegen_result": {"output_dir": "generated", "verification_adapter": "node"},
    }

    result = develop_frontend_agent_node(state)["frontend_result"]
    plan = result["frontend_plan"]
    assert plan["routes"] == ["/todo-list-screen"]
    assert "POST /todos" in plan["api_client_needs"]
    assert "todos.completed" in plan["data_contracts"]
    assert plan["screen_bindings"][0]["screen"] == "TodoListScreen"
