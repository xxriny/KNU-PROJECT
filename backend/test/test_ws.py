import os
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app


class WebSocketTests(unittest.TestCase):
    def test_ping_pong_contract(self):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/pipeline") as websocket:
                websocket.send_text('{"type": "ping", "payload": {}}')
                response = websocket.receive_json()

        self.assertEqual(response, {"type": "pong"})

    def test_invalid_json_returns_error(self):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/pipeline") as websocket:
                websocket.send_text('{invalid')
                response = websocket.receive_json()

        self.assertEqual(response["type"], "error")
        self.assertEqual(response["data"]["message"], "Invalid JSON")

    def test_analyze_streams_progress_before_result(self):
        class FakePipeline:
            async def astream(self, payload, stream_mode="updates"):
                self.payload = payload
                self.stream_mode = stream_mode
                yield {
                    "atomizer": {
                        "raw_requirements": [{"REQ_ID": "REQ-001", "description": "회원 가입", "category": "Backend"}],
                        "metadata": {"project_name": "Test", "action_type": "CREATE", "status": "Success"},
                        "thinking_log": [{"node": "atomizer", "thinking": "원자화 완료"}],
                    }
                }
                yield {
                    "prioritizer": {
                        "prioritized_requirements": [{"REQ_ID": "REQ-001", "description": "회원 가입", "category": "Backend", "priority": "Must-have"}],
                        "thinking_log": [
                            {"node": "atomizer", "thinking": "원자화 완료"},
                            {"node": "prioritizer", "thinking": "우선순위 완료"},
                        ],
                    }
                }
                yield {
                    "rtm_builder": {
                        "rtm_matrix": [{"REQ_ID": "REQ-001", "description": "회원 가입", "category": "Backend", "priority": "Must-have", "depends_on": [], "test_criteria": "가입 성공"}],
                        "thinking_log": [
                            {"node": "atomizer", "thinking": "원자화 완료"},
                            {"node": "prioritizer", "thinking": "우선순위 완료"},
                            {"node": "rtm_builder", "thinking": "RTM 완료"},
                        ],
                    }
                }
                yield {
                    "semantic_indexer": {
                        "semantic_graph": {"nodes": [{"id": "REQ-001", "label": "회원 가입", "category": "Backend", "tags": []}], "edges": []},
                        "thinking_log": [
                            {"node": "atomizer", "thinking": "원자화 완료"},
                            {"node": "prioritizer", "thinking": "우선순위 완료"},
                            {"node": "rtm_builder", "thinking": "RTM 완료"},
                            {"node": "semantic_indexer", "thinking": "그래프 완료"},
                        ],
                    }
                }
                yield {
                    "context_spec": {
                        "context_spec": {"summary": "요약", "key_decisions": [], "open_questions": [], "tech_stack_suggestions": [], "risk_factors": [], "next_steps": []},
                        "requirements_rtm": [{"REQ_ID": "REQ-001", "description": "회원 가입", "category": "Backend", "priority": "Must-have", "depends_on": [], "test_criteria": "가입 성공"}],
                        "metadata": {"project_name": "Test", "action_type": "CREATE", "status": "Completed"},
                        "thinking_log": [
                            {"node": "atomizer", "thinking": "원자화 완료"},
                            {"node": "prioritizer", "thinking": "우선순위 완료"},
                            {"node": "rtm_builder", "thinking": "RTM 완료"},
                            {"node": "context_spec", "thinking": "명세서 완료"},
                        ],
                    }
                }

        with patch("main.get_analysis_pipeline", return_value=FakePipeline()):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/pipeline") as websocket:
                    websocket.send_json({
                        "type": "analyze",
                        "payload": {"idea": "회원 가입 서비스", "context": "", "api_key": "", "model": "gemini-2.5-flash", "action_type": "CREATE"},
                    })
                    messages = []
                    while True:
                        message = websocket.receive_json()
                        messages.append(message)
                        if message.get("type") == "result":
                            break

        self.assertEqual(messages[0]["type"], "status")
        self.assertEqual(messages[0]["node"], "atomizer")
        self.assertEqual(messages[0]["data"]["status"], "running")
        self.assertTrue(any(msg["type"] == "thinking" and msg["node"] == "atomizer" for msg in messages))
        self.assertTrue(any(msg["type"] == "status" and msg["node"] == "prioritizer" and msg["data"]["status"] == "running" for msg in messages))
        self.assertTrue(any(msg["type"] == "status" and msg["node"] == "semantic_indexer" and msg["data"]["status"] == "running" for msg in messages))
        self.assertTrue(any(msg["type"] == "status" and msg["node"] == "context_spec" and msg["data"]["status"] == "done" for msg in messages))
        self.assertEqual(messages[-1]["type"], "result")
        self.assertEqual(messages[-1]["data"]["metadata"]["status"], "Completed")
        self.assertNotIn("rtm_matrix", messages[-1]["data"])
        self.assertEqual(messages[-1]["data"]["requirements_rtm"][0]["REQ_ID"], "REQ-001")

    def test_analyze_reverse_requires_source_dir(self):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/pipeline") as websocket:
                websocket.send_json({
                    "type": "analyze",
                    "payload": {
                        "idea": "",
                        "context": "",
                        "api_key": "",
                        "model": "gemini-2.5-flash",
                        "action_type": "REVERSE_ENGINEER",
                        "source_dir": "",
                    },
                })
                message = websocket.receive_json()

        self.assertEqual(message["type"], "error")
        self.assertEqual(message["data"]["message"], "역공학 모드입니다. 먼저 폴더를 선택하세요.")

    def test_analyze_update_requires_idea(self):
        with TestClient(app) as client:
            with client.websocket_connect("/ws/pipeline") as websocket:
                websocket.send_json({
                    "type": "analyze",
                    "payload": {
                        "idea": "",
                        "context": "",
                        "api_key": "",
                        "model": "gemini-2.5-flash",
                        "action_type": "UPDATE",
                        "source_dir": "C:/tmp/project",
                    },
                })
                message = websocket.receive_json()

        self.assertEqual(message["type"], "error")
        self.assertEqual(message["data"]["message"], "신규 기획/기능 확장 모드에서는 아이디어 입력이 필요합니다.")

    def test_analyze_reverse_builds_context_from_source_dir(self):
        class FakePipeline:
            async def astream(self, payload, stream_mode="updates"):
                self.payload = payload
                self.stream_mode = stream_mode
                yield {
                    "sa_phase1": {
                        "sa_phase1": {"status": "Pass", "scanned_files": 3, "scanned_functions": 9},
                        "thinking_log": [{"node": "sa_phase1", "thinking": "구조 분석 완료"}],
                    }
                }
                yield {
                    "sa_phase8": {
                        "sa_phase8": {"status": "Pass", "topo_queue": ["REQ-001"], "cyclic_requirements": []},
                        "requirements_rtm": [{"REQ_ID": "REQ-001", "description": "핵심 기능", "category": "Backend", "priority": "Must-have", "depends_on": [], "test_criteria": "동작 확인"}],
                        "metadata": {"project_name": "ReverseTest", "action_type": "REVERSE_ENGINEER", "status": "Completed"},
                        "sa_output": {"topology_queue": {"status": "Pass", "topo_queue": ["REQ-001"]}},
                        "thinking_log": [{"node": "sa_phase8", "thinking": "위상 정렬 완료"}],
                    }
                }

        fake_pipeline = FakePipeline()
        fake_functions = [
            {"file": "src/service.py", "func_name": "build_report", "lineno": 10, "docstring": "리포트 생성", "lang": "python"}
        ]

        with patch("main.get_analysis_pipeline", return_value=fake_pipeline), \
             patch("main.extract_functions", return_value=fake_functions), \
             patch("main.summarize_for_llm", return_value="src/service.py:build_report:L10"):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/pipeline") as websocket:
                    websocket.send_json({
                        "type": "analyze",
                        "payload": {
                            "idea": "",
                            "context": "",
                            "api_key": "",
                            "model": "gemini-2.5-flash",
                            "action_type": "REVERSE_ENGINEER",
                            "source_dir": "C:/tmp/project",
                        },
                    })

                    last_message = None
                    while True:
                        message = websocket.receive_json()
                        last_message = message
                        if message.get("type") in {"result", "error"}:
                            break

        self.assertEqual(last_message["type"], "result")
        self.assertTrue(fake_pipeline.payload["project_context"])
        self.assertIn("[함수 요약]", fake_pipeline.payload["project_context"])
        self.assertEqual(last_message["data"].get("pipeline_type"), "analysis_reverse")
        self.assertIn("sa_output", last_message["data"])

    def test_analyze_update_streams_pm_then_sa(self):
        class FakePipeline:
            async def astream(self, payload, stream_mode="updates"):
                self.payload = payload
                self.stream_mode = stream_mode
                yield {
                    "sa_phase1": {
                        "sa_phase1": {"status": "Pass", "scanned_files": 3, "scanned_functions": 9},
                        "thinking_log": [{"node": "sa_phase1", "thinking": "구조 분석 완료"}],
                    }
                }
                yield {
                    "atomizer": {
                        "raw_requirements": [{"REQ_ID": "REQ-001", "description": "기능 확장", "category": "Backend"}],
                        "metadata": {"project_name": "UpdateTest", "action_type": "UPDATE", "status": "Success"},
                        "thinking_log": [{"node": "atomizer", "thinking": "원자화 완료"}],
                    }
                }
                yield {
                    "prioritizer": {
                        "prioritized_requirements": [{"REQ_ID": "REQ-001", "description": "기능 확장", "category": "Backend", "priority": "Must-have"}],
                        "thinking_log": [{"node": "prioritizer", "thinking": "우선순위 완료"}],
                    }
                }
                yield {
                    "context_spec": {
                        "context_spec": {"summary": "요약"},
                        "thinking_log": [{"node": "context_spec", "thinking": "컨텍스트 완료"}],
                    }
                }
                yield {
                    "sa_phase8": {
                        "sa_phase8": {"status": "Pass", "topo_queue": ["REQ-001"], "cyclic_requirements": []},
                        "sa_output": {"topology_queue": {"status": "Pass", "topo_queue": ["REQ-001"]}},
                        "metadata": {"project_name": "UpdateTest", "action_type": "UPDATE", "status": "Completed"},
                        "requirements_rtm": [{"REQ_ID": "REQ-001", "description": "기능 확장", "category": "Backend", "priority": "Must-have", "depends_on": []}],
                    }
                }

        with patch("main.get_analysis_pipeline", return_value=FakePipeline()):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/pipeline") as websocket:
                    websocket.send_json({
                        "type": "analyze",
                        "payload": {
                            "idea": "결제 흐름에 쿠폰 로직 추가",
                            "context": "기존 결제 서비스",
                            "api_key": "",
                            "model": "gemini-2.5-flash",
                            "action_type": "UPDATE",
                            "source_dir": "C:/tmp/project",
                        },
                    })

                    messages = []
                    while True:
                        message = websocket.receive_json()
                        messages.append(message)
                        if message.get("type") in {"result", "error"}:
                            break

        running_nodes = [msg.get("node") for msg in messages if msg.get("type") == "status" and msg.get("data", {}).get("status") == "running"]
        self.assertIn("prioritizer", running_nodes)
        self.assertIn("sa_phase1", running_nodes)
        self.assertLess(running_nodes.index("sa_phase1"), running_nodes.index("prioritizer"))
        self.assertEqual(messages[-1]["type"], "result")
        self.assertEqual(messages[-1]["data"].get("pipeline_type"), "analysis_update")
        self.assertIn("sa_output", messages[-1]["data"])


if __name__ == "__main__":
    unittest.main()
