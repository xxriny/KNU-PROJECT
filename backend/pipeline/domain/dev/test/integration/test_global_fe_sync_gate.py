from __future__ import annotations

from pipeline.domain.dev.test.fixtures import *


def test_global_fe_sync_checks_handoff_routes_against_frontend_plan() -> None:
    result = develop_global_fe_sync_gate_node({
        "uiux_result": {"files": ["uiux:TodoListScreen"]},
        "uiux_artifact": {"frontend_handoff": {"routes": ["/todos", "/todo-detail"]}},
        "frontend_result": {
            "files": ["frontend:TodoListScreen"],
            "frontend_plan": {"routes": ["/todos"]},
        },
    })["global_fe_sync_result"]

    assert result["status"] == "rework_frontend" # 불일치로 인한 재작업 지시 확인
    assert "todo-detail" in result["sync_actions"][0]


def test_global_fe_sync_checks_generated_frontend_code_against_uiux_handoff(tmp_path: Path) -> None:
    frontend_dir = tmp_path / "frontend_generated"
    src_dir = frontend_dir / "src"
    src_dir.mkdir(parents=True)
    app_file = src_dir / "App.tsx"
    app_file.write_text(
        "export default function App() { return <main><a href='/todos'>Todos</a><span>loading</span></main>; }\n",
        encoding="utf-8",
    )

    result = develop_global_fe_sync_gate_node({
        "uiux_result": {"files": ["uiux:TodoListScreen"]},
        "uiux_artifact": {
            "frontend_handoff": {
                "routes": ["/todos", "/todo-detail"],
                "api_client_needs": ["GET /todos", "POST /messages"],
            },
            "screens": [{"name": "TodoListScreen", "route": "/todos", "states": ["loading", "error", "empty"]}],
        },
        "frontend_result": {
            "files": ["frontend:TodoListScreen"],
            "frontend_plan": {"routes": ["/todos", "/todo-detail"]},
        },
        "frontend_codegen_result": {
            "status": "generated",
            "output_dir": str(frontend_dir),
            "files": [{"path": str(app_file)}],
        },
    })["global_fe_sync_result"]

    assert result["status"] == "rework_frontend"
    assert result["code_sync"]["checked"] is True
    assert any("/todo-detail" in action for action in result["sync_actions"])
    assert any("/messages" in action for action in result["sync_actions"])
    assert any("error" in action and "empty" in action for action in result["sync_actions"])
