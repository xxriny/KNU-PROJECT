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

def test_gap_analyzer_creates_high_missing_api_gap():
    from pipeline.domain.dev_tracking.nodes import gap_analyzer

    state = {
        "published_spec_snapshot": {
            "api_contracts": [{"method": "GET", "url": "/api/missing"}],
            "component_contracts": [],
        },
        "implementation_profile": {
            "detected_apis": [{"name": "list_users", "file": "app/api/users.py"}],
            "detected_components": [],
        },
        "spec_outdated": False,
    }

    result = gap_analyzer(state)

    assert result["status"] == "PASS"
    assert result["has_high_gap"] is True
    assert result["dev_tracking_next_action"] == "intent_classifier"
    assert result["gap_report"][0]["type"] == "MISSING_API"
    assert result["gap_report"][0]["severity"] == "HIGH"
    assert result["gap_report"][0]["preliminary"] is True

def test_forensic_profiler_uses_mocked_llm(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    class Parsed:
        implementation_profile = nodes.DevImplementationProfile(
            detected_apis=[{"name": "login", "file": "app/api/auth.py"}],
            detected_components=[],
            file_role_map={"app/api/auth.py": "api"},
            implementation_summary="LLM detected auth API.",
        )

    class Result:
        parsed = Parsed()
        usage = {"input_tokens": 10}
        cost = 0.0
        retry_count = 0

    def fake_call_structured(**kwargs):
        assert kwargs["schema"] is nodes.DevImplementationProfileResponse
        assert "code_inventory" in kwargs["user_msg"]
        return Result()

    monkeypatch.setattr(nodes, "_call_structured_for_forensic", fake_call_structured)

    result = nodes.forensic_profiler(
        {
            "api_key": "test-key",
            "model": "test-model",
            "code_inventory": {"files": [{"file": "app/api/auth.py"}], "symbols_by_file": {}},
            "compress_prompt": False,
        }
    )

    assert result["status"] == "PASS"
    assert result["forensic_profiler_meta"]["mode"] == "llm"
    assert result["forensic_profiler_meta"]["preliminary"] is False
    assert result["implementation_profile"]["implementation_summary"] == "LLM detected auth API."

def test_forensic_profiler_fallback_is_preliminary(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    def fake_call_structured(**kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(nodes, "_call_structured_for_forensic", fake_call_structured)

    result = nodes.forensic_profiler(
        {
            "api_key": "test-key",
            "code_inventory": {
                "files": [{"file": "app/api/auth.py"}],
                "symbols_by_file": {"app/api/auth.py": [{"name": "login"}]},
            },
            "compress_prompt": False,
        }
    )

    assert result["forensic_profiler_meta"]["mode"] == "rule_based_fallback"
    assert result["forensic_profiler_meta"]["preliminary"] is True
    assert result["forensic_profiler_meta"]["fallback_used"] is True
    assert result["llm_warnings"][0]["node"] == "forensic_profiler"

def test_forensic_profiler_explicit_llm_flag_false_skips_llm(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    def fake_call_structured(**kwargs):
        raise AssertionError("LLM should not be called when use_llm_forensic_profiler is false")

    monkeypatch.setattr(nodes, "_call_structured_for_forensic", fake_call_structured)

    result = nodes.forensic_profiler(
        {
            "api_key": "test-key",
            "use_llm_forensic_profiler": False,
            "code_inventory": {
                "files": [{"file": "app/api/auth.py"}],
                "symbols_by_file": {"app/api/auth.py": [{"name": "login"}]},
            },
        }
    )

    assert result["forensic_profiler_meta"]["mode"] == "rule_based"
    assert result["forensic_profiler_meta"]["llm_attempted"] is False
    assert result["forensic_profiler_meta"]["preliminary"] is True

def test_forensic_profiler_uses_env_key_when_request_key_missing(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    class Parsed:
        implementation_profile = nodes.DevImplementationProfile(
            detected_apis=[],
            detected_components=[],
            file_role_map={},
            implementation_summary="LLM used env key.",
        )

    class Result:
        parsed = Parsed()
        usage = {}
        cost = 0.0
        retry_count = 0

    calls = {"forensic": 0}

    def fake_call_structured(**kwargs):
        calls["forensic"] += 1
        assert kwargs["api_key"] == ""
        return Result()

    monkeypatch.setenv("GEMINI_API_KEY", "env-test-key")
    monkeypatch.setattr(nodes, "_call_structured_for_forensic", fake_call_structured)

    result = nodes.forensic_profiler(
        {
            "code_inventory": {"files": [], "symbols_by_file": {}},
            "compress_prompt": False,
        }
    )

    assert calls["forensic"] == 1
    assert result["forensic_profiler_meta"]["mode"] == "llm"
    assert result["implementation_profile"]["implementation_summary"] == "LLM used env key."

def test_forensic_profiler_falls_back_when_llm_returns_unknown_file(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    class Parsed:
        implementation_profile = nodes.DevImplementationProfile(
            detected_apis=[{"name": "ghost_api", "file": "ghost/api.py"}],
            detected_components=[],
            file_role_map={"ghost/api.py": "api"},
            implementation_summary="Invalid invented file.",
        )

    class Result:
        parsed = Parsed()
        usage = {}
        cost = 0.0
        retry_count = 0

    monkeypatch.setattr(nodes, "_call_structured_for_forensic", lambda **kwargs: Result())

    result = nodes.forensic_profiler(
        {
            "api_key": "test-key",
            "code_inventory": {
                "files": [{"file": "app/api/auth.py"}],
                "symbols_by_file": {"app/api/auth.py": [{"name": "login"}]},
            },
            "compress_prompt": False,
        }
    )

    assert result["forensic_profiler_meta"]["mode"] == "rule_based_fallback"
    assert result["forensic_profiler_meta"]["preliminary"] is True
    assert "unknown" in result["forensic_profiler_meta"]["llm_error_message"].lower()
    assert result["implementation_profile"]["detected_apis"][0]["file"] == "app/api/auth.py"

def test_forensic_profiler_falls_back_when_llm_detected_item_missing_name(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    class Parsed:
        implementation_profile = nodes.DevImplementationProfile(
            detected_apis=[{"name": "", "file": "app/api/auth.py"}],
            detected_components=[],
            file_role_map={"app/api/auth.py": "api"},
            implementation_summary="Invalid empty name.",
        )

    class Result:
        parsed = Parsed()
        usage = {}
        cost = 0.0
        retry_count = 0

    monkeypatch.setattr(nodes, "_call_structured_for_forensic", lambda **kwargs: Result())

    result = nodes.forensic_profiler(
        {
            "api_key": "test-key",
            "code_inventory": {
                "files": [{"file": "app/api/auth.py"}],
                "symbols_by_file": {"app/api/auth.py": [{"name": "login"}]},
            },
            "compress_prompt": False,
        }
    )

    assert result["forensic_profiler_meta"]["mode"] == "rule_based_fallback"
    assert "without name/file" in result["forensic_profiler_meta"]["llm_error_message"]

def test_gap_analyzer_uses_mocked_llm(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    class Parsed:
        gaps = [
            nodes.DevGapItem(
                gap_id="GAP_LLM_001",
                severity="HIGH",
                type="MISSING_API",
                spec_target="get /api/auth",
                implementation_target=None,
                description="LLM detected missing API.",
                spec_outdated_related=False,
            )
        ]

    class Result:
        parsed = Parsed()
        usage = {"input_tokens": 10}
        cost = 0.0
        retry_count = 0

    def fake_call_structured(**kwargs):
        assert kwargs["schema"] is nodes.DevGapReportResponse
        assert "published_spec_snapshot" in kwargs["user_msg"]
        return Result()

    monkeypatch.setattr(nodes, "_call_structured_for_gap", fake_call_structured)

    result = nodes.gap_analyzer(
        {
            "api_key": "test-key",
            "published_spec_snapshot": {"api_contracts": [{"method": "GET", "url": "/api/auth"}]},
            "implementation_profile": {"detected_apis": []},
            "compress_prompt": False,
        }
    )

    assert result["gap_analyzer_meta"]["mode"] == "llm"
    assert result["gap_report"][0]["gap_id"] == "GAP_LLM_001"
    assert result["gap_report"][0]["preliminary"] is False

def test_gap_analyzer_fallback_marks_gaps_preliminary(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    def fake_call_structured(**kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(nodes, "_call_structured_for_gap", fake_call_structured)

    result = nodes.gap_analyzer(
        {
            "api_key": "test-key",
            "published_spec_snapshot": {"api_contracts": [{"method": "GET", "url": "/api/missing"}]},
            "implementation_profile": {"detected_apis": []},
            "compress_prompt": False,
        }
    )

    assert result["gap_analyzer_meta"]["mode"] == "rule_based_fallback"
    assert result["gap_report"][0]["preliminary"] is True
    assert result["llm_warnings"][0]["node"] == "gap_analyzer"

def test_gap_analyzer_explicit_llm_flag_false_skips_llm(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    def fake_call_structured(**kwargs):
        raise AssertionError("LLM should not be called when use_llm_gap_analyzer is false")

    monkeypatch.setattr(nodes, "_call_structured_for_gap", fake_call_structured)

    result = nodes.gap_analyzer(
        {
            "api_key": "test-key",
            "use_llm_gap_analyzer": False,
            "published_spec_snapshot": {"api_contracts": [{"method": "GET", "url": "/api/missing"}]},
            "implementation_profile": {"detected_apis": []},
        }
    )

    assert result["gap_analyzer_meta"]["mode"] == "rule_based"
    assert result["gap_analyzer_meta"]["llm_attempted"] is False
    assert result["gap_report"][0]["preliminary"] is True

def test_gap_analyzer_falls_back_when_llm_returns_duplicate_gap_ids(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    class Parsed:
        gaps = [
            nodes.DevGapItem(
                gap_id="GAP_DUP",
                severity="HIGH",
                type="MISSING_API",
                spec_target="get /api/auth",
                implementation_target=None,
                description="Missing auth API.",
            ),
            nodes.DevGapItem(
                gap_id="GAP_DUP",
                severity="MED",
                type="MISSING_COMPONENT",
                spec_target="AuthPanel",
                implementation_target=None,
                description="Missing auth panel.",
            ),
        ]

    class Result:
        parsed = Parsed()
        usage = {}
        cost = 0.0
        retry_count = 0

    monkeypatch.setattr(nodes, "_call_structured_for_gap", lambda **kwargs: Result())

    result = nodes.gap_analyzer(
        {
            "api_key": "test-key",
            "published_spec_snapshot": {"api_contracts": [{"method": "GET", "url": "/api/auth"}]},
            "implementation_profile": {"detected_apis": []},
            "compress_prompt": False,
        }
    )

    assert result["gap_analyzer_meta"]["mode"] == "rule_based_fallback"
    assert result["gap_report"][0]["preliminary"] is True
    assert "duplicate" in result["gap_analyzer_meta"]["llm_error_message"].lower()

def test_gap_analyzer_falls_back_when_llm_returns_empty_but_rules_find_gap(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    class Parsed:
        gaps = []

    class Result:
        parsed = Parsed()
        usage = {}
        cost = 0.0
        retry_count = 0

    monkeypatch.setattr(nodes, "_call_structured_for_gap", lambda **kwargs: Result())

    result = nodes.gap_analyzer(
        {
            "api_key": "test-key",
            "published_spec_snapshot": {"api_contracts": [{"method": "GET", "url": "/api/missing"}]},
            "implementation_profile": {"detected_apis": []},
            "compress_prompt": False,
        }
    )

    assert result["gap_analyzer_meta"]["mode"] == "rule_based_fallback"
    assert result["gap_report"][0]["type"] == "MISSING_API"
    assert result["gap_report"][0]["preliminary"] is True

def test_gap_analyzer_falls_back_when_llm_returns_empty_description(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    class Parsed:
        gaps = [
            nodes.DevGapItem(
                gap_id="GAP_001",
                severity="HIGH",
                type="MISSING_API",
                spec_target="get /api/auth",
                implementation_target=None,
                description="",
            )
        ]

    class Result:
        parsed = Parsed()
        usage = {}
        cost = 0.0
        retry_count = 0

    monkeypatch.setattr(nodes, "_call_structured_for_gap", lambda **kwargs: Result())

    result = nodes.gap_analyzer(
        {
            "api_key": "test-key",
            "published_spec_snapshot": {"api_contracts": [{"method": "GET", "url": "/api/auth"}]},
            "implementation_profile": {"detected_apis": []},
            "compress_prompt": False,
        }
    )

    assert result["gap_analyzer_meta"]["mode"] == "rule_based_fallback"
    assert "required non-empty" in result["gap_analyzer_meta"]["llm_error_message"]

def test_gap_analyzer_accepts_empty_llm_result_when_rules_find_no_gap(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    class Parsed:
        gaps = []

    class Result:
        parsed = Parsed()
        usage = {}
        cost = 0.0
        retry_count = 0

    monkeypatch.setattr(nodes, "_call_structured_for_gap", lambda **kwargs: Result())

    result = nodes.gap_analyzer(
        {
            "api_key": "test-key",
            "published_spec_snapshot": {"api_contracts": []},
            "implementation_profile": {"detected_apis": []},
            "compress_prompt": False,
        }
    )

    assert result["gap_analyzer_meta"]["mode"] == "llm"
    assert result["gap_report"] == []
    assert result["dev_tracking_next_action"] == "milestone_tracker"
