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

def test_pm_report_generator_returns_stable_schema():
    from pipeline.domain.dev_tracking.nodes import pm_report_generator

    state = {
        "pr_context": {
            "owner": "xxrin",
            "repo": "navigator",
            "pr_number": 3,
            "branch_name": "feature/auth",
            "title": "Auth endpoint",
        },
        "implementation_profile": {"implementation_summary": "Detected auth code."},
        "gap_report": [
            {
                "gap_id": "GAP_001",
                "severity": "HIGH",
                "type": "MISSING_API",
                "spec_target": "get /api/auth",
            }
        ],
        "intent_classification": [
            {
                "gap_id": "GAP_001",
                "intent": "UNINTENTIONAL",
                "recommended_action": "REQUEST_FIX",
            }
        ],
        "milestone_status": {"completion_rate": 0},
        "spec_outdated": False,
    }

    result = pm_report_generator(state)

    assert result["status"] == "PASS"
    assert result["approval_status"] == "PENDING_PM_APPROVAL"
    assert result["pm_report"]["summary"]
    assert result["pm_report"]["pr_summary"]["pr_number"] == 3
    assert len(result["pm_report"]["gap_summary"]) == 1
    assert result["pm_report"]["recommended_pm_actions"] == ["REQUEST_FIX"]

def test_pm_report_generator_exposes_llm_warnings():
    from pipeline.domain.dev_tracking.nodes import pm_report_generator

    state = {
        "pr_context": {"pr_number": 3},
        "implementation_profile": {},
        "gap_report": [],
        "intent_classification": [],
        "milestone_status": {},
        "llm_warnings": [
            {
                "node": "gap_analyzer",
                "message": "LLM GAP analysis failed; rule-based GAP draft requires PM review.",
            }
        ],
    }

    result = pm_report_generator(state)

    assert result["approval_status"] == "PENDING_PM_APPROVAL"
    assert result["pm_report"]["llm_warnings"][0]["node"] == "gap_analyzer"
    assert result["pm_report"]["recommended_pm_actions"] == ["PM_REVIEW"]
