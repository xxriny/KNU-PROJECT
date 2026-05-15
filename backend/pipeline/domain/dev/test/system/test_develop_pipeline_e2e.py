from __future__ import annotations

from pipeline.domain.dev.test.fixtures import *


def test_develop_pipeline_fallback_end_to_end(monkeypatch, tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")

    import pipeline.domain.dev.nodes.main_agent as main_agent
    import pipeline.domain.dev.nodes.embedding as embedding
    import pipeline.orchestration.dev_graphs as dev_graphs

    monkeypatch.setattr(
        main_agent,
        "_load_project_rag_context",
        lambda goal, source_session_id, requirements, components: {
            "session_id": source_session_id,
            "query": goal,
            "hits": 0,
            "chunks": [],
        },
    )
    monkeypatch.setattr(
        main_agent,
        "_load_artifact_rag_context",
        lambda source_session_id: {
            "session_id": source_session_id,
            "artifact_count": 0,
            "artifacts": [],
        },
    )
    monkeypatch.setattr(
        embedding,
        "upsert_pm_artifact",
        lambda **kwargs: kwargs["chunk_id"],
    )
    monkeypatch.setattr(
        embedding,
        "upsert_code_chunk",
        lambda session_id, chunk, vector=None: chunk.chunk_id,
    )
    monkeypatch.setattr(
        dev_graphs,
        "develop_backend_codegen_verifier_node",
        lambda ctx: {
            "backend_codegen_verification": {
                "status": "passed",
                "output_dir": str(tmp_path / "be"),
                "checks": [],
                "failed_checks": [],
            },
            "_thinking": "backend-verifier-fixture",
        },
    )
    monkeypatch.setattr(
        dev_graphs,
        "develop_frontend_codegen_verifier_node",
        lambda ctx: {
            "frontend_codegen_verification": {
                "status": "passed",
                "output_dir": str(tmp_path / "fe"),
                "checks": [],
                "failed_checks": [],
            },
            "_thinking": "frontend-verifier-fixture",
        },
    )
    monkeypatch.setattr(
        dev_graphs,
        "develop_fullstack_runtime_verifier_node",
        lambda ctx: {
            "fullstack_runtime_verification": {
                "status": "passed",
                "checks": [],
                "failed_checks": [],
            },
            "_thinking": "fullstack-runtime-fixture",
        },
    )
    monkeypatch.setattr(
        dev_graphs,
        "develop_frontend_qa_agent_node",
        lambda ctx: {
            "frontend_qa_result": {
                "status": "pass",
                "domain": "frontend",
                "findings": [],
                "fixes_required": [],
            },
            "_thinking": "frontend-qa-fixture",
        },
    )
    monkeypatch.setattr(
        dev_graphs,
        "develop_frontend_domain_gate_node",
        lambda ctx: {
            "frontend_domain_gate_result": {
                "status": "pass",
                "domain": "frontend",
                "reason": "Frontend QA fixture passed.",
                "blocking_findings": [],
            },
            "_thinking": "frontend-gate-fixture",
        },
    )
    monkeypatch.setattr(
        dev_graphs,
        "develop_global_fe_sync_gate_node",
        lambda ctx: {
            "global_fe_sync_result": {
                "status": "pass",
                "reason": "Global FE sync fixture passed.",
                "shared_components": [],
                "sync_actions": [],
            },
            "_thinking": "global-sync-fixture",
        },
    )
    monkeypatch.setattr(
        dev_graphs,
        "develop_integration_qa_gate_node",
        lambda ctx: {
            "integration_qa_result": {
                "status": "pass",
                "reason": "Integration QA fixture passed.",
                "findings": [],
                "rework_targets": [],
            },
            "_thinking": "integration-qa-fixture",
        },
    )

    result = execute_pipeline(
        dev_graphs.get_develop_pipeline(),
        {
            **_base_state(target_repo),
            "enable_backend_codegen": True,
            "enable_frontend_codegen": True,
            "backend_codegen_mode": "template",
            "frontend_codegen_mode": "template",
        },
        "develop_plan",
    )
    assert result.success, result.error
    data = result.data
    assert data["pipeline_type"] == "develop_plan"
    assert data["develop_overview"]["goal"]
    assert data["develop_overview"]["branch_pr_status"] == "ready"
    assert data["branch_pr_result"]["merge_ready"] is True
    assert data["embedding_result"]["status"] == "persisted"
