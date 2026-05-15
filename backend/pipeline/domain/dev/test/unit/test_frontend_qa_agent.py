from __future__ import annotations

from pipeline.domain.dev.test.fixtures import *


def test_frontend_qa_requires_handoff_based_plan() -> None:
    result = develop_frontend_qa_agent_node({
        "frontend_result": {
            "status": "draft",
            "domain": "frontend",
            "requirement_ids": ["REQ_1"],
            "proposed_changes": ["one", "two"],
            "files": ["frontend:screen"],
            "test_plan": [],
            "frontend_plan": {},
        },
        "frontend_task_spec": {},
    })["frontend_qa_result"]

    assert result["status"] == "rework"
    assert any("routes" in finding for finding in result["findings"])
    assert any("api client" in finding.lower() for finding in result["findings"])


def test_frontend_qa_static_review_blocks_generated_code_outside_sa_contract(tmp_path: Path) -> None:
    output_dir = tmp_path / "frontend_generated"
    src_dir = output_dir / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "client.tsx").write_text(
        """
        import axios from 'axios';
        export const load = () => axios.get('/api/debug');
        export function App() { return <div>success</div>; }
        """,
        encoding="utf-8",
    )
    (output_dir / "package.json").write_text(
        '{"dependencies":{"react":"^18.0.0","axios":"^1.0.0","zustand":"^4.0.0"},"devDependencies":{"vite":"^5.0.0","typescript":"^5.0.0"}}',
        encoding="utf-8",
    )

    result = develop_frontend_qa_agent_node({
        "apis": [{"endpoint": "GET /api/projects"}],
        "frontend_task_spec": {
            "requirement_ids": ["REQ_1"],
            "acceptance_criteria": ["Project list is visible."],
            "approved_stack": {"packages": ["react", "axios"]},
        },
        "frontend_result": {
            "domain": "frontend",
            "requirement_ids": ["REQ_1"],
            "files": ["frontend:Projects"],
            "proposed_changes": ["Implement projects screen", "Bind projects API"],
            "test_plan": ["Project list is visible."],
            "approved_stack": {"packages": ["react", "axios"]},
            "frontend_plan": {
                "routes": ["/projects"],
                "api_client_needs": ["GET /api/projects"],
                "screen_bindings": [{"route": "/projects", "states": ["loading", "error", "empty", "success"]}],
            },
        },
        "frontend_codegen_result": {
            "status": "generated",
            "output_dir": str(output_dir),
            "files": [{"path": str(src_dir / "client.tsx")}],
            "approved_stack": {"packages": ["react", "axios"]},
        },
    })["frontend_qa_result"]

    assert result["status"] == "rework"
    assert result["static_code_review"]["mode"] == "static_only"
    assert result["static_code_review"]["run_and_see"] is False
    assert any("absent from SA_BUNDLE" in finding for finding in result["findings"])
    assert any("outside approved_stack" in finding for finding in result["findings"])
