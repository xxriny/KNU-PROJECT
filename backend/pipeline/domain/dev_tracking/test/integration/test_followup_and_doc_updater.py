import os
import sys
import asyncio
import hashlib
import hmac
import json
import subprocess
import types


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from pipeline.domain.dev_tracking.test.dev_tracking_test_utils import (
    _fake_user,
    _github_pr_payload,
    _valid_payload,
)

# author: xxrin
# 원본 대형 Dev Tracking 테스트 파일에서 기능 단위로 분리한 테스트 모듈이다.

def test_dev_gap_decision_followup_prepares_metadata_and_pr_comment(monkeypatch, dev_knowledge_db_session):
    from auth.shared_models import DevKnowledgeArtifact
    import pipeline.domain.dev_tracking.nodes as nodes

    calls = {}

    def fake_run_gh(args, cwd, input_text=None):
        calls["args"] = args
        calls["cwd"] = cwd
        return 0, "comment-url", ""

    monkeypatch.setattr(nodes, "_run_gh", fake_run_gh)
    monkeypatch.delenv("NAVIGATOR_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    result = nodes.run_dev_gap_decision_followup(
        {
            "id": "task-1",
            "payload": {
                "source_dir": "E:/navigator_v2/KNU-PROJECT",
                "pr_context": {"owner": "xxrin", "repo": "navigator", "pr_number": 7},
                "gap_report": [{"gap_id": "gap-1"}],
                "changed_files": ["app/api/auth.py"],
                "code_inventory": {
                    "files": [{"file": "app/api/auth.py", "language": "python"}],
                    "symbols_by_file": {
                        "app/api/auth.py": [{"name": "login", "type": "function", "line": 10}]
                    },
                },
                "implementation_profile": {
                    "file_role_map": {"app/api/auth.py": "auth api"}
                },
            },
        },
        "APPROVED_INTENTIONAL_CHANGE",
        "pm-1",
        {"approval_status": "APPROVED_INTENTIONAL_CHANGE"},
        shared_db=dev_knowledge_db_session,
    )
    artifacts = dev_knowledge_db_session.query(DevKnowledgeArtifact).order_by(DevKnowledgeArtifact.artifact_type).all()

    assert result["rag_metadata"]["write_enabled"] is True
    assert result["rag_metadata"]["stored"] is True
    assert result["artifact"]["summary"]["gap_count"] == 1
    assert result["code_chunk_upsert"]["write_enabled"] is True
    assert result["code_chunk_upsert"]["code_chunks_upserted"] is True
    assert result["code_chunk_upsert"]["stored_count"] == 1
    assert [artifact.artifact_type for artifact in artifacts] == [
        "APPROVED_CODE_CHUNK",
        "DEV_GAP_DECISION",
    ]
    assert "app/api/auth.py" in artifacts[0].searchable_text
    assert result["doc_sync"]["action"] == "skipped"
    assert result["pr_comment"]["comment_created"] is True
    assert calls["args"][:3] == ["pr", "comment", "7"]

def test_dev_gap_decision_followup_warns_on_rejection_comment_failure(monkeypatch, dev_knowledge_db_session):
    import pipeline.domain.dev_tracking.nodes as nodes

    def fake_run_gh(args, cwd, input_text=None):
        return 1, "", "gh auth required"

    monkeypatch.setattr(nodes, "_run_gh", fake_run_gh)
    result = nodes.run_dev_gap_decision_followup(
        {
            "id": "task-1",
            "payload": {"pr_context": {"pr_number": 7}},
        },
        "REJECTED_UNINTENTIONAL_CHANGE",
        "pm-1",
        {},
        shared_db=dev_knowledge_db_session,
    )

    assert result["status"] == "PASS"
    assert result["rag_metadata"]["stored"] is True
    assert result["code_chunk_upsert"]["write_enabled"] is False
    assert result["code_chunk_upsert"]["stored_count"] == 0
    assert result["doc_sync"]["action"] == "skipped"
    assert result["pr_comment"]["status"] == "WARN"
    assert result["pr_comment"]["error"] == "gh auth required"

def test_doc_updater_runs_sync_docs_on_approved_decision(monkeypatch):
    from pipeline.domain.dev_tracking.doc_updater import run_doc_updater_for_dev_gap_decision
    import pipeline.domain.agile.nodes.doc_sync as doc_sync_mod

    captured = {}

    def fake_sync_docs(**kwargs):
        captured.update(kwargs)
        return {"synced": True, "action": "updated"}

    monkeypatch.setattr(doc_sync_mod, "sync_docs", fake_sync_docs)

    result = run_doc_updater_for_dev_gap_decision(
        {
            "decision_status": "APPROVED_INTENTIONAL_CHANGE",
            "pr_context": {
                "owner": "xxrin",
                "repo": "navigator",
                "pr_number": 99,
                "created_at": "2026-05-24T00:00:00Z",
            },
            "reviewed_by": "pm-1",
            "gap_report": [{"gap_id": "GAP_001", "description": "approved gap"}],
            "result": {
                "reason": "요구사항 의도 반영",
                "approved_spec_version_lock": "v1.3",
            },
        }
    )

    assert result["synced"] is True
    assert result["updater"] == "doc_updater"
    assert result["decision_status"] == "APPROVED_INTENTIONAL_CHANGE"
    assert captured["owner"] == "xxrin"
    assert captured["repo"] == "navigator"
    assert captured["page_title"] == "NAVIGATOR Dev Gap Decisions - PR #99"
    assert captured["result_data"]["sa_output"]["decision_status"] == "APPROVED_INTENTIONAL_CHANGE"
    assert captured["result_data"]["sa_output"]["dev_gap_doc_update"]["approved_gaps"][0]["gap_id"] == "GAP_001"
    assert captured["result_data"]["sa_output"]["dev_gap_doc_update"]["branch_created_at"] == "2026-05-24T00:00:00Z"
    assert captured["result_data"]["sa_output"]["dev_gap_doc_update"]["approved_spec_version_lock"] == "v1.3"
    assert result["request_meta"]["has_github_token"] is False
    assert result["request_meta"]["attempts"] == 1
    assert result["update_metadata"]["reviewed_by"] == "pm-1"
    assert result["update_metadata"]["approval_reason"] == "요구사항 의도 반영"

def test_doc_updater_skips_sync_docs_on_rejected_decision():
    from pipeline.domain.dev_tracking.doc_updater import run_doc_updater_for_dev_gap_decision

    result = run_doc_updater_for_dev_gap_decision(
        {
            "decision_status": "REJECTED_UNINTENTIONAL_CHANGE",
            "pr_context": {"owner": "xxrin", "repo": "navigator"},
        }
    )

    assert result["synced"] is False
    assert result["action"] == "skipped"
    assert result["updater"] == "doc_updater"
    assert result["decision_status"] == "REJECTED_UNINTENTIONAL_CHANGE"

def test_doc_updater_retries_when_sync_docs_raises(monkeypatch):
    from pipeline.domain.dev_tracking.doc_updater import run_doc_updater_for_dev_gap_decision
    import pipeline.domain.agile.nodes.doc_sync as doc_sync_mod

    calls = {"count": 0}

    def flaky_sync_docs(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary failure")
        return {"synced": True, "action": "updated"}

    monkeypatch.setattr(doc_sync_mod, "sync_docs", flaky_sync_docs)

    result = run_doc_updater_for_dev_gap_decision(
        {
            "decision_status": "APPROVED_INTENTIONAL_CHANGE",
            "doc_update_max_attempts": 2,
            "pr_context": {"owner": "xxrin", "repo": "navigator", "pr_number": 10},
        }
    )

    assert result["synced"] is True
    assert calls["count"] == 2
    assert result["request_meta"]["attempts"] == 2
