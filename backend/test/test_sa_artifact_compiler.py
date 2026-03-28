import os
import sys
import unittest


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from result_shaping.sa_artifact_compiler import compile_sa_artifacts


class SAArtifactCompilerTests(unittest.TestCase):
    def test_compile_sa_artifacts_generates_mvp_sections(self):
        result = {
            "sa_phase3": {"status": "Pass"},
            "sa_phase5": {
                "mapped_requirements": [
                    {
                        "REQ_ID": "REQ-001",
                        "layer": "Application",
                        "description": "핵심 분석",
                        "depends_on": ["REQ-000"],
                        "layer_confidence": 81,
                        "file_path": "backend/main.py",
                        "canonical_id": "main",
                        "source_kind": "code_scan",
                    },
                    {
                        "REQ_ID": "REQ-002",
                        "layer": "Infrastructure",
                        "description": "저장소 연동",
                        "depends_on": [],
                        "layer_confidence": 74,
                        "file_path": "backend/connectors/store.py",
                        "canonical_id": "store",
                        "source_kind": "code_scan",
                    },
                ],
                "layer_order": ["Presentation", "Application", "Domain", "Infrastructure"],
            },
            "sa_phase6": {
                "authz_matrix": [
                    {
                        "req_id": "REQ-001",
                        "allowed_roles": ["admin", "user"],
                        "restriction_level": "Authenticated",
                    }
                ]
            },
            "sa_phase7": {
                "interface_contracts": [
                    {
                        "contract_id": "IF-REQ-001",
                        "layer": "Application",
                        "interface_name": "run_analysis",
                        "input_spec": '{"input": "str"}',
                        "output_spec": '{"result": "dict"}',
                        "error_handling": "에러 시 재시도",
                    }
                ],
                "guardrails": ["REQ-001은 인증 필요"],
            },
            "sa_phase8": {
                "dependency_sources": {
                    "REQ-001": [
                        {
                            "source": "data_flow",
                            "from": "REQ-002",
                            "confidence": 0.71,
                            "tokens": ["analysis_result"],
                            "applied_to_canonical": True,
                        }
                    ]
                }
            },
        }

        artifacts = compile_sa_artifacts(result)

        self.assertIn("flowchart_spec", artifacts)
        self.assertIn("uml_component_spec", artifacts)
        self.assertIn("interface_definition_doc", artifacts)
        self.assertIn("decision_table", artifacts)
        self.assertEqual(artifacts["interface_definition_doc"]["summary"]["contract_count"], 1)
        self.assertTrue(artifacts["decision_table"]["rows"])
        self.assertIn("stages", artifacts["flowchart_spec"])
        self.assertIn("components", artifacts["uml_component_spec"])
        self.assertNotIn("system_diagram_spec", artifacts)

    def test_container_diagram_spec_generated(self):
        result = {
            "sa_phase1": {
                "file_inventory": [
                    {"file": "backend/main.py", "raw_imports": ["fastapi"]},
                    {"file": "backend/transport/ws_handler.py", "raw_imports": ["fastapi"]},
                    {"file": "backend/pipeline/nodes/sa_phase1.py", "raw_imports": ["google.generativeai"]},
                    {"file": "backend/connectors/folder_connector.py", "raw_imports": ["chromadb"]},
                    {"file": "src/App.jsx", "raw_imports": []},
                    {"file": "electron/main.js", "raw_imports": []},
                ],
                "detected_frameworks": [],
            },
            "sa_phase5": {},
        }

        artifacts = compile_sa_artifacts(result)

        self.assertIn("container_diagram_spec", artifacts)
        spec = artifacts["container_diagram_spec"]

        component_ids = {c["id"] for c in spec["components"]}
        self.assertIn("fastapi-server", component_ids)
        self.assertIn("transport-layer", component_ids)
        self.assertIn("sa-pipeline", component_ids)
        self.assertIn("react-ui", component_ids)
        self.assertIn("electron-shell", component_ids)

        external_ids = {e["id"] for e in spec["external_systems"]}
        self.assertIn("users", external_ids)
        self.assertIn("file-system", external_ids)
        self.assertIn("llm-api", external_ids)
        self.assertIn("chromadb", external_ids)

        self.assertTrue(len(spec["connections"]) > 0)
        self.assertTrue(any(conn["source"] == "users" and conn["target"] == "electron-shell" for conn in spec["connections"]))
        self.assertIn("component_count", spec["summary"])
        self.assertEqual(spec["summary"]["component_count"], len(spec["components"]))

    def test_container_diagram_fallback_from_layer_when_file_path_missing(self):
        result = {
            "sa_phase1": {
                "file_inventory": [],
                "detected_frameworks": [],
            },
            "sa_phase5": {
                "mapped_requirements": [
                    {"REQ_ID": "REQ-001", "layer": "Application", "file_path": ""},
                    {"REQ_ID": "REQ-002", "layer": "Domain", "file_path": ""},
                    {"REQ_ID": "REQ-003", "layer": "Infrastructure", "file_path": ""},
                    {"REQ_ID": "REQ-004", "layer": "Presentation", "file_path": ""},
                ]
            },
        }

        artifacts = compile_sa_artifacts(result)
        spec = artifacts["container_diagram_spec"]

        component_ids = {c["id"] for c in spec["components"]}
        self.assertIn("pipeline-orchestrator", component_ids)
        self.assertIn("core-domain", component_ids)
        self.assertIn("data-connectors", component_ids)
        self.assertIn("react-ui", component_ids)
        self.assertGreater(spec["summary"]["component_count"], 0)
        self.assertTrue(any(conn["source"] == "users" for conn in spec["connections"]))


if __name__ == "__main__":
    unittest.main()
