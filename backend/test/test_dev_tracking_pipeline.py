import os
import sys
import asyncio
import hashlib
import hmac
import json
import types


BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)


def _fake_user(role="pm", user_id="user-1"):
    return types.SimpleNamespace(id=user_id, role=role)


def _valid_payload(source_dir="E:/navigator_v2/KNU-PROJECT"):
    return {
        "trigger": "GITHUB_PR_WEBHOOK",
        "repository": {"owner": "xxrin", "repo": "navigator"},
        "pull_request": {
            "pr_number": 1,
            "branch_name": "feature/dev-tracking",
            "base_branch": "main",
            "head_sha": "abc123",
            "created_at": "2026-05-19T10:00:00+09:00",
            "title": "Implement auth endpoint",
            "description": "Adds auth endpoint and PM report",
        },
        "actor": {"github_id": "xxrin", "role": "developer"},
        "source_dir": source_dir,
        "notify_pr": False,
    }


def test_dev_task_planner_valid_payload_creates_pr_context():
    from pipeline.domain.dev_tracking.nodes import dev_task_planner

    result = dev_task_planner(_valid_payload())

    assert result["status"] == "PASS"
    assert result["dev_tracking_next_action"] == "branch_fetcher"
    assert result["pr_context"]["owner"] == "xxrin"
    assert result["pr_context"]["repo"] == "navigator"
    assert result["pr_context"]["pr_number"] == 1
    assert result["pr_context"]["branch_name"] == "feature/dev-tracking"


def test_dev_task_planner_invalid_payload_reports_missing_head_sha():
    from pipeline.domain.dev_tracking.nodes import dev_task_planner

    payload = _valid_payload()
    payload["pull_request"]["head_sha"] = ""

    result = dev_task_planner(payload)

    assert result["status"] == "FAIL"
    assert result["error_type"] == "INVALID_WEBHOOK_PAYLOAD"
    assert result["dev_tracking_next_action"] == "blocked"
    assert any("pull_request.head_sha" in item for item in result["errors"])


def test_code_inventory_builder_scans_temp_project(tmp_path):
    from pipeline.domain.dev_tracking.nodes import code_inventory_builder

    api_dir = tmp_path / "app" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "users.py").write_text(
        "def list_users():\n"
        "    return []\n",
        encoding="utf-8",
    )
    component_dir = tmp_path / "src" / "components"
    component_dir.mkdir(parents=True)
    (component_dir / "UserList.jsx").write_text(
        "export function UserList() {\n"
        "  return null;\n"
        "}\n",
        encoding="utf-8",
    )

    result = code_inventory_builder({"source_dir": str(tmp_path)})

    assert result["status"] == "PASS"
    assert result["dev_tracking_next_action"] == "forensic_profiler"
    assert result["code_inventory"]["summary"]["file_count"] == 2
    assert result["code_inventory"]["summary"]["symbol_count"] >= 2


def test_pr_inventory_prioritizes_changed_files():
    from pipeline.domain.dev_tracking.nodes import _prioritize_inventory_for_pr

    inventory = {
        "files": [
            {"file": "src/unchanged.py", "internal_imports": []},
            {"file": "src/changed.py", "internal_imports": ["src/helper.py"]},
            {"file": "src/helper.py", "internal_imports": []},
        ],
        "symbols_by_file": {
            "src/changed.py": [{"name": "changed"}],
            "src/helper.py": [{"name": "helper"}],
            "src/unchanged.py": [{"name": "unchanged"}],
        },
        "summary": {"file_count": 3},
    }

    prioritized = _prioritize_inventory_for_pr(inventory, {"src/changed.py"}, max_files=3)

    assert prioritized["files"][0]["file"] == "src/changed.py"
    assert prioritized["files"][1]["file"] == "src/helper.py"
    assert prioritized["summary"]["changed_file_count"] == 1
    assert "src/changed.py" in prioritized["symbols_by_file"]


def test_split_text_chunks_keeps_chunks_under_limit():
    from pipeline.domain.dev_tracking.nodes import _split_text_chunks

    chunks = _split_text_chunks("\n".join(["x" * 20 for _ in range(10)]), 50)

    assert len(chunks) > 1
    assert all(len(chunk) <= 50 for chunk in chunks)


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


def test_intent_classifier_uses_mocked_llm(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    class Parsed:
        classifications = [
            nodes.DevGapIntentItem(
                gap_id="GAP_001",
                intent="INTENTIONAL",
                confidence=0.91,
                reason="PR description explicitly mentions this contract change.",
                recommended_action="APPROVE_AS_INTENTIONAL",
            )
        ]

    class Result:
        parsed = Parsed()
        usage = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        cost = 0.0
        retry_count = 0

    def fake_call_structured(**kwargs):
        assert kwargs["schema"] is nodes.DevGapIntentResponse
        assert "GAP_001" in kwargs["user_msg"]
        return Result()

    monkeypatch.setattr(nodes, "_call_structured_for_intent", fake_call_structured)

    result = nodes.intent_classifier(
        {
            "api_key": "test-key",
            "model": "test-model",
            "pr_context": {
                "branch_name": "feature/auth",
                "title": "Intentional auth contract change",
                "description": "Auth contract change is intentional.",
            },
            "gap_report": [
                {
                    "gap_id": "GAP_001",
                    "severity": "HIGH",
                    "type": "MISSING_API",
                    "spec_target": "get /api/auth",
                }
            ],
            "implementation_profile": {"implementation_summary": "Auth code changed."},
            "compress_prompt": False,
        }
    )

    assert result["status"] == "PASS"
    assert result["intent_classifier_meta"]["mode"] == "llm"
    assert result["intent_classification"][0]["intent"] == "INTENTIONAL"
    assert result["intent_classification"][0]["recommended_action"] == "APPROVE_AS_INTENTIONAL"


def test_intent_classifier_falls_back_when_llm_fails(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    def fake_call_structured(**kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(nodes, "_call_structured_for_intent", fake_call_structured)

    result = nodes.intent_classifier(
        {
            "api_key": "test-key",
            "pr_context": {"title": "No mention", "description": ""},
            "gap_report": [
                {
                    "gap_id": "GAP_001",
                    "severity": "HIGH",
                    "type": "MISSING_API",
                    "spec_target": "get /api/auth",
                }
            ],
            "compress_prompt": False,
        }
    )

    assert result["status"] == "PASS"
    assert result["intent_classifier_meta"]["mode"] == "rule_based_fallback"
    assert result["intent_classifier_meta"]["preliminary"] is True
    assert result["intent_classification"][0]["intent"] == "UNCERTAIN"
    assert result["intent_classification"][0]["confidence"] <= 0.5
    assert result["intent_classification"][0]["recommended_action"] == "PM_REVIEW"
    assert result["intent_classification"][0]["preliminary"] is True


def test_intent_classifier_explicit_llm_flag_false_skips_llm(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    def fake_call_structured(**kwargs):
        raise AssertionError("LLM should not be called when use_llm_intent_classifier is false")

    monkeypatch.setattr(nodes, "_call_structured_for_intent", fake_call_structured)

    result = nodes.intent_classifier(
        {
            "api_key": "test-key",
            "use_llm_intent_classifier": False,
            "gap_report": [
                {
                    "gap_id": "GAP_001",
                    "severity": "HIGH",
                    "type": "MISSING_API",
                    "spec_target": "get /api/auth",
                }
            ],
        }
    )

    assert result["intent_classifier_meta"]["mode"] == "rule_based"
    assert result["intent_classifier_meta"]["llm_attempted"] is False
    assert result["intent_classification"][0]["intent"] == "UNCERTAIN"
    assert result["intent_classification"][0]["recommended_action"] == "PM_REVIEW"


def test_intent_classifier_falls_back_on_duplicate_llm_gap_id(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    class Parsed:
        classifications = [
            nodes.DevGapIntentItem(
                gap_id="GAP_001",
                intent="UNINTENTIONAL",
                confidence=0.8,
                reason="Missing API.",
                recommended_action="REQUEST_FIX",
            ),
            nodes.DevGapIntentItem(
                gap_id="GAP_001",
                intent="UNCERTAIN",
                confidence=0.5,
                reason="Duplicate.",
                recommended_action="PM_REVIEW",
            ),
        ]

    class Result:
        parsed = Parsed()
        usage = {}
        cost = 0.0
        retry_count = 0

    monkeypatch.setattr(nodes, "_call_structured_for_intent", lambda **kwargs: Result())

    result = nodes.intent_classifier(
        {
            "api_key": "test-key",
            "gap_report": [
                {"gap_id": "GAP_001", "severity": "HIGH", "type": "MISSING_API", "spec_target": "get /api/auth"}
            ],
            "compress_prompt": False,
        }
    )

    assert result["intent_classifier_meta"]["mode"] == "rule_based_fallback"
    assert result["intent_classification"][0]["intent"] == "UNCERTAIN"
    assert result["intent_classification"][0]["recommended_action"] == "PM_REVIEW"
    assert "duplicate" in result["intent_classifier_meta"]["llm_error_message"].lower()


def test_intent_classifier_falls_back_on_unknown_llm_gap_id(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    class Parsed:
        classifications = [
            nodes.DevGapIntentItem(
                gap_id="GAP_UNKNOWN",
                intent="UNINTENTIONAL",
                confidence=0.8,
                reason="Unknown gap.",
                recommended_action="REQUEST_FIX",
            )
        ]

    class Result:
        parsed = Parsed()
        usage = {}
        cost = 0.0
        retry_count = 0

    monkeypatch.setattr(nodes, "_call_structured_for_intent", lambda **kwargs: Result())

    result = nodes.intent_classifier(
        {
            "api_key": "test-key",
            "gap_report": [
                {"gap_id": "GAP_001", "severity": "HIGH", "type": "MISSING_API", "spec_target": "get /api/auth"}
            ],
            "compress_prompt": False,
        }
    )

    assert result["intent_classifier_meta"]["mode"] == "rule_based_fallback"
    assert result["intent_classification"][0]["recommended_action"] == "PM_REVIEW"
    assert "unknown" in result["intent_classifier_meta"]["llm_error_message"].lower()


def test_intent_classifier_falls_back_when_llm_misses_gap_id(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    class Parsed:
        classifications = [
            nodes.DevGapIntentItem(
                gap_id="GAP_001",
                intent="UNINTENTIONAL",
                confidence=0.8,
                reason="Missing first API.",
                recommended_action="REQUEST_FIX",
            )
        ]

    class Result:
        parsed = Parsed()
        usage = {}
        cost = 0.0
        retry_count = 0

    monkeypatch.setattr(nodes, "_call_structured_for_intent", lambda **kwargs: Result())

    result = nodes.intent_classifier(
        {
            "api_key": "test-key",
            "gap_report": [
                {"gap_id": "GAP_001", "severity": "HIGH", "type": "MISSING_API", "spec_target": "get /api/auth"},
                {"gap_id": "GAP_002", "severity": "HIGH", "type": "MISSING_API", "spec_target": "get /api/users"},
            ],
            "compress_prompt": False,
        }
    )

    assert result["intent_classifier_meta"]["mode"] == "rule_based_fallback"
    assert {item["gap_id"] for item in result["intent_classification"]} == {"GAP_001", "GAP_002"}
    assert all(item["recommended_action"] == "PM_REVIEW" for item in result["intent_classification"])
    assert "missed" in result["intent_classifier_meta"]["llm_error_message"].lower()


def test_intent_classifier_falls_back_when_llm_approves_preliminary_gap(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    class Parsed:
        classifications = [
            nodes.DevGapIntentItem(
                gap_id="GAP_001",
                intent="INTENTIONAL",
                confidence=0.9,
                reason="Claims this is intentional.",
                recommended_action="APPROVE_AS_INTENTIONAL",
            )
        ]

    class Result:
        parsed = Parsed()
        usage = {}
        cost = 0.0
        retry_count = 0

    monkeypatch.setattr(nodes, "_call_structured_for_intent", lambda **kwargs: Result())

    result = nodes.intent_classifier(
        {
            "api_key": "test-key",
            "gap_report": [
                {
                    "gap_id": "GAP_001",
                    "severity": "HIGH",
                    "type": "MISSING_API",
                    "spec_target": "get /api/auth",
                    "preliminary": True,
                }
            ],
            "compress_prompt": False,
        }
    )

    assert result["intent_classifier_meta"]["mode"] == "rule_based_fallback"
    assert result["intent_classification"][0]["intent"] == "UNCERTAIN"
    assert result["intent_classification"][0]["recommended_action"] == "PM_REVIEW"
    assert "preliminary" in result["intent_classifier_meta"]["llm_error_message"].lower()


def test_intent_classifier_falls_back_when_llm_reason_is_empty(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    class Parsed:
        classifications = [
            nodes.DevGapIntentItem(
                gap_id="GAP_001",
                intent="UNINTENTIONAL",
                confidence=0.8,
                reason="",
                recommended_action="REQUEST_FIX",
            )
        ]

    class Result:
        parsed = Parsed()
        usage = {}
        cost = 0.0
        retry_count = 0

    monkeypatch.setattr(nodes, "_call_structured_for_intent", lambda **kwargs: Result())

    result = nodes.intent_classifier(
        {
            "api_key": "test-key",
            "gap_report": [
                {"gap_id": "GAP_001", "severity": "HIGH", "type": "MISSING_API", "spec_target": "get /api/auth"}
            ],
            "compress_prompt": False,
        }
    )

    assert result["intent_classifier_meta"]["mode"] == "rule_based_fallback"
    assert result["intent_classification"][0]["recommended_action"] == "PM_REVIEW"
    assert "empty reason" in result["intent_classifier_meta"]["llm_error_message"]


def test_intent_classifier_uses_dev_knowledge_for_rule_based_decision():
    from pipeline.domain.dev_tracking import nodes

    result = nodes.intent_classifier(
        {
            "pr_context": {"title": "Auth work", "description": ""},
            "dev_knowledge_context": (
                "[DEV_GAP_DECISION] xxrin/navigator PR #11 "
                "(APPROVED_INTENTIONAL_CHANGE)\n"
                "spec_target: get /api/auth\n"
                "decision_status: APPROVED_INTENTIONAL_CHANGE"
            ),
            "gap_report": [
                {
                    "gap_id": "GAP_001",
                    "severity": "HIGH",
                    "type": "MISSING_API",
                    "spec_target": "get /api/auth",
                }
            ],
        }
    )

    assert result["status"] == "PASS"
    assert result["intent_classifier_meta"]["mode"] == "rule_based"
    assert result["intent_classifier_meta"]["preliminary"] is True
    assert result["intent_classification"][0]["intent"] == "UNCERTAIN"
    assert result["intent_classification"][0]["recommended_action"] == "PM_REVIEW"
    assert "Existing PM decision" in result["intent_classification"][0]["reason"]


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
    assert captured["payload"]["pm_report"]["summary"] == "GAP report ready."


def test_analysis_persister_stores_pr_analysis_and_gap_items():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from auth.database import Base
    from auth.shared_models import DevGapItem, DevPrAnalysis
    from pipeline.domain.dev_tracking.nodes import analysis_persister

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        bind=engine,
        tables=[DevPrAnalysis.__table__, DevGapItem.__table__],
    )
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
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
                },
                "published_spec_snapshot": {"snapshot_id": "snapshot-1"},
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
                        "recommended_action": "REQUEST_FIX",
                    }
                ],
            },
            shared_db=session,
        )

        assert result["status"] == "PASS"
        assert result["analysis_persistence"]["stored"] is True
        analysis = session.query(DevPrAnalysis).one()
        gap = session.query(DevGapItem).one()
        assert analysis.owner == "xxrin"
        assert analysis.repo == "navigator"
        assert analysis.pr_number == 11
        assert analysis.task_id == "task-1"
        assert gap.analysis_id == analysis.id
        assert gap.gap_id == "GAP_001"
        assert gap.intent == "UNINTENTIONAL"
        assert gap.recommended_action == "REQUEST_FIX"
    finally:
        session.close()


def test_develop_embedding_stores_dev_gap_report_artifact():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from auth.database import Base
    from auth.shared_models import DevKnowledgeArtifact
    from pipeline.domain.dev_tracking.nodes import develop_embedding

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[DevKnowledgeArtifact.__table__])
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
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
            shared_db=session,
        )

        artifact = session.query(DevKnowledgeArtifact).one()
        assert result["status"] == "PASS"
        assert result["embedding_result"]["status"] == "stored"
        assert result["embedding_result"]["metadata"]["write_enabled"] is True
        assert artifact.artifact_type == "DEV_GAP_REPORT"
        assert artifact.team_id == "team-1"
        assert artifact.task_id == "task-1"
        assert "GAP_001" in artifact.searchable_text
    finally:
        session.close()


def test_query_dev_knowledge_artifacts_returns_prompt_context():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from auth.database import Base
    from auth.shared_models import DevKnowledgeArtifact
    from pipeline.domain.dev_tracking.knowledge import query_dev_knowledge_artifacts

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[DevKnowledgeArtifact.__table__])
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        session.add(
            DevKnowledgeArtifact(
                team_id="team-1",
                artifact_type="DEV_GAP_DECISION",
                owner="xxrin",
                repo="navigator",
                pr_number=11,
                branch_name="feature/dev-tracking",
                task_id="task-1",
                decision_status="APPROVED_INTENTIONAL_CHANGE",
                content_json=json.dumps({"gap": "auth endpoint"}),
                searchable_text="GAP_001 auth endpoint approved intentional change",
            )
        )
        session.add(
            DevKnowledgeArtifact(
                team_id="team-2",
                artifact_type="DEV_GAP_REPORT",
                owner="other",
                repo="repo",
                pr_number=3,
                content_json="{}",
                searchable_text="unrelated",
            )
        )
        session.commit()

        result = query_dev_knowledge_artifacts(
            session,
            team_id="team-1",
            owner="xxrin",
            repo="navigator",
            query="auth endpoint",
        )

        assert result["count"] == 1
        assert result["artifacts"][0]["artifact_type"] == "DEV_GAP_DECISION"
        assert "APPROVED_INTENTIONAL_CHANGE" in result["context_text"]
        assert "auth endpoint" in result["context_text"]
    finally:
        session.close()


def test_dev_knowledge_loader_fetches_context_for_intent_classifier():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from auth.database import Base
    from auth.shared_models import DevKnowledgeArtifact
    from pipeline.domain.dev_tracking.nodes import dev_knowledge_loader

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[DevKnowledgeArtifact.__table__])
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        session.add(
            DevKnowledgeArtifact(
                team_id="team-1",
                artifact_type="DEV_GAP_DECISION",
                owner="xxrin",
                repo="navigator",
                pr_number=11,
                decision_status="APPROVED_INTENTIONAL_CHANGE",
                content_json="{}",
                searchable_text="get /api/auth APPROVED_INTENTIONAL_CHANGE",
            )
        )
        session.commit()

        result = dev_knowledge_loader(
            {
                "team_id": "team-1",
                "dev_tracking_next_action": "intent_classifier",
                "pr_context": {"owner": "xxrin", "repo": "navigator", "title": "Auth"},
                "gap_report": [{"gap_id": "GAP_001", "spec_target": "get /api/auth"}],
            },
            shared_db=session,
        )

        assert result["status"] == "PASS"
        assert result["dev_tracking_next_action"] == "intent_classifier"
        assert result["dev_knowledge"]["count"] == 1
        assert "APPROVED_INTENTIONAL_CHANGE" in result["dev_knowledge_context"]
    finally:
        session.close()


def test_dev_tracking_knowledge_query_endpoint(monkeypatch):
    from transport.rest_handler import DevKnowledgeQueryRequest, dev_tracking_knowledge_query_endpoint

    captured = {}

    def fake_query(shared_db, **kwargs):
        captured.update(kwargs)
        return {"count": 1, "artifacts": [], "context_text": "ctx"}

    import pipeline.domain.dev_tracking.knowledge as knowledge

    monkeypatch.setattr(knowledge, "query_dev_knowledge_artifacts", fake_query)

    result = asyncio.run(
        dev_tracking_knowledge_query_endpoint(
            DevKnowledgeQueryRequest(
                team_id="team-1",
                owner="xxrin",
                repo="navigator",
                query="GAP_001",
                limit=5,
            ),
            shared_db="shared",
        )
    )

    assert result["status"] == "ok"
    assert result["data"]["context_text"] == "ctx"
    assert captured["team_id"] == "team-1"
    assert captured["query"] == "GAP_001"
    assert captured["limit"] == 5


def test_agile_impact_injects_dev_tracking_knowledge(monkeypatch):
    from pipeline.domain.agile.schemas import ImpactResult
    from transport.rest_handler import AgileImpactRequest, agile_impact

    captured = {}

    def fake_query(shared_db, **kwargs):
        captured["knowledge"] = kwargs
        return {
            "count": 1,
            "artifacts": [],
            "context_text": "DEV_GAP_DECISION auth endpoint approved",
        }

    def fake_run_impact_analyzer(**kwargs):
        captured["impact"] = kwargs
        return ImpactResult(
            change_description=kwargs["change_description"],
            impacted_components=[],
            risk_level="medium",
            summary="ok",
        )

    import pipeline.domain.agile.nodes.impact as impact_node
    import pipeline.domain.dev_tracking.knowledge as knowledge

    monkeypatch.setattr(knowledge, "query_dev_knowledge_artifacts", fake_query)
    monkeypatch.setattr(impact_node, "run_impact_analyzer", fake_run_impact_analyzer)

    result = asyncio.run(
        agile_impact(
            AgileImpactRequest(
                change_description="auth endpoint change",
                sa_data={"components": []},
                use_llm=False,
                team_id="team-1",
                owner="xxrin",
                repo="navigator",
                branch_name="feature/dev-tracking",
            ),
            shared_db="shared",
        )
    )

    assert result["status"] == "ok"
    assert captured["knowledge"]["team_id"] == "team-1"
    assert captured["knowledge"]["query"] == "auth endpoint change"
    assert captured["impact"]["dev_knowledge_context"] == "DEV_GAP_DECISION auth endpoint approved"


def test_sa_merge_project_user_message_includes_dev_tracking_knowledge():
    from pipeline.domain.sa.nodes.merge_project import _build_user_message

    message = _build_user_message(
        "UPDATE",
        "Add auth callback",
        "FastAPI detected",
        [{"feature_id": "F-1", "description": "Auth callback", "priority": "HIGH"}],
        project_context="{\"components\": []}",
        dev_knowledge_context="DEV_GAP_DECISION get /api/auth approved",
    )

    assert "[Dev Tracking Knowledge]" in message
    assert "DEV_GAP_DECISION get /api/auth approved" in message


def test_downstream_sa_user_messages_include_dev_tracking_knowledge():
    from pipeline.domain.sa.nodes.component_scheduler import _build_user_message as build_components_msg
    from pipeline.domain.sa.nodes.sa_project_structure import _build_user_msg as build_structure_msg
    from pipeline.domain.sa.nodes.sa_test_analysis import _build_user_msg as build_test_msg
    from pipeline.domain.sa.nodes.sa_unified_modeler import _build_user_message as build_unified_msg

    knowledge = "DEV_GAP_DECISION get /api/auth approved"
    merged_project = {
        "merge_strategy": "Preserve auth flow",
        "dev_knowledge_context": knowledge,
        "plan": {"requirements_rtm": [{"feature_id": "F-1", "description": "Auth"}]},
    }
    sa_bundle = {
        "data": {
            "components": [{"component_name": "AuthService"}],
            "apis": [{"endpoint": "GET /api/auth"}],
            "tables": [{"table_name": "users"}],
        }
    }

    assert knowledge in build_components_msg(merged_project, {}, "UPDATE")
    assert knowledge in build_unified_msg([], [], {}, "UPDATE", dev_knowledge_context=knowledge)
    assert knowledge in build_test_msg(sa_bundle, [], "UPDATE", dev_knowledge_context=knowledge)
    assert knowledge in build_structure_msg(sa_bundle, {}, [], "UPDATE", dev_knowledge_context=knowledge)


def test_analyze_update_injects_dev_tracking_knowledge(monkeypatch):
    import transport.rest_handler as rest_handler
    from transport.rest_handler import AnalysisRequest, analyze

    captured = {}

    def fake_query(shared_db, **kwargs):
        captured["knowledge"] = kwargs
        return {"context_text": "DEV_GAP_DECISION auth approved", "count": 1, "artifacts": []}

    def fake_execute_pipeline(pipeline, state, pipeline_type):
        captured["state"] = state
        captured["pipeline_type"] = pipeline_type
        return types.SimpleNamespace(success=True, data=state, error="")

    import pipeline.domain.dev_tracking.knowledge as knowledge

    monkeypatch.setattr(rest_handler, "_ensure_pipeline", lambda: None)
    monkeypatch.setattr(rest_handler, "normalize_action_type", lambda value: value, raising=False)
    monkeypatch.setattr(rest_handler, "validate_analysis_inputs", lambda action_type, idea, source_dir: None, raising=False)
    monkeypatch.setattr(rest_handler, "get_analysis_pipeline", lambda action_type: "pipeline", raising=False)
    monkeypatch.setattr(rest_handler, "analysis_pipeline_type", lambda action_type: "analysis_update", raising=False)
    monkeypatch.setattr(rest_handler, "execute_pipeline", fake_execute_pipeline, raising=False)
    monkeypatch.setattr(knowledge, "query_dev_knowledge_artifacts", fake_query)

    result = asyncio.run(
        analyze(
            AnalysisRequest(
                idea="auth callback",
                context="{\"components\": []}",
                action_type="UPDATE",
                team_id="team-1",
                owner="xxrin",
                repo="navigator",
            ),
            shared_db="shared",
        )
    )

    assert result["status"] == "ok"
    assert captured["knowledge"]["query"] == "auth callback"
    assert captured["state"]["dev_knowledge_context"] == "DEV_GAP_DECISION auth approved"
    assert captured["pipeline_type"] == "analysis_update"


def _github_pr_payload(action="opened"):
    return {
        "action": action,
        "repository": {
            "name": "navigator",
            "owner": {"login": "xxrin"},
        },
        "number": 17,
        "pull_request": {
            "number": 17,
            "head": {"ref": "feature/dev-tracking", "sha": "abc123"},
            "base": {"ref": "main"},
            "created_at": "2026-05-19T10:00:00Z",
            "title": "Dev tracking webhook",
            "body": "Webhook smoke test",
        },
        "sender": {"login": "xxrin"},
    }


def test_github_webhook_signature_validation_accepts_valid_signature():
    from transport.rest_handler import _verify_github_webhook_signature

    body = b'{"action":"opened"}'
    secret = "webhook-secret"
    signature = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    verified, error = _verify_github_webhook_signature(body, signature, secret)

    assert verified is True
    assert error == ""


def test_github_webhook_signature_validation_rejects_invalid_signature():
    from transport.rest_handler import _verify_github_webhook_signature

    verified, error = _verify_github_webhook_signature(
        b'{"action":"opened"}',
        "sha256=bad",
        "webhook-secret",
    )

    assert verified is False
    assert "invalid" in error.lower()


def test_normalize_github_pr_webhook_maps_to_dev_tracking_shape():
    from transport.rest_handler import _normalize_github_pr_webhook

    normalized = _normalize_github_pr_webhook(_github_pr_payload())

    assert normalized["trigger"] == "GITHUB_PR_WEBHOOK"
    assert normalized["repository"] == {"owner": "xxrin", "repo": "navigator"}
    assert normalized["pull_request"]["pr_number"] == 17
    assert normalized["pull_request"]["branch_name"] == "feature/dev-tracking"
    assert normalized["pull_request"]["base_branch"] == "main"
    assert normalized["pull_request"]["head_sha"] == "abc123"
    assert normalized["actor"]["github_id"] == "xxrin"


def test_github_pulls_endpoint_returns_open_pr_shape(monkeypatch):
    import connectors.github_connector as github_connector
    from transport.rest_handler import GitHubPullsRequest, github_pulls

    captured = {}

    class FakeGitHubConnector:
        def __init__(self, token):
            captured["token"] = token

        def list_pull_requests(self, owner, repo, state, limit):
            captured["args"] = (owner, repo, state, limit)
            # author: xxrin
            # UI가 PR 선택만으로 Dev Tracking 실행값을 채울 수 있는 응답 shape를 보장한다.
            return [
                types.SimpleNamespace(
                    number=17,
                    title="Dev tracking webhook",
                    state="open",
                    author="xxrin",
                    head_branch="feature/dev-tracking",
                    base_branch="main",
                    head_sha="abc123",
                    updated_at="2026-05-24T00:00:00",
                    url="https://github.com/xxrin/navigator/pull/17",
                )
            ]

    monkeypatch.setattr(github_connector, "GitHubConnector", FakeGitHubConnector)

    result = asyncio.run(github_pulls(
        GitHubPullsRequest(owner="xxrin", repo="navigator", state="open", limit=10),
        current_user=types.SimpleNamespace(github_oauth_token="token-123"),
    ))

    assert result["status"] == "ok"
    assert captured["token"] == "token-123"
    assert captured["args"] == ("xxrin", "navigator", "open", 10)
    assert result["data"][0]["number"] == 17
    assert result["data"][0]["head_branch"] == "feature/dev-tracking"
    assert result["data"][0]["base_branch"] == "main"
    assert result["data"][0]["head_sha"] == "abc123"


def test_github_branches_endpoint_keeps_head_sha_for_ui(monkeypatch):
    import connectors.github_connector as github_connector
    from transport.rest_handler import GitHubAnalyticsRequest, github_branches

    class FakeGitHubConnector:
        def __init__(self, token):
            self.token = token

        def list_branches(self, owner, repo):
            # author: xxrin
            # Branch picker가 선택값만으로 head_sha를 채울 수 있는 응답을 유지한다.
            return [{"name": "feature/dev-tracking", "protected": False, "sha": "abc123"}]

    monkeypatch.setattr(github_connector, "GitHubConnector", FakeGitHubConnector)

    result = asyncio.run(github_branches(
        GitHubAnalyticsRequest(owner="xxrin", repo="navigator", branch="main", limit=100),
        current_user=types.SimpleNamespace(github_oauth_token="token-123"),
    ))

    assert result["status"] == "ok"
    assert result["data"][0]["name"] == "feature/dev-tracking"
    assert result["data"][0]["sha"] == "abc123"


def test_serialize_dev_pr_analysis_returns_ui_history_shape():
    from transport.rest_handler import _serialize_dev_pr_analysis

    row = types.SimpleNamespace(
        id="analysis-1",
        team_id="team-1",
        owner="xxrin",
        repo="navigator",
        pr_number=17,
        branch_name="feature/dev-tracking",
        base_branch="main",
        head_sha="abc123",
        source_dir="/repo",
        spec_snapshot_id="snapshot-1",
        approval_status="PENDING_PM_APPROVAL",
        analysis_status="pm_approval_pending",
        task_id="task-1",
        pm_report=json.dumps({"summary": "GAP 검토 필요"}, ensure_ascii=False),
        timeline=json.dumps([{"node": "gap_analyzer", "status": "PASS"}], ensure_ascii=False),
        created_at=types.SimpleNamespace(isoformat=lambda: "2026-05-24T00:00:00"),
        gap_items=[
            types.SimpleNamespace(severity="HIGH"),
            types.SimpleNamespace(severity="LOW"),
        ],
    )

    serialized = _serialize_dev_pr_analysis(row)

    assert serialized["id"] == "analysis-1"
    assert serialized["pr_number"] == 17
    assert serialized["gap_count"] == 2
    assert serialized["high_gap_count"] == 1
    assert serialized["pm_report_summary"] == "GAP 검토 필요"
    assert serialized["timeline"][0]["node"] == "gap_analyzer"


def test_serialize_dev_pr_analysis_detail_includes_gap_items():
    from transport.rest_handler import _serialize_dev_pr_analysis_detail

    row = types.SimpleNamespace(
        id="analysis-1",
        team_id="team-1",
        owner="xxrin",
        repo="navigator",
        pr_number=17,
        branch_name="feature/dev-tracking",
        base_branch="main",
        head_sha="abc123",
        source_dir="/repo",
        spec_snapshot_id="snapshot-1",
        approval_status="PENDING_PM_APPROVAL",
        analysis_status="pm_approval_pending",
        task_id="task-1",
        pm_report=json.dumps({"summary": "GAP 검토 필요"}, ensure_ascii=False),
        timeline="[]",
        created_at=None,
        gap_items=[
            types.SimpleNamespace(
                id="gap-row-1",
                gap_id="GAP_001",
                severity="HIGH",
                type="MISSING_API",
                spec_target="GET /api/dev",
                implementation_target="",
                intent="UNCERTAIN",
                recommended_action="PM_REVIEW",
                description="API가 구현되지 않음",
                created_at=None,
            )
        ],
    )

    serialized = _serialize_dev_pr_analysis_detail(row)

    assert serialized["gap_count"] == 1
    assert serialized["pm_report"]["summary"] == "GAP 검토 필요"
    assert serialized["gap_items"][0]["gap_id"] == "GAP_001"
    assert serialized["gap_items"][0]["description"] == "API가 구현되지 않음"


def test_github_webhook_endpoint_ignores_non_pr_event():
    from transport.rest_handler import github_webhook_endpoint

    class FakeRequest:
        headers = {"X-GitHub-Event": "push"}

        async def body(self):
            return json.dumps({"ref": "refs/heads/main"}).encode("utf-8")

    result = asyncio.run(github_webhook_endpoint(FakeRequest(), shared_db=None))

    assert result["status"] == "ok"
    assert result["handled"] is False
    assert "ignored event" in result["reason"]


def test_github_webhook_endpoint_ignores_unsupported_pr_action():
    from transport.rest_handler import github_webhook_endpoint

    class FakeRequest:
        headers = {"X-GitHub-Event": "pull_request"}

        async def body(self):
            return json.dumps(_github_pr_payload(action="closed")).encode("utf-8")

    result = asyncio.run(github_webhook_endpoint(FakeRequest(), shared_db=None))

    assert result["status"] == "ok"
    assert result["handled"] is False
    assert "ignored pull_request action" in result["reason"]


def test_github_webhook_endpoint_runs_dev_tracking_for_opened_pr(monkeypatch):
    import pipeline.domain.dev_tracking as dev_tracking
    from transport.rest_handler import github_webhook_endpoint

    captured = {}

    def fake_run_dev_tracking_analysis(payload, *, shared_db=None):
        captured.update(payload)
        return {"status": "pending_pm_approval", "timeline": [], "data": {}}

    monkeypatch.setattr(dev_tracking, "run_dev_tracking_analysis", fake_run_dev_tracking_analysis)
    monkeypatch.setenv("NAVIGATOR_GITHUB_TOKEN", "token-123")
    monkeypatch.setenv("NAVIGATOR_DEFAULT_TEAM_ID", "team-1")
    monkeypatch.delenv("NAVIGATOR_GITHUB_WEBHOOK_SECRET", raising=False)

    class FakeRequest:
        headers = {"X-GitHub-Event": "pull_request"}

        async def body(self):
            return json.dumps(_github_pr_payload(action="opened")).encode("utf-8")

    result = asyncio.run(github_webhook_endpoint(FakeRequest(), shared_db="shared"))

    assert result["status"] == "ok"
    assert result["handled"] is True
    assert result["signature_verified"] is False
    assert captured["repository"] == {"owner": "xxrin", "repo": "navigator"}
    assert captured["pull_request"]["pr_number"] == 17
    assert captured["source_dir"] == ""
    assert captured["github_oauth_token"] == "token-123"
    assert captured["notify_pr"] is True
    assert captured["team_id"] == "team-1"


def test_github_webhook_endpoint_rejects_bad_signature(monkeypatch):
    from transport.rest_handler import github_webhook_endpoint

    monkeypatch.setenv("NAVIGATOR_GITHUB_WEBHOOK_SECRET", "webhook-secret")

    class FakeRequest:
        headers = {
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "sha256=bad",
        }

        async def body(self):
            return json.dumps(_github_pr_payload(action="opened")).encode("utf-8")

    result = asyncio.run(github_webhook_endpoint(FakeRequest(), shared_db=None))

    assert result["status"] == "error"
    assert result["handled"] is False
    assert result["signature_verified"] is False


def test_github_webhook_endpoint_skips_duplicate_head_sha(monkeypatch):
    import pipeline.domain.dev_tracking as dev_tracking
    from transport.rest_handler import github_webhook_endpoint

    class FakeAnalysis:
        def __init__(self):
            self.created_at = None

    class FakeQuery:
        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def first(self):
            return FakeAnalysis()

    class FakeSharedDB:
        def query(self, model):
            return FakeQuery()

    called = {"run": False}

    def fake_run_dev_tracking_analysis(payload, *, shared_db=None):
        called["run"] = True
        return {"status": "pending_pm_approval", "timeline": [], "data": {}}

    monkeypatch.setattr(dev_tracking, "run_dev_tracking_analysis", fake_run_dev_tracking_analysis)

    class FakeRequest:
        headers = {"X-GitHub-Event": "pull_request"}

        async def body(self):
            return json.dumps(_github_pr_payload(action="opened")).encode("utf-8")

    result = asyncio.run(github_webhook_endpoint(FakeRequest(), shared_db=FakeSharedDB()))

    assert result["status"] == "ok"
    assert result["handled"] is False
    assert "duplicate head_sha" in result["reason"]
    assert called["run"] is False


def test_pr_status_check_updater_sets_pending_for_pm_approval(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    captured = {}

    def fake_run_gh(args, cwd, input_text=None):
        captured["args"] = args
        captured["cwd"] = cwd
        captured["payload"] = json.loads(input_text)
        return 0, "created", ""

    monkeypatch.setattr(nodes, "_run_gh", fake_run_gh)

    result = nodes.pr_status_check_updater(
        {
            "notify_pr": True,
            "source_dir": "E:/navigator_v2/KNU-PROJECT",
            "approval_status": "PENDING_PM_APPROVAL",
            "pr_context": {
                "owner": "xxrin",
                "repo": "navigator",
                "head_sha": "abc123",
            },
        }
    )

    assert result["status"] == "PASS"
    assert captured["args"][0] == "api"
    assert captured["args"][1] == "repos/xxrin/navigator/statuses/abc123"
    assert captured["payload"]["state"] == "pending"
    assert captured["payload"]["context"] == "NAVIGATOR Dev Tracking"


def test_pr_status_check_updater_sets_success_for_no_gap(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    captured = {}

    def fake_run_gh(args, cwd, input_text=None):
        captured["payload"] = json.loads(input_text)
        return 0, "created", ""

    monkeypatch.setattr(nodes, "_run_gh", fake_run_gh)

    result = nodes.pr_status_check_updater(
        {
            "notify_pr": True,
            "approval_status": "NO_GAP_DETECTED",
            "pr_context": {
                "owner": "xxrin",
                "repo": "navigator",
                "head_sha": "abc123",
            },
        }
    )

    assert result["status"] == "PASS"
    assert captured["payload"]["state"] == "success"


def test_pr_status_check_updater_warns_when_gh_fails(monkeypatch):
    from pipeline.domain.dev_tracking import nodes

    def fake_run_gh(args, cwd, input_text=None):
        return 1, "", "gh auth required"

    monkeypatch.setattr(nodes, "_run_gh", fake_run_gh)

    result = nodes.pr_status_check_updater(
        {
            "notify_pr": True,
            "approval_status": "PENDING_PM_APPROVAL",
            "pr_context": {
                "owner": "xxrin",
                "repo": "navigator",
                "head_sha": "abc123",
            },
        }
    )

    assert result["status"] == "WARN"
    assert result["pr_status_check"]["status_updated"] is False
    assert result["pr_status_check"]["error"] == "gh auth required"


def test_dev_gap_decision_followup_prepares_metadata_and_pr_comment(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from auth.database import Base
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
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[DevKnowledgeArtifact.__table__])
    session = sessionmaker(bind=engine)()

    try:
        result = nodes.run_dev_gap_decision_followup(
            {
                "id": "task-1",
                "payload": {
                    "source_dir": "E:/navigator_v2/KNU-PROJECT",
                    "pr_context": {"owner": "xxrin", "repo": "navigator", "pr_number": 7},
                    "gap_report": [{"gap_id": "gap-1"}],
                },
            },
            "APPROVED_INTENTIONAL_CHANGE",
            "pm-1",
            {"approval_status": "APPROVED_INTENTIONAL_CHANGE"},
            shared_db=session,
        )
        artifact = session.query(DevKnowledgeArtifact).one()
    finally:
        session.close()

    assert result["rag_metadata"]["write_enabled"] is True
    assert result["rag_metadata"]["stored"] is True
    assert result["artifact"]["summary"]["gap_count"] == 1
    assert artifact.artifact_type == "DEV_GAP_DECISION"
    assert result["doc_sync"]["action"] == "skipped"
    assert result["pr_comment"]["comment_created"] is True
    assert calls["args"][:3] == ["pr", "comment", "7"]


def test_dev_gap_decision_followup_warns_on_rejection_comment_failure(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from auth.database import Base
    from auth.shared_models import DevKnowledgeArtifact
    import pipeline.domain.dev_tracking.nodes as nodes

    def fake_run_gh(args, cwd, input_text=None):
        return 1, "", "gh auth required"

    monkeypatch.setattr(nodes, "_run_gh", fake_run_gh)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[DevKnowledgeArtifact.__table__])
    session = sessionmaker(bind=engine)()

    try:
        result = nodes.run_dev_gap_decision_followup(
            {
                "id": "task-1",
                "payload": {"pr_context": {"pr_number": 7}},
            },
            "REJECTED_UNINTENTIONAL_CHANGE",
            "pm-1",
            {},
            shared_db=session,
        )
    finally:
        session.close()

    assert result["status"] == "PASS"
    assert result["rag_metadata"]["stored"] is True
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
            "pr_context": {"owner": "xxrin", "repo": "navigator", "pr_number": 99},
            "reviewed_by": "pm-1",
            "result": {"reason": "요구사항 의도 반영"},
        }
    )

    assert result["synced"] is True
    assert result["updater"] == "doc_updater"
    assert result["decision_status"] == "APPROVED_INTENTIONAL_CHANGE"
    assert captured["owner"] == "xxrin"
    assert captured["repo"] == "navigator"
    assert captured["page_title"] == "NAVIGATOR Dev Gap Decisions - PR #99"
    assert captured["result_data"]["sa_output"]["decision_status"] == "APPROVED_INTENTIONAL_CHANGE"
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


def test_dev_gap_approval_endpoint_updates_success_status(monkeypatch):
    import pipeline.domain.agile.task_coordinator as agile_task_coordinator
    import pipeline.domain.dev_tracking.nodes as dev_nodes
    from transport.rest_handler import TaskUpdateRequest, update_task_endpoint

    calls = {}
    stored_results = []
    task = {
        "id": "task-1",
        "task_type": "dev_gap_approval",
        "status": "in_progress",
        "payload": {
            "pr_context": {
                "owner": "xxrin",
                "repo": "navigator",
                "head_sha": "abc123",
            }
        },
    }

    monkeypatch.setattr(agile_task_coordinator, "init_tasks_db", lambda: None)
    monkeypatch.setattr(agile_task_coordinator, "execute_approved_task", lambda task: json.dumps({"approval_status": "APPROVED_INTENTIONAL_CHANGE"}))

    def fake_update_task_status(task_id, status, reviewed_by="", result=""):
        if result:
            stored_results.append(json.loads(result))
        updated = dict(task)
        updated["status"] = status
        updated["result"] = result
        updated["reviewed_by"] = reviewed_by
        return updated

    def fake_update_pr_status_check(state, status_state, description):
        calls["state"] = state
        calls["status_state"] = status_state
        calls["description"] = description
        return {"status": "PASS", "status_updated": True, "state": status_state}

    def fake_run_dev_gap_decision_followup(task, decision_status, reviewed_by="", result_payload=None):
        calls["followup_decision_status"] = decision_status
        calls["followup_reviewed_by"] = reviewed_by
        return {"status": "PASS", "rag_metadata": {"write_enabled": False}}

    monkeypatch.setattr(agile_task_coordinator, "update_task_status", fake_update_task_status)
    monkeypatch.setattr(agile_task_coordinator, "get_task", lambda task_id: task)
    monkeypatch.setattr(dev_nodes, "update_pr_status_check", fake_update_pr_status_check)
    monkeypatch.setattr(dev_nodes, "run_dev_gap_decision_followup", fake_run_dev_gap_decision_followup)

    result = asyncio.run(
        update_task_endpoint(
            "task-1",
            TaskUpdateRequest(status="in_progress", reviewed_by="pm"),
            current_user=_fake_user("pm", "pm-1"),
        )
    )

    assert result["status"] == "ok"
    assert result["data"]["status"] == "completed"
    assert calls["status_state"] == "success"
    assert calls["followup_decision_status"] == "APPROVED_INTENTIONAL_CHANGE"
    assert calls["followup_reviewed_by"] == "pm-1"
    assert stored_results[-1]["status_check"]["status_updated"] is True
    assert stored_results[-1]["followup"]["status"] == "PASS"
    assert stored_results[-1]["followup"]["doc_sync"]["updater"] == "doc_updater"
    assert stored_results[-1]["followup"]["doc_sync"]["decision_status"] == "APPROVED_INTENTIONAL_CHANGE"
    assert "pr_comment" in stored_results[-1]["followup"]
    assert result["data"]["reviewed_by"] == "pm-1"


def test_dev_gap_rejection_endpoint_updates_failure_status(monkeypatch):
    import pipeline.domain.agile.task_coordinator as agile_task_coordinator
    import pipeline.domain.dev_tracking.nodes as dev_nodes
    from transport.rest_handler import TaskUpdateRequest, update_task_endpoint

    calls = {}
    stored_results = []
    task = {
        "id": "task-1",
        "task_type": "dev_gap_approval",
        "status": "rejected",
        "payload": {
            "pr_context": {
                "owner": "xxrin",
                "repo": "navigator",
                "head_sha": "abc123",
            }
        },
    }

    monkeypatch.setattr(agile_task_coordinator, "init_tasks_db", lambda: None)

    def fake_update_task_status(task_id, status, reviewed_by="", result=""):
        if result:
            stored_results.append(json.loads(result))
        updated = dict(task)
        updated["status"] = status
        updated["result"] = result
        updated["reviewed_by"] = reviewed_by
        return updated

    def fake_update_pr_status_check(state, status_state, description):
        calls["state"] = state
        calls["status_state"] = status_state
        calls["description"] = description
        return {"status": "PASS", "status_updated": True, "state": status_state}

    def fake_run_dev_gap_decision_followup(task, decision_status, reviewed_by="", result_payload=None):
        calls["followup_decision_status"] = decision_status
        calls["followup_reviewed_by"] = reviewed_by
        return {"status": "PASS", "pr_comment": {"comment_created": True}}

    monkeypatch.setattr(agile_task_coordinator, "update_task_status", fake_update_task_status)
    monkeypatch.setattr(agile_task_coordinator, "get_task", lambda task_id: task)
    monkeypatch.setattr(dev_nodes, "update_pr_status_check", fake_update_pr_status_check)
    monkeypatch.setattr(dev_nodes, "run_dev_gap_decision_followup", fake_run_dev_gap_decision_followup)

    result = asyncio.run(
        update_task_endpoint(
            "task-1",
            TaskUpdateRequest(status="rejected", reviewed_by="pm"),
            current_user=_fake_user("admin", "admin-1"),
        )
    )

    assert result["status"] == "ok"
    assert result["data"]["status"] == "rejected"
    assert calls["status_state"] == "failure"
    assert calls["followup_decision_status"] == "REJECTED_UNINTENTIONAL_CHANGE"
    assert calls["followup_reviewed_by"] == "admin-1"
    assert stored_results[-1]["approval_status"] == "REJECTED_UNINTENTIONAL_CHANGE"
    assert stored_results[-1]["status_check"]["status_updated"] is True
    assert stored_results[-1]["followup"]["pr_comment"]["comment_created"] is True
    assert stored_results[-1]["followup"]["doc_sync"]["updater"] == "doc_updater"
    assert stored_results[-1]["followup"]["doc_sync"]["decision_status"] == "REJECTED_UNINTENTIONAL_CHANGE"


def test_dev_gap_approve_endpoint_uses_explicit_contract(monkeypatch):
    import pipeline.domain.agile.task_coordinator as agile_task_coordinator
    import pipeline.domain.dev_tracking.nodes as dev_nodes
    from transport.rest_handler import DevGapDecisionRequest, dev_gap_approve_endpoint

    stored_results = []
    task = {
        "id": "task-1",
        "task_type": "dev_gap_approval",
        "status": "pending_approval",
        "payload": {"pr_context": {"owner": "xxrin", "repo": "navigator", "head_sha": "abc123"}},
    }

    monkeypatch.setattr(agile_task_coordinator, "init_tasks_db", lambda: None)
    monkeypatch.setattr(agile_task_coordinator, "get_task", lambda task_id: task)
    monkeypatch.setattr(agile_task_coordinator, "execute_approved_task", lambda task: json.dumps({"approval_status": "APPROVED_INTENTIONAL_CHANGE"}))

    def fake_update_task_status(task_id, status, reviewed_by="", result=""):
        if result:
            stored_results.append(json.loads(result))
        updated = dict(task)
        updated["status"] = status
        updated["reviewed_by"] = reviewed_by
        updated["result"] = result
        return updated

    monkeypatch.setattr(agile_task_coordinator, "update_task_status", fake_update_task_status)
    monkeypatch.setattr(dev_nodes, "update_pr_status_check", lambda state, status_state, description: {"status": "PASS", "status_updated": True, "state": status_state})
    monkeypatch.setattr(dev_nodes, "run_dev_gap_decision_followup", lambda *args, **kwargs: {"status": "PASS"})

    result = asyncio.run(
        dev_gap_approve_endpoint(
            "task-1",
            DevGapDecisionRequest(reason="요구사항 의도 반영"),
            current_user=_fake_user("pm", "pm-1"),
        )
    )

    assert result["status"] == "ok"
    assert result["data"]["status"] == "completed"
    assert result["data"]["reviewed_by"] == "pm-1"
    assert stored_results[-1]["approval_status"] == "APPROVED_INTENTIONAL_CHANGE"
    assert stored_results[-1]["reason"] == "요구사항 의도 반영"


def test_dev_gap_reject_endpoint_rejects_engineer_role(monkeypatch):
    from transport.rest_handler import DevGapDecisionRequest, dev_gap_reject_endpoint

    result = asyncio.run(
        dev_gap_reject_endpoint(
            "task-1",
            DevGapDecisionRequest(reason="불일치"),
            current_user=_fake_user("engineer", "eng-1"),
        )
    )

    assert result["status"] == "error"
    assert "PM or admin" in result["error"]


def test_dev_gap_approval_requires_authenticated_pm(monkeypatch):
    import pipeline.domain.agile.task_coordinator as agile_task_coordinator
    from transport.rest_handler import TaskUpdateRequest, update_task_endpoint

    task = {"id": "task-1", "task_type": "dev_gap_approval", "status": "pending_approval", "payload": {}}
    called = {"updated": False}

    monkeypatch.setattr(agile_task_coordinator, "init_tasks_db", lambda: None)
    monkeypatch.setattr(agile_task_coordinator, "get_task", lambda task_id: task)

    def fake_update_task_status(*args, **kwargs):
        called["updated"] = True
        return task

    monkeypatch.setattr(agile_task_coordinator, "update_task_status", fake_update_task_status)

    result = asyncio.run(
        update_task_endpoint(
            "task-1",
            TaskUpdateRequest(status="in_progress"),
            current_user=None,
        )
    )

    assert result["status"] == "error"
    assert "Authentication required" in result["error"]
    assert called["updated"] is False


def test_dev_gap_approval_rejects_engineer_role(monkeypatch):
    import pipeline.domain.agile.task_coordinator as agile_task_coordinator
    from transport.rest_handler import TaskUpdateRequest, update_task_endpoint

    task = {"id": "task-1", "task_type": "dev_gap_approval", "status": "pending_approval", "payload": {}}
    called = {"updated": False}

    monkeypatch.setattr(agile_task_coordinator, "init_tasks_db", lambda: None)
    monkeypatch.setattr(agile_task_coordinator, "get_task", lambda task_id: task)

    def fake_update_task_status(*args, **kwargs):
        called["updated"] = True
        return task

    monkeypatch.setattr(agile_task_coordinator, "update_task_status", fake_update_task_status)

    result = asyncio.run(
        update_task_endpoint(
            "task-1",
            TaskUpdateRequest(status="rejected"),
            current_user=_fake_user("engineer", "eng-1"),
        )
    )

    assert result["status"] == "error"
    assert "PM or admin" in result["error"]
    assert called["updated"] is False


def test_regular_task_update_keeps_legacy_optional_auth(monkeypatch):
    import pipeline.domain.agile.task_coordinator as agile_task_coordinator
    from transport.rest_handler import TaskUpdateRequest, update_task_endpoint

    task = {"id": "task-1", "task_type": "feature", "status": "pending_approval", "payload": {}}

    monkeypatch.setattr(agile_task_coordinator, "init_tasks_db", lambda: None)
    monkeypatch.setattr(agile_task_coordinator, "get_task", lambda task_id: task)

    def fake_update_task_status(task_id, status, reviewed_by="", result=""):
        updated = dict(task)
        updated["status"] = status
        updated["reviewed_by"] = reviewed_by
        return updated

    monkeypatch.setattr(agile_task_coordinator, "update_task_status", fake_update_task_status)

    result = asyncio.run(
        update_task_endpoint(
            "task-1",
            TaskUpdateRequest(status="in_progress", reviewed_by="legacy-user"),
            current_user=None,
        )
    )

    assert result["status"] == "ok"
    assert result["data"]["status"] == "in_progress"
    assert result["data"]["reviewed_by"] == "legacy-user"


def test_dev_tracking_graph_is_exported_without_legacy_develop_name():
    from pipeline.orchestration import facade

    assert callable(facade.get_dev_tracking_pipeline)
    assert callable(facade.get_dev_tracking_routing_map)
    assert not hasattr(facade, "get_develop_pipeline")
    assert not hasattr(facade, "get_develop_routing_map")

    graph = facade.get_dev_tracking_pipeline()
    routing = facade.get_dev_tracking_routing_map()

    assert graph is not None
    assert routing["first_node"] == "dev_task_planner"
    assert "gap_analyzer" in routing["next_nodes"]


def test_dev_tracking_graph_blocks_invalid_payload_before_task_creation(monkeypatch):
    from pipeline.domain.dev_tracking.service import run_dev_tracking_analysis
    import pipeline.domain.dev_tracking.nodes as dev_nodes

    called = {"task": False}

    def fake_task_coordinator(state):
        called["task"] = True
        return {"status": "PASS"}

    monkeypatch.setattr(dev_nodes, "task_coordinator", fake_task_coordinator)

    result = run_dev_tracking_analysis(
        {
            "trigger": "GITHUB_PR_WEBHOOK",
            "repository": {"owner": "xxrin", "repo": "navigator"},
            "pull_request": {
                "pr_number": 1,
                "branch_name": "feature/dev-tracking",
                "head_sha": "",
            },
            "actor": {"github_id": "xxrin"},
        }
    )

    assert result["status"] == "error"
    assert result["timeline"][0]["node"] == "dev_task_planner"
    assert result["timeline"][0]["error_type"] == "INVALID_WEBHOOK_PAYLOAD"
    assert called["task"] is False
    assert "_shared_db" not in result["data"]


def test_dev_tracking_graph_skips_intent_classifier_when_gap_absent(monkeypatch, tmp_path):
    import pipeline.orchestration.dev_tracking_graphs as graphs
    from pipeline.domain.dev_tracking.service import run_dev_tracking_analysis
    import pipeline.domain.dev_tracking.nodes as dev_nodes
    import pipeline.domain.agile.task_coordinator as agile_task_coordinator

    graphs._PipelineRegistry._cache.clear()


def test_dev_tracking_service_returns_pending_after_completed_graph(monkeypatch, tmp_path):
    import pipeline.orchestration.dev_tracking_graphs as graphs
    from pipeline.domain.dev_tracking.service import run_dev_tracking_analysis
    import pipeline.domain.dev_tracking.nodes as dev_nodes
    import pipeline.domain.agile.task_coordinator as agile_task_coordinator

    graphs._PipelineRegistry._cache.clear()

    def fake_branch_fetcher(state):
        return {
            "status": "PASS",
            "source_dir": str(tmp_path),
            "checkout": {"head_sha_matched": True},
            "dev_tracking_next_action": "reverse_analyzer",
        }

    def fake_reverse_analyzer(state):
        return {"status": "PASS", "project_context": "ctx", "dev_tracking_next_action": "code_inventory_builder"}

    def fake_code_inventory_builder(state):
        return {
            "status": "PASS",
            "code_inventory": {"files": [], "symbols_by_file": {}, "summary": {}},
            "dev_tracking_next_action": "forensic_profiler",
        }

    def fake_forensic_profiler(state):
        return {
            "status": "PASS",
            "implementation_profile": {"detected_apis": [], "detected_components": []},
            "dev_tracking_next_action": "spec_loader",
        }

    def fake_spec_loader(state, shared_db=None):
        return {
            "status": "PASS",
            "published_spec_snapshot": {
                "api_contracts": [{"method": "GET", "url": "/api/auth"}],
                "component_contracts": [],
            },
            "spec_outdated": False,
            "latest_snapshot": {},
            "dev_tracking_next_action": "gap_analyzer",
        }

    def fake_create_task(**kwargs):
        return {"id": "task-pending", "task_type": kwargs["task_type"], "status": kwargs["status"]}

    def fake_analysis_persister(state, shared_db=None):
        return {
            "status": "SKIPPED",
            "analysis_persistence": {"stored": False},
            "dev_tracking_next_action": "develop_embedding",
        }

    def fake_develop_embedding(state, shared_db=None):
        return {
            "status": "SKIPPED",
            "embedding_result": {"status": "skipped"},
            "dev_tracking_next_action": "develop_loop_controller",
        }

    monkeypatch.setattr(dev_nodes, "branch_fetcher", fake_branch_fetcher)
    monkeypatch.setattr(dev_nodes, "reverse_analyzer", fake_reverse_analyzer)
    monkeypatch.setattr(dev_nodes, "code_inventory_builder", fake_code_inventory_builder)
    monkeypatch.setattr(dev_nodes, "forensic_profiler", fake_forensic_profiler)
    monkeypatch.setattr(dev_nodes, "spec_loader", fake_spec_loader)
    monkeypatch.setattr(dev_nodes, "analysis_persister", fake_analysis_persister)
    monkeypatch.setattr(dev_nodes, "develop_embedding", fake_develop_embedding)
    monkeypatch.setattr(agile_task_coordinator, "create_task", fake_create_task)

    result = run_dev_tracking_analysis(_valid_payload(source_dir=str(tmp_path)))

    assert result["status"] == "pending_pm_approval"
    assert result["data"]["approval_status"] == "PENDING_PM_APPROVAL"
    assert result["data"]["dev_tracking_next_action"] == "pm_approval_pending"
    assert result["data"]["current_step"] == "develop_loop_controller_done"

    graphs._PipelineRegistry._cache.clear()
    called = {"intent": False, "shared_db_seen": False}

    def fake_branch_fetcher(state):
        return {
            "status": "PASS",
            "source_dir": str(tmp_path),
            "checkout": {"head_sha_matched": True},
            "dev_tracking_next_action": "reverse_analyzer",
        }

    def fake_reverse_analyzer(state):
        return {
            "status": "PASS",
            "project_context": "ctx",
            "dev_tracking_next_action": "code_inventory_builder",
        }

    def fake_code_inventory_builder(state):
        return {
            "status": "PASS",
            "code_inventory": {"files": [], "symbols_by_file": {}, "summary": {}},
            "dev_tracking_next_action": "forensic_profiler",
        }

    def fake_forensic_profiler(state):
        return {
            "status": "PASS",
            "implementation_profile": {
                "detected_apis": [],
                "detected_components": [],
                "implementation_summary": "No code.",
            },
            "dev_tracking_next_action": "spec_loader",
        }

    def fake_spec_loader(state, shared_db=None):
        called["shared_db_seen"] = shared_db == "shared-session"
        return {
            "status": "PASS",
            "published_spec_snapshot": {"api_contracts": [], "component_contracts": []},
            "spec_outdated": False,
            "latest_snapshot": {},
            "dev_tracking_next_action": "gap_analyzer",
        }

    def fake_intent_classifier(state):
        called["intent"] = True
        return {"status": "PASS", "intent_classification": []}

    def fake_create_task(**kwargs):
        return {"id": "task-graph", "task_type": kwargs["task_type"], "status": kwargs["status"]}

    def fake_analysis_persister(state, shared_db=None):
        return {
            "status": "SKIPPED",
            "analysis_persistence": {"stored": False, "reason": "test"},
            "dev_tracking_next_action": "develop_embedding",
        }

    def fake_develop_embedding(state, shared_db=None):
        return {
            "status": "SKIPPED",
            "embedding_result": {"status": "skipped"},
            "dev_tracking_next_action": "develop_loop_controller",
        }

    monkeypatch.setattr(dev_nodes, "branch_fetcher", fake_branch_fetcher)
    monkeypatch.setattr(dev_nodes, "reverse_analyzer", fake_reverse_analyzer)
    monkeypatch.setattr(dev_nodes, "code_inventory_builder", fake_code_inventory_builder)
    monkeypatch.setattr(dev_nodes, "forensic_profiler", fake_forensic_profiler)
    monkeypatch.setattr(dev_nodes, "spec_loader", fake_spec_loader)
    monkeypatch.setattr(dev_nodes, "intent_classifier", fake_intent_classifier)
    monkeypatch.setattr(dev_nodes, "analysis_persister", fake_analysis_persister)
    monkeypatch.setattr(dev_nodes, "develop_embedding", fake_develop_embedding)
    monkeypatch.setattr(agile_task_coordinator, "create_task", fake_create_task)

    result = run_dev_tracking_analysis(
        _valid_payload(source_dir=str(tmp_path)),
        shared_db="shared-session",
    )
    node_names = [item["node"] for item in result["timeline"]]

    assert result["status"] == "complete"
    assert called["shared_db_seen"] is True
    assert called["intent"] is False
    assert "intent_classifier" not in node_names
    assert "milestone_tracker" in node_names
    assert "_shared_db" not in result["data"]

    graphs._PipelineRegistry._cache.clear()


def test_dev_tracking_graph_calls_three_llm_paths_for_high_gap(monkeypatch, tmp_path):
    # author:xxrin
    # Graph 전체 실행에서 세 LLM 노드가 실제 state 흐름 안에서 호출되는지 고정한다.
    import pipeline.orchestration.dev_tracking_graphs as graphs
    from pipeline.domain.dev_tracking.service import run_dev_tracking_analysis
    import pipeline.domain.dev_tracking.nodes as dev_nodes
    import pipeline.domain.agile.task_coordinator as agile_task_coordinator

    graphs._PipelineRegistry._cache.clear()
    calls = {"forensic": 0, "gap": 0, "intent": 0}

    class ForensicParsed:
        implementation_profile = dev_nodes.DevImplementationProfile(
            detected_apis=[],
            detected_components=[],
            file_role_map={"app/api/auth.py": "api"},
            implementation_summary="LLM profile from graph.",
        )

    class GapParsed:
        gaps = [
            dev_nodes.DevGapItem(
                gap_id="GAP_001",
                severity="HIGH",
                type="MISSING_API",
                spec_target="get /api/auth",
                implementation_target=None,
                description="LLM graph gap.",
                spec_outdated_related=False,
            )
        ]

    class IntentParsed:
        classifications = [
            dev_nodes.DevGapIntentItem(
                gap_id="GAP_001",
                intent="UNINTENTIONAL",
                confidence=0.88,
                reason="LLM graph intent.",
                recommended_action="REQUEST_FIX",
            )
        ]

    class Result:
        usage = {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}
        cost = 0.0
        retry_count = 0

        def __init__(self, parsed):
            self.parsed = parsed

    def fake_branch_fetcher(state):
        return {
            "status": "PASS",
            "source_dir": str(tmp_path),
            "checkout": {"head_sha_matched": True},
            "dev_tracking_next_action": "reverse_analyzer",
        }

    def fake_reverse_analyzer(state):
        return {"status": "PASS", "project_context": "ctx", "dev_tracking_next_action": "code_inventory_builder"}

    def fake_code_inventory_builder(state):
        return {
            "status": "PASS",
            "code_inventory": {
                "files": [{"file": "app/api/auth.py"}],
                "symbols_by_file": {"app/api/auth.py": [{"name": "login"}]},
                "summary": {"file_count": 1},
            },
            "dev_tracking_next_action": "forensic_profiler",
        }

    def fake_spec_loader(state, shared_db=None):
        return {
            "status": "PASS",
            "published_spec_snapshot": {
                "api_contracts": [{"method": "GET", "url": "/api/auth"}],
                "component_contracts": [],
            },
            "spec_outdated": False,
            "latest_snapshot": {},
            "dev_tracking_next_action": "gap_analyzer",
        }

    def fake_forensic_llm(**kwargs):
        calls["forensic"] += 1
        return Result(ForensicParsed())

    def fake_gap_llm(**kwargs):
        calls["gap"] += 1
        return Result(GapParsed())

    def fake_intent_llm(**kwargs):
        calls["intent"] += 1
        return Result(IntentParsed())

    monkeypatch.setattr(dev_nodes, "branch_fetcher", fake_branch_fetcher)
    monkeypatch.setattr(dev_nodes, "reverse_analyzer", fake_reverse_analyzer)
    monkeypatch.setattr(dev_nodes, "code_inventory_builder", fake_code_inventory_builder)
    monkeypatch.setattr(dev_nodes, "spec_loader", fake_spec_loader)
    monkeypatch.setattr(dev_nodes, "_call_structured_for_forensic", fake_forensic_llm)
    monkeypatch.setattr(dev_nodes, "_call_structured_for_gap", fake_gap_llm)
    monkeypatch.setattr(dev_nodes, "_call_structured_for_intent", fake_intent_llm)
    monkeypatch.setattr(agile_task_coordinator, "create_task", lambda **kwargs: {"id": "task-llm", "task_type": kwargs["task_type"], "status": kwargs["status"]})
    monkeypatch.setattr(dev_nodes, "analysis_persister", lambda state, shared_db=None: {"status": "SKIPPED", "dev_tracking_next_action": "develop_embedding"})
    monkeypatch.setattr(dev_nodes, "develop_embedding", lambda state, shared_db=None: {"status": "SKIPPED", "dev_tracking_next_action": "develop_loop_controller"})

    result = run_dev_tracking_analysis({**_valid_payload(source_dir=str(tmp_path)), "api_key": "test-key"})
    node_names = [item["node"] for item in result["timeline"]]

    assert calls == {"forensic": 1, "gap": 1, "intent": 1}
    assert "intent_classifier" in node_names
    assert result["data"]["forensic_profiler_meta"]["mode"] == "llm"
    assert result["data"]["gap_analyzer_meta"]["mode"] == "llm"
    assert result["data"]["intent_classifier_meta"]["mode"] == "llm"
    assert result["data"]["pm_report"]["recommended_pm_actions"] == ["REQUEST_FIX"]

    graphs._PipelineRegistry._cache.clear()


def test_dev_tracking_graph_accumulates_llm_warning_when_gap_llm_fails(monkeypatch, tmp_path):
    # author:xxrin
    # 한 LLM 노드가 실패해도 graph를 중단하지 않고 PM Report까지 warning을 전달한다.
    import pipeline.orchestration.dev_tracking_graphs as graphs
    from pipeline.domain.dev_tracking.service import run_dev_tracking_analysis
    import pipeline.domain.dev_tracking.nodes as dev_nodes
    import pipeline.domain.agile.task_coordinator as agile_task_coordinator

    graphs._PipelineRegistry._cache.clear()

    class ForensicParsed:
        implementation_profile = dev_nodes.DevImplementationProfile(
            detected_apis=[],
            detected_components=[],
            file_role_map={"app/service/auth.py": "module"},
            implementation_summary="LLM profile from graph.",
        )

    class IntentParsed:
        classifications = [
            dev_nodes.DevGapIntentItem(
                gap_id="GAP_001",
                intent="UNCERTAIN",
                confidence=0.7,
                reason="LLM saw fallback GAP and requires review.",
                recommended_action="PM_REVIEW",
            )
        ]

    class Result:
        usage = {}
        cost = 0.0
        retry_count = 0

        def __init__(self, parsed):
            self.parsed = parsed

    monkeypatch.setattr(dev_nodes, "branch_fetcher", lambda state: {"status": "PASS", "source_dir": str(tmp_path), "checkout": {}, "dev_tracking_next_action": "reverse_analyzer"})
    monkeypatch.setattr(dev_nodes, "reverse_analyzer", lambda state: {"status": "PASS", "project_context": "ctx", "dev_tracking_next_action": "code_inventory_builder"})
    monkeypatch.setattr(dev_nodes, "code_inventory_builder", lambda state: {
        "status": "PASS",
        "code_inventory": {
            "files": [{"file": "app/service/auth.py"}],
            "symbols_by_file": {"app/service/auth.py": [{"name": "helper"}]},
        },
        "dev_tracking_next_action": "forensic_profiler",
    })
    monkeypatch.setattr(dev_nodes, "spec_loader", lambda state, shared_db=None: {
        "status": "PASS",
        "published_spec_snapshot": {
            "api_contracts": [{"method": "GET", "url": "/api/auth"}],
            "component_contracts": [],
        },
        "spec_outdated": False,
        "latest_snapshot": {},
        "dev_tracking_next_action": "gap_analyzer",
    })
    monkeypatch.setattr(dev_nodes, "_call_structured_for_forensic", lambda **kwargs: Result(ForensicParsed()))
    monkeypatch.setattr(dev_nodes, "_call_structured_for_gap", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("gap llm unavailable")))
    monkeypatch.setattr(dev_nodes, "_call_structured_for_intent", lambda **kwargs: Result(IntentParsed()))
    monkeypatch.setattr(agile_task_coordinator, "create_task", lambda **kwargs: {"id": "task-warning", "task_type": kwargs["task_type"], "status": kwargs["status"]})
    monkeypatch.setattr(dev_nodes, "analysis_persister", lambda state, shared_db=None: {"status": "SKIPPED", "dev_tracking_next_action": "develop_embedding"})
    monkeypatch.setattr(dev_nodes, "develop_embedding", lambda state, shared_db=None: {"status": "SKIPPED", "dev_tracking_next_action": "develop_loop_controller"})

    result = run_dev_tracking_analysis({**_valid_payload(source_dir=str(tmp_path)), "api_key": "test-key"})
    node_names = [item["node"] for item in result["timeline"]]

    assert result["status"] == "pending_pm_approval"
    assert "intent_classifier" in node_names
    assert result["data"]["gap_analyzer_meta"]["mode"] == "rule_based_fallback"
    assert result["data"]["gap_report"][0]["preliminary"] is True
    assert result["data"]["pm_report"]["llm_warnings"][0]["node"] == "gap_analyzer"
    assert result["data"]["pm_report"]["recommended_pm_actions"] == ["PM_REVIEW"]

    graphs._PipelineRegistry._cache.clear()


def test_dev_tracking_graph_respects_llm_node_flags(monkeypatch, tmp_path):
    # author:xxrin
    # 명시 false 플래그가 graph 실행에서도 해당 노드의 LLM 호출을 막는지 검증한다.
    import pipeline.orchestration.dev_tracking_graphs as graphs
    from pipeline.domain.dev_tracking.service import run_dev_tracking_analysis
    import pipeline.domain.dev_tracking.nodes as dev_nodes
    import pipeline.domain.agile.task_coordinator as agile_task_coordinator

    graphs._PipelineRegistry._cache.clear()
    calls = {"forensic": 0, "gap": 0, "intent": 0}

    def fail_forensic(**kwargs):
        calls["forensic"] += 1
        raise AssertionError("forensic LLM should be skipped")

    def fail_gap(**kwargs):
        calls["gap"] += 1
        raise AssertionError("gap LLM should be skipped")

    def fail_intent(**kwargs):
        calls["intent"] += 1
        raise AssertionError("intent LLM should be skipped")

    monkeypatch.setattr(dev_nodes, "branch_fetcher", lambda state: {"status": "PASS", "source_dir": str(tmp_path), "checkout": {}, "dev_tracking_next_action": "reverse_analyzer"})
    monkeypatch.setattr(dev_nodes, "reverse_analyzer", lambda state: {"status": "PASS", "project_context": "ctx", "dev_tracking_next_action": "code_inventory_builder"})
    monkeypatch.setattr(dev_nodes, "code_inventory_builder", lambda state: {
        "status": "PASS",
        "code_inventory": {
            "files": [{"file": "app/service/auth.py"}],
            "symbols_by_file": {"app/service/auth.py": [{"name": "helper"}]},
        },
        "dev_tracking_next_action": "forensic_profiler",
    })
    monkeypatch.setattr(dev_nodes, "spec_loader", lambda state, shared_db=None: {
        "status": "PASS",
        "published_spec_snapshot": {
            "api_contracts": [{"method": "GET", "url": "/api/auth"}],
            "component_contracts": [],
        },
        "spec_outdated": False,
        "latest_snapshot": {},
        "dev_tracking_next_action": "gap_analyzer",
    })
    monkeypatch.setattr(dev_nodes, "_call_structured_for_forensic", fail_forensic)
    monkeypatch.setattr(dev_nodes, "_call_structured_for_gap", fail_gap)
    monkeypatch.setattr(dev_nodes, "_call_structured_for_intent", fail_intent)
    monkeypatch.setattr(agile_task_coordinator, "create_task", lambda **kwargs: {"id": "task-flags", "task_type": kwargs["task_type"], "status": kwargs["status"]})
    monkeypatch.setattr(dev_nodes, "analysis_persister", lambda state, shared_db=None: {"status": "SKIPPED", "dev_tracking_next_action": "develop_embedding"})
    monkeypatch.setattr(dev_nodes, "develop_embedding", lambda state, shared_db=None: {"status": "SKIPPED", "dev_tracking_next_action": "develop_loop_controller"})

    payload = {
        **_valid_payload(source_dir=str(tmp_path)),
        "api_key": "test-key",
        "use_llm_forensic_profiler": False,
        "use_llm_gap_analyzer": False,
        "use_llm_intent_classifier": False,
    }
    result = run_dev_tracking_analysis(payload)

    assert calls == {"forensic": 0, "gap": 0, "intent": 0}
    assert result["data"]["forensic_profiler_meta"]["mode"] == "rule_based"
    assert result["data"]["gap_analyzer_meta"]["mode"] == "rule_based"
    assert result["data"]["intent_classifier_meta"]["mode"] == "rule_based"
    assert result["data"]["intent_classification"][0]["recommended_action"] == "PM_REVIEW"

    graphs._PipelineRegistry._cache.clear()
