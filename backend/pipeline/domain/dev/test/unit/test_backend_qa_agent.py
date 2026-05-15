from __future__ import annotations

from pipeline.domain.dev.test.fixtures import *


def test_backend_qa_static_review_blocks_generated_code_outside_sa_contract(tmp_path: Path) -> None:
    output_dir = tmp_path / "backend_generated"
    src_dir = output_dir / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "routes.ts").write_text(
        "router.get('/api/projects', handler);\nrouter.post('/api/debug', handler);\n",
        encoding="utf-8",
    )
    (output_dir / "package.json").write_text(
        '{"dependencies":{"express":"^4.0.0","mongoose":"^8.0.0"},"devDependencies":{"typescript":"^5.0.0"}}',
        encoding="utf-8",
    )

    result = develop_backend_qa_agent_node({
        "apis": [{"endpoint": "GET /api/projects"}],
        "tables": [{"table_name": "projects"}],
        "components": [{"name": "ProjectService"}],
        "backend_task_spec": {
            "requirement_ids": ["REQ_1"],
            "acceptance_criteria": ["Project list is available."],
            "approved_stack": {"packages": ["express"]},
        },
        "backend_result": {
            "domain": "backend",
            "requirement_ids": ["REQ_1"],
            "files": ["api:GET /api/projects"],
            "proposed_changes": ["Implement projects API", "Persist projects"],
            "test_plan": ["Project list is available."],
            "approved_stack": {"packages": ["express"]},
        },
        "backend_codegen_result": {
            "status": "generated",
            "output_dir": str(output_dir),
            "files": [{"path": str(src_dir / "routes.ts")}],
            "approved_stack": {"packages": ["express"]},
        },
    })["backend_qa_result"]

    assert result["status"] == "rework"
    assert result["static_code_review"]["mode"] == "static_only"
    assert result["static_code_review"]["run_and_see"] is False
    assert any("absent from SA_BUNDLE" in finding for finding in result["findings"])
    assert any("outside approved_stack" in finding for finding in result["findings"])


def test_domain_qa_prefers_dev_task_contracts_for_static_review(tmp_path: Path) -> None:
    output_dir = tmp_path / "backend_generated"
    src_dir = output_dir / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "routes.ts").write_text("router.get('/api/state-contract', handler);\n", encoding="utf-8")

    result = develop_backend_qa_agent_node({
        "apis": [{"endpoint": "GET /api/state-contract"}],
        "backend_task_spec": {
            "requirement_ids": ["REQ_1"],
            "dev_task": {
                "task_info": {"task_id": "task_REQ_1_BACKEND_01", "target_agent": "BackendAgent"},
                "context": {
                    "target_api_specs": [{"endpoint": "GET /api/dev-task-contract"}],
                    "target_table_specs": [],
                    "component_specs": [],
                    "approved_stack": {"packages": []},
                },
                "constraints": {"no_dummy_code": True},
            },
        },
        "backend_result": {
            "domain": "backend",
            "requirement_ids": ["REQ_1"],
            "files": ["api:GET /api/dev-task-contract"],
            "proposed_changes": ["Implement API", "Verify contract"],
            "test_plan": [],
        },
        "backend_codegen_result": {
            "status": "generated",
            "output_dir": str(output_dir),
            "files": [{"path": str(src_dir / "routes.ts")}],
        },
    })["backend_qa_result"]

    assert result["status"] == "rework"
    assert any("GET /api/dev-task-contract" in finding for finding in result["findings"])
