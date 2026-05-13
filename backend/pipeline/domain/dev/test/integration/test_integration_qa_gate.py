from __future__ import annotations

from pipeline.domain.dev.test.fixtures import *


def test_integration_qa_rework_routes_back_to_main_agent() -> None:
    assert _route_integration_qa_gate({"integration_qa_result": {"status": "rework_frontend"}}) == "retry_main"
    assert _route_integration_qa_gate({"integration_qa_result": {"status": "rework_backend"}}) == "retry_main"
    assert _route_integration_qa_gate({
        "integration_qa_result": {"status": "rework_backend"},
        "develop_integration_rework_count": 1,
    }) == "block"
    assert _route_integration_qa_gate({"integration_qa_result": {"status": "pass"}}) == "pass"


def test_integration_qa_ignores_unselected_domains() -> None:
    result = develop_integration_qa_gate_node({
        "develop_main_plan": {"selected_domains": ["backend"]},
        "backend_result": {"files": ["api:/todos"]},
        "frontend_result": {},
        "uiux_result": {},
    })["integration_qa_result"]

    assert result["status"] == "pass"


def test_integration_qa_blocks_failed_fullstack_runtime() -> None:
    result = develop_integration_qa_gate_node({
        "develop_main_plan": {"selected_domains": ["backend", "frontend"]},
        "backend_result": {"files": ["backend:api"]},
        "frontend_result": {"files": ["frontend:app"]},
        "uiux_result": {"files": ["uiux:screen"]},
        "fullstack_runtime_verification": {
            "status": "failed",
            "findings": ["Backend did not respond."],
            "rework_targets": ["backend", "frontend"],
        },
    })["integration_qa_result"]

    assert result["status"] == "rework_backend"
    assert result["rework_targets"] == ["backend", "frontend"]
    assert result["fullstack_runtime_verification"]["status"] == "failed"


def test_integration_qa_cross_checks_fe_be_code_against_sa_contract(tmp_path: Path) -> None:
    backend_dir = tmp_path / "backend_generated"
    frontend_dir = tmp_path / "frontend_generated"
    backend_src = backend_dir / "src"
    frontend_src = frontend_dir / "src"
    backend_src.mkdir(parents=True)
    frontend_src.mkdir(parents=True)
    (backend_src / "routes.ts").write_text(
        "router.get('/api/projects', handler);\n",
        encoding="utf-8",
    )
    (frontend_src / "client.ts").write_text(
        "export const load = () => axios.get('/api/messages');\n",
        encoding="utf-8",
    )

    result = develop_integration_qa_gate_node({
        "develop_main_plan": {"selected_domains": ["backend", "frontend"]},
        "backend_result": {"files": ["backend:api"]},
        "frontend_result": {"files": ["frontend:app"]},
        "uiux_result": {"files": ["uiux:screen"]},
        "apis": [{"endpoint": "GET /api/projects"}],
        "backend_codegen_result": {
            "status": "generated",
            "output_dir": str(backend_dir),
            "files": [{"path": str(backend_src / "routes.ts")}],
        },
        "frontend_codegen_result": {
            "status": "generated",
            "output_dir": str(frontend_dir),
            "files": [{"path": str(frontend_src / "client.ts")}],
        },
    })["integration_qa_result"]

    assert result["status"] == "rework_frontend"
    assert result["interface_contract_check"]["status"] == "failed"
    assert "GET /api/messages" in result["interface_contract_check"]["frontend_calls"][0]["endpoint"]
    assert "frontend" in result["rework_targets"]


def test_integration_qa_detects_frontend_payload_contract_mismatch(tmp_path: Path) -> None:
    backend_dir = tmp_path / "backend_generated"
    frontend_dir = tmp_path / "frontend_generated"
    backend_src = backend_dir / "src"
    frontend_src = frontend_dir / "src"
    backend_src.mkdir(parents=True)
    frontend_src.mkdir(parents=True)
    (backend_src / "routes.ts").write_text("router.post('/api/messages', handler);\n", encoding="utf-8")
    (frontend_src / "client.ts").write_text(
        "export const send = () => axios.post('/api/messages', { name: 'Ning' });\n",
        encoding="utf-8",
    )

    result = develop_integration_qa_gate_node({
        "develop_main_plan": {"selected_domains": ["backend", "frontend"]},
        "backend_result": {"files": ["backend:api"]},
        "frontend_result": {"files": ["frontend:app"]},
        "uiux_result": {"files": ["uiux:screen"]},
        "apis": [{
            "endpoint": "POST /api/messages",
            "request_schema": {"properties": {"senderName": {}, "senderEmail": {}, "content": {}}},
        }],
        "backend_codegen_result": {
            "status": "generated",
            "output_dir": str(backend_dir),
            "files": [{"path": str(backend_src / "routes.ts")}],
        },
        "frontend_codegen_result": {
            "status": "generated",
            "output_dir": str(frontend_dir),
            "files": [{"path": str(frontend_src / "client.ts")}],
        },
    })["integration_qa_result"]

    mismatch = result["interface_contract_check"]["mismatches"][0]
    assert result["status"] == "rework_frontend"
    assert mismatch["type"] == "fe_payload_not_matching_sa_contract"
    assert mismatch["responsible_domain"] == "frontend"


def test_integration_qa_extracts_custom_clients_fastapi_and_spring_routes(tmp_path: Path) -> None:
    backend_dir = tmp_path / "backend_generated"
    frontend_dir = tmp_path / "frontend_generated"
    backend_src = backend_dir / "src"
    frontend_src = frontend_dir / "src"
    backend_src.mkdir(parents=True)
    frontend_src.mkdir(parents=True)
    (backend_src / "routes.py").write_text(
        '@router.get("/api/projects")\ndef list_projects():\n    pass\n',
        encoding="utf-8",
    )
    (backend_src / "MessageController.java").write_text(
        '@PostMapping("/api/messages")\npublic void createMessage() {}\n',
        encoding="utf-8",
    )
    (frontend_src / "client.ts").write_text(
        "export const load = () => apiClient.get('/api/projects');\n"
        "export const send = () => client.request({ method: 'POST', url: '/api/messages' });\n",
        encoding="utf-8",
    )

    result = develop_integration_qa_gate_node({
        "develop_main_plan": {"selected_domains": ["backend", "frontend"]},
        "backend_result": {"files": ["backend:api"]},
        "frontend_result": {"files": ["frontend:app"]},
        "apis": [
            {"endpoint": "GET /api/projects"},
            {"endpoint": "POST /api/messages"},
        ],
        "backend_codegen_result": {
            "status": "generated",
            "output_dir": str(backend_dir),
            "files": [
                {"path": str(backend_src / "routes.py")},
                {"path": str(backend_src / "MessageController.java")},
            ],
        },
        "frontend_codegen_result": {
            "status": "generated",
            "output_dir": str(frontend_dir),
            "files": [{"path": str(frontend_src / "client.ts")}],
        },
    })["integration_qa_result"]

    check = result["interface_contract_check"]
    assert result["status"] == "pass"
    assert check["status"] == "pass"
    assert {call["source"] for call in check["frontend_calls"]} == {"custom_client"}
    assert {route["source"] for route in check["backend_routes"]} == {"fastapi", "spring"}
