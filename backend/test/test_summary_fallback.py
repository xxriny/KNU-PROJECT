import os
import sys
import unittest


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from result_shaping.result_shaper import shape_result


class SummaryFallbackTests(unittest.TestCase):
    def test_shape_result_prefers_context_spec_summary(self):
        shaped = shape_result({
            "metadata": {"status": "Success", "action_type": "CREATE"},
            "requirements_rtm": [{"REQ_ID": "REQ-001", "priority": "Must-have"}],
            "context_spec": {"summary": "pm summary", "risk_factors": ["r1"]},
            "sa_output": {"summary": "sa summary"},
        })

        self.assertEqual(shaped["pm_overview"]["summary"], "pm summary")
        self.assertEqual(shaped["project_overview"]["summary"], "pm summary")
        self.assertEqual(shaped["project_overview"]["summary_source"], "context_spec")

    def test_shape_result_falls_back_to_sa_output_summary(self):
        shaped = shape_result({
            "metadata": {"status": "Success", "action_type": "REVERSE_ENGINEER"},
            "requirements_rtm": [],
            "context_spec": {},
            "sa_output": {"summary": "sa summary"},
        })

        self.assertEqual(shaped["project_overview"]["summary"], "sa summary")
        self.assertEqual(shaped["project_overview"]["summary_source"], "sa_output")


if __name__ == "__main__":
    unittest.main()

