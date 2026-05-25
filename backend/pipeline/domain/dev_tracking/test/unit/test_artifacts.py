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

def test_develop_embedding_stores_dev_gap_report_artifact(dev_knowledge_db_session):
    from auth.shared_models import DevKnowledgeArtifact
    from pipeline.domain.dev_tracking.nodes import develop_embedding

    result = develop_embedding(
        {
            "team_id": "team-1",
            "approval_task": {"task_id": "task-1"},
            "approval_status": "PENDING_PM_APPROVAL",
            "pr_context": {
                "owner": "xxrin",
                "repo": "navigator",
                "pr_number": 11,
                "branch_name": "feature/dev-tracking",
            },
            "pm_report": {"summary": "GAP report ready."},
            "gap_report": [{"gap_id": "GAP_001", "severity": "HIGH"}],
            "intent_classification": [{"gap_id": "GAP_001", "intent": "UNINTENTIONAL"}],
        },
        shared_db=dev_knowledge_db_session,
    )

    artifact = dev_knowledge_db_session.query(DevKnowledgeArtifact).one()
    assert result["status"] == "PASS"
    assert result["embedding_result"]["status"] == "stored"
    assert result["embedding_result"]["metadata"]["write_enabled"] is False
    assert result["embedding_result"]["metadata"]["code_chunks_upserted"] is False
    assert result["embedding_result"]["metadata"]["code_chunk_policy"] == "blocked_until_pm_approval"
    assert artifact.artifact_type == "DEV_GAP_REPORT"
    assert artifact.team_id == "team-1"
    assert artifact.task_id == "task-1"
    assert "GAP_001" in artifact.searchable_text
