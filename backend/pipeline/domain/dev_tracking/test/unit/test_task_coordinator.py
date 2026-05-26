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

def test_task_coordinator_creates_dev_gap_approval_task(monkeypatch):
    from pipeline.domain.agile import task_coordinator as agile_task_coordinator
    from pipeline.domain.dev_tracking.nodes import task_coordinator

    captured = {}

    def fake_create_task(**kwargs):
        captured.update(kwargs)
        return {
            "id": "task-123",
            "task_type": kwargs["task_type"],
            "status": kwargs["status"],
        }

    monkeypatch.setattr(agile_task_coordinator, "create_task", fake_create_task)

    result = task_coordinator(
        {
            "actor": {"github_id": "xxrin"},
            "team_id": "team-1",
            "approval_status": "PENDING_PM_APPROVAL",
            "pr_context": {"pr_number": 7, "branch_name": "feature/dev-tracking"},
            "pm_report": {"summary": "GAP report ready."},
            "gap_report": [{"gap_id": "GAP_001"}],
            "intent_classification": [],
            "milestone_status": {},
        }
    )

    assert result["status"] == "PASS"
    assert result["approval_task"]["task_id"] == "task-123"
    assert captured["task_type"] == "dev_gap_approval"
    assert captured["status"] == "pending_approval"
    assert captured["pr_number"] == 7
    assert captured["payload"]["pm_report"]["summary"] == "GAP report ready."
