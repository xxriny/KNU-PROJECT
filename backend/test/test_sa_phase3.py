import os
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.domain.sa.nodes.sa_phase3 import sa_phase3_node


def _write_file(path: str, content: str = ""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


class SAPhase3Tests(unittest.TestCase):
    def _build_reverse_repo(self, root: str, *, include_tests: bool = True):
        _write_file(os.path.join(root, "backend", "observability", "logger.py"), "def get_logger():\n    return None\n")
        _write_file(os.path.join(root, "backend", "observability", "metrics.py"), "def track_node():\n    return None\n")
        _write_file(os.path.join(root, "backend", "pipeline", "schemas.py"), "from pydantic import BaseModel\n")
        _write_file(
            os.path.join(root, "backend", "pipeline", "utils.py"),
            "def with_structured_output():\n    pass\n\n"
            "def call_structured_with_usage():\n    return None\n",
        )
        _write_file(
            os.path.join(root, "backend", "pipeline", "graph.py"),
            "from langgraph.graph import StateGraph\n\n"
            "def build():\n    graph = StateGraph(dict)\n    graph.add_conditional_edges('a', lambda _: 'b', {'b': 'c'})\n",
        )
        _write_file(os.path.join(root, "backend", "result_shaping", "result_shaper.py"), "def shape_result(raw):\n    return raw\n")
        _write_file(
            os.path.join(root, "backend", "pipeline", "nodes", "pm_phase1.py"),
            "def run():\n    input_tokens = 1\n    output_tokens = 1\n    return input_tokens + output_tokens\n",
        )
        _write_file(
            os.path.join(root, "backend", "pipeline", "nodes", "atomizer.py"),
            "def run():\n    return 'call_structured_with_usage'\n",
        )
        if include_tests:
            _write_file(os.path.join(root, "backend", "test", "test_dummy.py"), "def test_dummy():\n    assert True\n")

    def test_reverse_mode_uses_rule_based_assessment_without_llm(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self._build_reverse_repo(temp_dir)
            state = {
                "action_type": "REVERSE_ENGINEER",
                "system_scan": {
                    "status": "Pass",
                    "source_dir": temp_dir,
                    "scanned_files": 32,
                    "scanned_functions": 140,
                    "languages": {"python": 120, "javascript": 20},
                    "detected_frameworks": ["FastAPI", "React"],
                    "framework_evidence": [{"framework": "FastAPI", "file": "backend/main.py"}],
                },
                "sa_phase2": {"gap_report": []},
                "requirements_rtm": [],
                "rtm_matrix": [],
                "thinking_log": [],
            }

            with patch("pipeline.domain.sa.nodes.sa_phase3.call_structured", side_effect=AssertionError("reverse path should not call LLM")):
                result = sa_phase3_node(state)

            phase = result["sa_phase3"]
            self.assertEqual(phase["status"], "Pass")
            self.assertEqual(phase["decision"], phase["status"])
            self.assertEqual(phase["high_risk_reqs"], [])
            self.assertEqual(phase["diagnostic_code"], "REVERSE_RULE_BASED_PASS")
            self.assertIn("evidence_summary", phase)
            self.assertIn("score_breakdown", phase)

    def test_reverse_mode_with_low_evidence_returns_needs_clarification(self):
        state = {
            "action_type": "REVERSE_ENGINEER",
            "system_scan": {
                "status": "Pass",
                "source_dir": "",
                "scanned_files": 2,
                "scanned_functions": 5,
                "languages": {},
                "detected_frameworks": [],
                "framework_evidence": [],
            },
            "sa_phase2": {"gap_report": []},
            "requirements_rtm": [],
            "rtm_matrix": [],
            "thinking_log": [],
        }

        with patch("pipeline.domain.sa.nodes.sa_phase3.call_structured", side_effect=AssertionError("reverse path should not call LLM")):
            result = sa_phase3_node(state)

        phase = result["sa_phase3"]
        self.assertEqual(phase["status"], "Needs_Clarification")
        self.assertEqual(phase["diagnostic_code"], "REVERSE_EVIDENCE_INSUFFICIENT")
        self.assertEqual(phase["decision"], phase["status"])
        self.assertGreaterEqual(phase["complexity_score"], 0)

    def test_reverse_mode_filters_high_risk_reqs_to_known_ids(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self._build_reverse_repo(temp_dir)
            state = {
                "action_type": "REVERSE_ENGINEER",
                "system_scan": {
                    "status": "Pass",
                    "source_dir": temp_dir,
                    "scanned_files": 18,
                    "scanned_functions": 60,
                    "languages": {"python": 60},
                    "detected_frameworks": ["FastAPI"],
                    "framework_evidence": [{"framework": "FastAPI", "file": "backend/main.py"}],
                },
                "sa_phase2": {
                    "gap_report": [
                        {"req_id": "REQ-001", "impact_level": "High"},
                        {"req_id": "REQ-404", "impact_level": "High"},
                    ]
                },
                "requirements_rtm": [{"REQ_ID": "REQ-001", "description": "로그인"}],
                "thinking_log": [],
            }

            result = sa_phase3_node(state)

        phase = result["sa_phase3"]
        self.assertEqual(phase["high_risk_reqs"], ["REQ-001"])

    def test_create_mode_invalid_rtm_returns_needs_clarification(self):
        state = {
            "action_type": "CREATE",
            "requirements_rtm": [{"description": "REQ ID 누락"}],
            "thinking_log": [],
        }

        result = sa_phase3_node(state)
        phase = result["sa_phase3"]

        self.assertEqual(phase["status"], "Needs_Clarification")
        self.assertEqual(phase["diagnostic_code"], "RTM_SCHEMA_INVALID")
        self.assertEqual(phase["high_risk_reqs"], [])

    def test_reverse_mode_complexity_score_is_deterministic(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self._build_reverse_repo(temp_dir)
            state = {
                "action_type": "REVERSE_ENGINEER",
                "system_scan": {
                    "status": "Pass",
                    "source_dir": temp_dir,
                    "scanned_files": 22,
                    "scanned_functions": 100,
                    "languages": {"python": 100},
                    "detected_frameworks": ["FastAPI"],
                    "framework_evidence": [{"framework": "FastAPI", "file": "backend/main.py"}],
                },
                "sa_phase2": {"gap_report": []},
                "requirements_rtm": [],
                "thinking_log": [],
            }

            first = sa_phase3_node(state)["sa_phase3"]
            second = sa_phase3_node(state)["sa_phase3"]

        self.assertEqual(first["complexity_score"], second["complexity_score"])
        self.assertEqual(first["status"], second["status"])

    def test_evidence_summary_quality_score_range(self):
        """evidence_quality_score는 0~100 범위 확인"""
        with tempfile.TemporaryDirectory() as temp_dir:
            self._build_reverse_repo(temp_dir)
            state = {
                "action_type": "REVERSE_ENGINEER",
                "system_scan": {
                    "status": "Pass",
                    "source_dir": temp_dir,
                    "scanned_files": 25,
                    "scanned_functions": 150,
                    "languages": {"python": 150},
                    "detected_frameworks": ["FastAPI"],
                    "framework_evidence": [{"framework": "FastAPI", "file": "backend/main.py"}],
                },
                "sa_phase2": {"gap_report": []},
                "requirements_rtm": [],
                "thinking_log": [],
            }

            result = sa_phase3_node(state)
            phase = result["sa_phase3"]
            score = phase["evidence_summary"]["evidence_quality_score"]
            
            self.assertGreaterEqual(score, 0, "evidence_quality_score는 0 이상이어야 함")
            self.assertLessEqual(score, 100, "evidence_quality_score는 100 이하여야 함")
            self.assertIsInstance(score, int, "evidence_quality_score는 int여야 함")

    def test_score_breakdown_structure(self):
        """score_breakdown 항목 구조 확인"""
        with tempfile.TemporaryDirectory() as temp_dir:
            self._build_reverse_repo(temp_dir)
            state = {
                "action_type": "REVERSE_ENGINEER",
                "system_scan": {
                    "status": "Pass",
                    "source_dir": temp_dir,
                    "scanned_files": 15,
                    "scanned_functions": 50,
                    "languages": {"python": 50},
                    "detected_frameworks": [],
                    "framework_evidence": [],
                },
                "sa_phase2": {"gap_report": []},
                "requirements_rtm": [],
                "thinking_log": [],
            }

            result = sa_phase3_node(state)
            phase = result["sa_phase3"]
            breakdown = phase["score_breakdown"]
            
            self.assertIsInstance(breakdown, list, "score_breakdown는 list여야 함")
            self.assertGreater(len(breakdown), 0, "score_breakdown은 최소 1개 이상 항목 필요")
            
            for item in breakdown:
                self.assertIn("code", item, "각 항목에 'code' 필드 필수")
                self.assertIn("delta", item, "각 항목에 'delta' 필드 필수")
                self.assertIn("message", item, "각 항목에 'message' 필드 필수")
                self.assertIsInstance(item["delta"], int, "delta는 int여야 함")
                self.assertIsInstance(item["message"], str, "message는 str여야 함")


if __name__ == "__main__":
    unittest.main()