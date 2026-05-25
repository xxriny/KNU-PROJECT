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

def test_analysis_persister_stores_pr_analysis_and_gap_items(dev_analysis_db_session):
    from auth.shared_models import DevGapItem, DevPrAnalysis
    from pipeline.domain.dev_tracking.nodes import analysis_persister

    result = analysis_persister(
        {
            "team_id": "team-1",
            "source_dir": "E:/navigator_v2/KNU-PROJECT",
            "pr_context": {
                "owner": "xxrin",
                "repo": "navigator",
                "pr_number": 11,
                "branch_name": "feature/dev-tracking",
                "base_branch": "main",
                "head_sha": "abc123",
                "created_at": "2026-05-24T00:00:00Z",
            },
            "published_spec_snapshot": {"snapshot_id": "snapshot-1"},
            "spec_outdated": True,
            "has_high_gap": True,
            "approval_status": "PENDING_PM_APPROVAL",
            "dev_tracking_next_action": "develop_embedding",
            "approval_task": {"task_id": "task-1"},
            "pm_report": {"summary": "GAP report ready."},
            "timeline": [{"node": "dev_task_planner", "status": "PASS"}],
            "gap_report": [
                {
                    "gap_id": "GAP_001",
                    "severity": "HIGH",
                    "type": "MISSING_API",
                    "spec_target": "get /api/auth",
                    "implementation_target": "",
                    "description": "Missing API",
                }
            ],
            "intent_classification": [
                {
                    "gap_id": "GAP_001",
                    "intent": "UNINTENTIONAL",
                    "confidence": 0.91,
                    "recommended_action": "REQUEST_FIX",
                }
            ],
        },
        shared_db=dev_analysis_db_session,
    )

    assert result["status"] == "PASS"
    assert result["analysis_persistence"]["stored"] is True
    analysis = dev_analysis_db_session.query(DevPrAnalysis).one()
    gap = dev_analysis_db_session.query(DevGapItem).one()
    assert analysis.owner == "xxrin"
    assert analysis.repo == "navigator"
    assert analysis.pr_number == 11
    assert analysis.task_id == "task-1"
    assert analysis.branch_created_at == "2026-05-24T00:00:00Z"
    assert analysis.spec_outdated is True
    assert analysis.gap_count == 1
    assert analysis.has_high_gap is True
    assert gap.analysis_id == analysis.id
    assert gap.gap_id == "GAP_001"
    assert gap.intent == "UNINTENTIONAL"
    assert gap.confidence == 0.91
    assert gap.recommended_action == "REQUEST_FIX"
    assert gap.approval_status == "PENDING_PM_APPROVAL"
