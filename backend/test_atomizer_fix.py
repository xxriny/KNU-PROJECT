import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline.nodes.pm_phase4 import _dedupe_semantic_edges
from pipeline.nodes.chat_revision import (
    ChatRevisionPatchOutput,
    RTMRequirementPatch,
    RTMRevision,
    _apply_revision_patch,
    _normalize_rtm,
    _normalize_semantic_graph,
    _select_revision_context,
)


class RevisionContractTests(unittest.TestCase):
    def test_dedupe_semantic_edges_collapses_reverse_related_to_pairs(self):
        edges = _dedupe_semantic_edges([
            {"source": "REQ-008", "target": "REQ-009", "relation": "related_to"},
            {"source": "REQ-009", "target": "REQ-008", "relation": "related_to"},
            {"source": "REQ-001", "target": "REQ-002", "relation": "depends_on"},
            {"source": "REQ-002", "target": "REQ-001", "relation": "depends_on"},
        ])

        self.assertEqual(edges, [
            {"source": "REQ-008", "target": "REQ-009", "relation": "related_to"},
            {"source": "REQ-001", "target": "REQ-002", "relation": "depends_on"},
            {"source": "REQ-002", "target": "REQ-001", "relation": "depends_on"},
        ])

    def test_normalize_rtm_converts_legacy_id_field(self):
        normalized = _normalize_rtm([
            {
                "id": "REQ-001",
                "description": "로그인",
                "depends_on": None,
            },
            {
                "description": "회원가입",
            },
        ])

        self.assertEqual(normalized[0]["REQ_ID"], "REQ-001")
        self.assertNotIn("id", normalized[0])
        self.assertEqual(normalized[0]["depends_on"], [])
        self.assertEqual(normalized[1]["REQ_ID"], "REQ-002")

    def test_normalize_semantic_graph_filters_invalid_edges_and_backfills_nodes(self):
        requirements = _normalize_rtm([
            {"REQ_ID": "REQ-001", "description": "API", "category": "Backend"},
            {"REQ_ID": "REQ-002", "description": "UI", "category": "Frontend", "depends_on": ["REQ-001"]},
        ])
        graph = _normalize_semantic_graph({
            "nodes": [{"REQ_ID": "REQ-001", "label": "API"}],
            "edges": [
                {"source": "REQ-001", "target": "REQ-002", "relation": "depends_on"},
                {"source": "REQ-404", "target": "REQ-002", "relation": "depends_on"},
            ],
        }, requirements)

        self.assertEqual({node["id"] for node in graph["nodes"]}, {"REQ-001", "REQ-002"})
        self.assertEqual(graph["edges"], [{"source": "REQ-001", "target": "REQ-002", "relation": "depends_on"}])

    def test_apply_revision_patch_updates_adds_and_deletes_requirements(self):
        requirements = _normalize_rtm([
            {
                "REQ_ID": "REQ-001",
                "description": "로그인",
                "category": "Backend",
                "priority": "Must-have",
                "depends_on": [],
            },
            {
                "REQ_ID": "REQ-002",
                "description": "대시보드",
                "category": "Frontend",
                "priority": "Should-have",
                "depends_on": ["REQ-001"],
            },
            {
                "REQ_ID": "REQ-003",
                "description": "배포 자동화",
                "category": "Infrastructure",
                "priority": "Could-have",
                "depends_on": ["REQ-001"],
            },
        ])

        patch = ChatRevisionPatchOutput(
            agent_reply="반영 완료",
            modified_requirements=[
                RTMRequirementPatch(
                    REQ_ID="REQ-002",
                    priority="Must-have",
                    depends_on=["REQ-001"],
                    test_criteria="주요 KPI가 1초 이내에 표시된다.",
                )
            ],
            added_requirements=[
                RTMRevision(
                    description="관리자 감사 로그",
                    category="Security",
                    priority="Should-have",
                    rationale="운영 추적성 강화",
                    depends_on=["REQ-001"],
                    test_criteria="관리자 액션이 모두 저장된다.",
                )
            ],
            deleted_req_ids=["REQ-003"],
        )

        revised = _apply_revision_patch(requirements, patch)

        self.assertEqual([item["REQ_ID"] for item in revised], ["REQ-001", "REQ-002", "REQ-004"])
        req_002 = next(item for item in revised if item["REQ_ID"] == "REQ-002")
        self.assertEqual(req_002["priority"], "Must-have")
        self.assertEqual(req_002["test_criteria"], "주요 KPI가 1초 이내에 표시된다.")
        req_004 = next(item for item in revised if item["REQ_ID"] == "REQ-004")
        self.assertEqual(req_004["category"], "Security")
        self.assertEqual(req_004["depends_on"], ["REQ-001"])

    def test_select_revision_context_returns_targeted_subset_for_specific_req(self):
        requirements = _normalize_rtm([
            {"REQ_ID": f"REQ-{index:03d}", "description": f"기능 {index}", "category": "Backend", "depends_on": []}
            for index in range(1, 21)
        ])
        requirements[5]["description"] = "알림 전송 엔진"
        requirements[6]["description"] = "알림 설정 화면"
        requirements[6]["depends_on"] = ["REQ-006"]
        graph = _normalize_semantic_graph({}, requirements)

        selected, meta = _select_revision_context(
            requirements,
            graph,
            "REQ-006 알림 엔진과 연결된 설정 화면만 수정해줘",
        )

        self.assertEqual(meta["scope"], "partial_scope")
        self.assertIn("REQ-006", {item["REQ_ID"] for item in selected})
        self.assertIn("REQ-007", {item["REQ_ID"] for item in selected})
        self.assertLess(len(selected), len(requirements))

    def test_select_revision_context_uses_full_scope_for_broad_request(self):
        requirements = _normalize_rtm([
            {"REQ_ID": f"REQ-{index:03d}", "description": f"기능 {index}", "category": "Backend", "depends_on": []}
            for index in range(1, 21)
        ])

        selected, meta = _select_revision_context(
            requirements,
            {"nodes": [], "edges": []},
            "전체 RTM을 전면 재구성해줘",
        )

        self.assertEqual(meta["scope"], "full_scope")
        self.assertEqual(len(selected), len(requirements))

    def test_rtm_builder_returns_requirements_rtm_for_analysis_contract(self):
        state = {
            "prioritized_requirements": [
                {
                    "REQ_ID": "REQ-001",
                    "category": "Backend",
                    "description": "회원 가입 기능",
                    "priority": "Must-have",
                }
            ],
            "thinking_log": [],
        }

        from unittest.mock import patch
        from pipeline.nodes.pm_phase3 import rtm_builder_node

        class _Req:
            def __init__(self):
                self.REQ_ID = "REQ-001"
                self.category = "Backend"
                self.description = "회원 가입 기능"
                self.priority = "Must-have"
                self.depends_on = []
                self.test_criteria = "회원 가입이 성공한다."

            def model_dump(self):
                return {
                    "REQ_ID": self.REQ_ID,
                    "category": self.category,
                    "description": self.description,
                    "priority": self.priority,
                    "depends_on": self.depends_on,
                    "test_criteria": self.test_criteria,
                }

        class _Result:
            def __init__(self):
                self.requirements = [_Req()]

        with patch("pipeline.nodes.pm_phase3.call_structured_with_thinking", return_value=(_Result(), "ok")):
            result = rtm_builder_node(state)

        self.assertIn("requirements_rtm", result)
        self.assertEqual(result["requirements_rtm"], result["rtm_matrix"])


if __name__ == "__main__":
    unittest.main()
