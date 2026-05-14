from __future__ import annotations

from fastapi.testclient import TestClient

from orchestration.executor import PipelineResult
from main import app


def _previous_result() -> dict:
    return {
        "metadata": {"session_id": "source_session"},
        "requirements_rtm": [
            {
                "id": "FEAT_001",
                "description": "Users can log in with email and password.",
                "priority": "must-have",
            }
        ],
        "components": [
            {"name": "LoginPage", "domain": "frontend"},
            {"name": "AuthService", "domain": "backend"},
        ],
        "apis": [{"endpoint": "POST /api/auth/login"}],
        "tables": [{"table_name": "users"}],
        "project_overview": {"summary": "Login feature planning fixture."},
        "pm_overview": {},
        "sa_overview": {},
        "sa_artifacts": {},
    }


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_develop_endpoint_builds_backend_pipeline_payload(monkeypatch, tmp_path) -> None:
    import transport.rest_handler as rest_handler

    sentinel_pipeline = object()
    captured = {}

    def fake_execute_pipeline(pipeline, state_payload, pipeline_type, result_mutator=None):
        captured["pipeline"] = pipeline
        captured["state_payload"] = state_payload
        captured["pipeline_type"] = pipeline_type
        captured["result_mutator"] = result_mutator
        return PipelineResult(
            success=True,
            data={
                "pipeline_type": pipeline_type,
                "develop_overview": {"branch_pr_status": "ready"},
                "branch_pr_result": {"merge_ready": True},
            },
        )

    monkeypatch.setattr(rest_handler, "get_develop_pipeline", lambda: sentinel_pipeline)
    monkeypatch.setattr(rest_handler, "execute_pipeline", fake_execute_pipeline)

    source_dir = tmp_path / "target"
    source_dir.mkdir()
    payload = {
        "development_request": "Add login API and screen plan.",
        "source_dir": str(source_dir),
        "previous_result": _previous_result(),
        "api_key": "",
        "model": "",
        "enable_backend_codegen": True,
    }

    with TestClient(app) as client:
        response = client.post("/api/develop", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok", body
    assert body["data"]["pipeline_type"] == "develop_plan"
    assert body["data"]["develop_overview"]["branch_pr_status"] == "ready"
    assert body["data"]["branch_pr_result"]["merge_ready"] is True
    assert captured["pipeline"] is sentinel_pipeline
    assert captured["pipeline_type"] == "develop_plan"
    assert captured["result_mutator"] is None
    assert captured["state_payload"]["source_dir"] == str(source_dir)
    assert captured["state_payload"]["development_request"] == payload["development_request"]
    assert captured["state_payload"]["enable_backend_codegen"] is True
    assert captured["state_payload"]["requirements_rtm"] == payload["previous_result"]["requirements_rtm"]
    assert captured["state_payload"]["components"] == payload["previous_result"]["components"]
    assert captured["state_payload"]["apis"] == payload["previous_result"]["apis"]
    assert captured["state_payload"]["tables"] == payload["previous_result"]["tables"]


def test_develop_compact_response_keeps_runtime_status_fields(monkeypatch, tmp_path) -> None:
    import transport.rest_handler as rest_handler

    sentinel_pipeline = object()

    def fake_execute_pipeline(pipeline, state_payload, pipeline_type, result_mutator=None):
        data = {
            "pipeline_type": pipeline_type,
            "develop_overview": {"branch_pr_status": "ready"},
            "branch_pr_result": {
                "status": "ready",
                "merge_ready": True,
                "pr_description": {"summary": "Add login"},
            },
            "embedding_result": {
                "status": "persisted",
                "updated_targets": {"PROJECT_RAG": ["code_1"], "PM_SA_RAG": ["artifact_1"]},
            },
            "dev_message_log": [{"node": "develop_branch_pr_orchestrator", "message_type": "BRANCH_PR"}],
            "project_state": {"pipeline_status": "READY", "rag_sync_status": "PERSISTED"},
            "dev_fallback_result": {"status": "not_required"},
            "sa_review_request": {"status": "CLOSED"},
            "internal_debug_blob": {"hidden": True},
        }
        if result_mutator:
            result_mutator(data)
        return PipelineResult(success=True, data=data)

    monkeypatch.setattr(rest_handler, "get_develop_pipeline", lambda: sentinel_pipeline)
    monkeypatch.setattr(rest_handler, "execute_pipeline", fake_execute_pipeline)

    source_dir = tmp_path / "target"
    source_dir.mkdir()
    payload = {
        "development_request": "Add login API and screen plan.",
        "source_dir": str(source_dir),
        "previous_result": _previous_result(),
        "compact_response": True,
    }

    with TestClient(app) as client:
        response = client.post("/api/develop", json=payload)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["response_mode"] == "compact"
    assert data["embedding_result"]["updated_targets"]["PROJECT_RAG"] == ["code_1"]
    assert data["branch_pr_result"]["pr_description"]["summary"] == "Add login"
    assert data["dev_message_log"][0]["message_type"] == "BRANCH_PR"
    assert data["project_state"]["rag_sync_status"] == "PERSISTED"
    assert data["dev_fallback_result"]["status"] == "not_required"
    assert data["sa_review_request"]["status"] == "CLOSED"
    assert "internal_debug_blob" not in data
