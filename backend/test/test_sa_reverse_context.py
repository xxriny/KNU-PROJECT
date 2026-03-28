import os
import sys
import unittest


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.nodes.sa_reverse_context import sa_reverse_context_node
from result_shaping.result_shaper import shape_result


class SAReverseContextTests(unittest.TestCase):
    def test_reverse_context_node_builds_summary_from_sa_outputs(self):
        state = {
            "metadata": {"project_name": "navigator", "status": "Success"},
            "source_dir": "navigator",
            "sa_phase1": {
                "scanned_files": 12,
                "scanned_functions": 48,
                "detected_frameworks": ["React", "FastAPI"],
                "framework_evidence": [{"framework": "React", "file": "src/App.jsx"}],
            },
            "sa_phase3": {
                "evidence_summary": {"warnings": ["테스트 자산은 제한적입니다."]},
            },
            "sa_phase5": {
                "pattern": "Clean Architecture",
                "mapped_requirements": [
                    {"name": "src/App.jsx", "layer": "Presentation", "layer_confidence": 88},
                    {"name": "backend/main.py", "layer": "Application", "layer_confidence": 81},
                    {"name": "backend/connectors/folder_connector.py", "layer": "Infrastructure", "layer_confidence": 49},
                ],
            },
            "sa_phase8": {
                "parallel_batches": [["MOD-001", "MOD-002"], ["MOD-003"]],
                "cyclic_requirements": [],
                "inferred_dependencies": [{"target": "MOD-003", "depends_on": "MOD-001", "source": "data_flow", "confidence": 0.72}],
            },
            "thinking_log": [],
        }

        result = sa_reverse_context_node(state)
        reverse_context = result["sa_reverse_context"]

        self.assertIn("역분석", reverse_context["summary"])
        self.assertTrue(reverse_context["architecture_highlights"])
        self.assertTrue(reverse_context["dependency_observations"])
        self.assertTrue(reverse_context["risk_factors"])
        self.assertTrue(reverse_context["next_steps"])

    def test_shape_result_uses_reverse_context_for_pm_overview(self):
        shaped = shape_result({
            "metadata": {"status": "Success"},
            "requirements_rtm": [],
            "sa_reverse_context": {
                "summary": "reverse summary",
                "risk_factors": ["layer ambiguity"],
            },
        })

        self.assertEqual(shaped["pm_overview"]["summary"], "reverse summary")
        self.assertEqual(shaped["pm_overview"]["risks"], ["layer ambiguity"])
        self.assertIn("project_overview", shaped)
        self.assertEqual(shaped["project_overview"]["summary"], "reverse summary")
        self.assertEqual(shaped["project_overview"]["summary_source"], "sa_reverse_context")
        self.assertIn("sa_artifacts", shaped)
        self.assertIn("container_diagram_spec", shaped["sa_artifacts"])


if __name__ == "__main__":
    unittest.main()