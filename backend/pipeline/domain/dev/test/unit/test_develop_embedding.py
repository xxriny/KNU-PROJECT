from __future__ import annotations

import pipeline.domain.dev.nodes.embedding as embedding
from pipeline.domain.dev.nodes.embedding import develop_embedding_node


def test_develop_embedding_blocks_before_branch_pr_ready(tmp_path) -> None:
    result = develop_embedding_node(
        {
            "run_id": "run-rag-blocked",
            "source_dir": str(tmp_path),
            "current_feature_id": "FEAT_001",
            "branch_pr_result": {"status": "blocked", "merge_ready": False},
        }
    )["embedding_result"]

    assert result["status"] == "blocked"
    assert result["error_type"] == "RAG_UPDATE_BLOCKED"
    assert result["updated_targets"] == {"PROJECT_RAG": [], "PM_SA_RAG": []}


def test_develop_embedding_updates_project_and_pm_sa_rag_after_pr(tmp_path, monkeypatch) -> None:
    source_file = tmp_path / "backend" / "api.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text(
        "def create_message(payload):\n    return {'status': 'ok', 'payload': payload}\n",
        encoding="utf-8",
    )
    stored_artifacts: list[dict] = []
    stored_chunks: list[dict] = []

    def fake_upsert_pm_artifact(**kwargs):
        stored_artifacts.append(kwargs)
        return kwargs["chunk_id"]

    def fake_upsert_code_chunk(session_id, chunk, vector=None):
        stored_chunks.append({"session_id": session_id, "chunk": chunk.model_dump(), "vector": vector})
        return chunk.chunk_id

    monkeypatch.setattr(embedding, "upsert_pm_artifact", fake_upsert_pm_artifact)
    monkeypatch.setattr(embedding, "upsert_code_chunk", fake_upsert_code_chunk)

    result = develop_embedding_node(
        {
            "run_id": "run-rag",
            "source_session_id": "source-session",
            "source_dir": str(tmp_path),
            "current_feature_id": "FEAT_001",
            "requirements_rtm": [{"id": "FEAT_001"}],
            "branch_pr_result": {
                "status": "ready",
                "merge_ready": True,
                "pr_created": True,
                "changed_files_manifest": ["backend/api.py"],
                "pr_description": {
                    "summary": "Implement messages API",
                    "rtm_coverage": "100%",
                    "changed_files": ["backend/api.py"],
                },
            },
            "integration_qa_result": {"status": "pass"},
            "project_state": {"current_feature_id": "FEAT_001", "last_gate_status": "BRANCH_PR_READY"},
        }
    )["embedding_result"]

    assert result["status"] == "persisted"
    assert result["feature_id"] == "FEAT_001"
    assert result["version"] == "v1.1"
    assert result["post_pr_gate"] == "pr_created"
    assert result["target_collections"] == ["project_code_knowledge", "pm_artifact_knowledge"]
    assert result["updated_targets"]["PROJECT_RAG"] == ["backend/api.py"]
    assert {"PR_SUMMARY", "QA_REPORT", "RTM_COVERAGE", "PROJECT_STATE"}.issubset(
        set(result["updated_targets"]["PM_SA_RAG"])
    )
    assert stored_chunks[0]["chunk"]["feature_id"] == "FEAT_001"
    assert stored_artifacts
