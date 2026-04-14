import os
import sys
import unittest


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.domain.pm.nodes.pm_phase5 import _build_tech_stack_details


class PMPhase5TechStackTests(unittest.TestCase):
    def test_manifest_frameworks_are_promoted_to_detailed_output(self):
        system_scan = {
            "framework_evidence": [
                {"framework": "React", "file": "package.json", "reason": "dependencies.react 발견"},
                {"framework": "FastAPI", "file": "backend/main.py", "reason": "엔트리 파일 발견"},
            ]
        }

        detailed, plain, score = _build_tech_stack_details(["React", "Redis"], system_scan)

        detailed_by_name = {item["name"]: item for item in detailed}
        self.assertIn("React", plain)
        self.assertIn("FastAPI", plain)
        self.assertIn("Redis", plain)
        self.assertEqual(detailed_by_name["React"]["source"], "manifest")
        self.assertEqual(detailed_by_name["FastAPI"]["source"], "manifest")
        self.assertEqual(detailed_by_name["Redis"]["source"], "inferred")
        self.assertGreater(score, 0.0)


if __name__ == "__main__":
    unittest.main()
