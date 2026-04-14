import os
import sys
import unittest


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.domain.sa.nodes.sa_phase8 import sa_phase8_node


class SAPhase8DependencyTests(unittest.TestCase):
    def test_dependency_synthesis_creates_multiple_parallel_batches(self):
        state = {
            "action_type": "REVERSE_ENGINEER",
            "requirements_rtm": [],
            "rtm_matrix": [],
            "sa_phase5": {
                "mapped_requirements": [
                    {"REQ_ID": "MOD-001", "description": "request handler", "depends_on": []},
                    {"REQ_ID": "MOD-002", "description": "file reader", "depends_on": []},
                    {"REQ_ID": "MOD-006", "description": "pipeline executor", "depends_on": []},
                ]
            },
            "sa_phase7": {
                "interface_contracts": [
                    {
                        "contract_id": "IF-MOD-001",
                        "input_spec": '{"source_path": str}',
                        "output_spec": '{"files": list[str], "module_graph": dict}',
                    },
                    {
                        "contract_id": "IF-MOD-002",
                        "input_spec": '{"files": list[str], "module_graph": dict}',
                        "output_spec": '{"analysis_result": dict, "dependency_map": dict}',
                    },
                    {
                        "contract_id": "IF-MOD-006",
                        "input_spec": '{"analysis_result": dict, "dependency_map": dict}',
                        "output_spec": '{"processed_data": dict}',
                    },
                ]
            },
            "semantic_graph": {"nodes": [], "edges": []},
            "thinking_log": [],
        }

        result = sa_phase8_node(state)
        phase = result["sa_phase8"]

        self.assertEqual(phase["status"], "Pass")
        self.assertGreaterEqual(len(phase["parallel_batches"]), 2)
        self.assertTrue(any(item["source"] == "data_flow" for item in phase["inferred_dependencies"]))
        self.assertIn("MOD-001", {item["from"] for item in phase["dependency_sources"]["MOD-002"]})
        self.assertTrue(any(item.get("applied_to_canonical") for item in phase["dependency_sources"]["MOD-002"] if item["source"] == "data_flow"))
        self.assertFalse(any(item.get("applied_to_canonical") for item in phase["dependency_sources"]["MOD-006"] if item["source"] == "data_flow"))
        self.assertIn("MOD-001", phase["parallel_batches"][0])
        self.assertIn("MOD-006", phase["parallel_batches"][0])
        self.assertEqual(phase["parallel_batches"][1], ["MOD-002"])
        self.assertIn("MOD-001", phase["topo_queue"])
        self.assertIn("MOD-002", phase["topo_queue"])

    def test_low_signal_contract_tokens_do_not_become_canonical_dependencies(self):
        state = {
            "action_type": "REVERSE_ENGINEER",
            "requirements_rtm": [],
            "rtm_matrix": [],
            "sa_phase5": {
                "mapped_requirements": [
                    {"REQ_ID": "MOD-010", "description": "metrics producer", "depends_on": []},
                    {"REQ_ID": "MOD-011", "description": "metrics consumer", "depends_on": []},
                ]
            },
            "sa_phase7": {
                "interface_contracts": [
                    {
                        "contract_id": "IF-MOD-010",
                        "output_spec": '{"analysis_config": dict, "metric_name": str}',
                    },
                    {
                        "contract_id": "IF-MOD-011",
                        "input_spec": '{"analysis_config": dict, "metric_name": str}',
                    },
                ]
            },
            "semantic_graph": {"nodes": [], "edges": []},
            "thinking_log": [],
        }

        result = sa_phase8_node(state)
        phase = result["sa_phase8"]
        dependency_sources = phase["dependency_sources"]["MOD-011"]

        self.assertTrue(any(item["source"] == "data_flow" for item in dependency_sources))
        self.assertFalse(any(item.get("applied_to_canonical") for item in dependency_sources if item["source"] == "data_flow"))
        self.assertIn("MOD-010", phase["parallel_batches"][0])
        self.assertIn("MOD-011", phase["parallel_batches"][0])
        mapped_target = next(item for item in result["sa_output"]["topology_queue"]["dependency_sources"]["MOD-011"] if item["source"] == "data_flow")
        self.assertFalse(mapped_target.get("applied_to_canonical"))

    def test_import_hints_create_reverse_dependencies(self):
        state = {
            "action_type": "REVERSE_ENGINEER",
            "requirements_rtm": [],
            "rtm_matrix": [],
            "sa_phase5": {
                "mapped_requirements": [
                    {"REQ_ID": "MOD-001", "description": "main app", "file_path": "backend/main.py", "canonical_id": "main", "import_hints": ["backend/orchestration/pipeline_runner.py"], "depends_on": []},
                    {"REQ_ID": "MOD-002", "description": "runner", "file_path": "backend/orchestration/pipeline_runner.py", "canonical_id": "pipeline-runner", "import_hints": [], "depends_on": []},
                ]
            },
            "sa_phase7": {"interface_contracts": []},
            "semantic_graph": {"nodes": [], "edges": []},
            "thinking_log": [],
        }

        result = sa_phase8_node(state)
        dependency_sources = result["sa_phase8"]["dependency_sources"]["MOD-001"]

        self.assertTrue(any(item["source"] == "code_import" for item in dependency_sources))
        self.assertIn("MOD-002", result["sa_phase8"]["topo_queue"])
        self.assertIn("MOD-002", result["sa_output"]["topology_queue"]["topo_queue"])


if __name__ == "__main__":
    unittest.main()
