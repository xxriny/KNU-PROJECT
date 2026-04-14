import os
import sys
import unittest


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.domain.sa.nodes.sa_phase5 import _build_reverse_module_mapping


class SAPhase5MappingTests(unittest.TestCase):
    def test_reverse_mapping_uses_multiple_layers_from_evidence(self):
        system_scan = {
            "detected_frameworks": ["React", "FastAPI"],
            "sample_functions": [
                {
                    "file": "src/components/ChatPanel.jsx",
                    "func_name": "renderChatPanel",
                    "docstring": "UI 화면 렌더링과 사용자 입력 처리",
                    "lang": "javascript",
                },
                {
                    "file": "backend/pipeline/ast_scanner.py",
                    "func_name": "parse_source_graph",
                    "docstring": "코드 구조를 파싱하고 시맨틱 그래프를 생성",
                    "lang": "python",
                },
                {
                    "file": "backend/chroma_client.py",
                    "func_name": "save_vectors",
                    "docstring": "vector storage client to persist embeddings",
                    "lang": "python",
                },
            ],
            "key_modules": [],
        }

        mapped = _build_reverse_module_mapping(system_scan)
        layers = {item["layer"] for item in mapped}

        self.assertIn("Presentation", layers)
        self.assertIn("Domain", layers)
        self.assertIn("Infrastructure", layers)
        for item in mapped:
            self.assertIn("layer_confidence", item)
            self.assertIn("layer_evidence", item)
            self.assertGreaterEqual(item["layer_confidence"], 35)
            self.assertTrue(item["mapping_reason"])

    def test_framework_hints_are_scoped_per_module(self):
        system_scan = {
            "detected_frameworks": ["React", "FastAPI"],
            "framework_evidence": [
                {"framework": "React", "file": "src/App.jsx", "reason": "dependencies.react 발견"},
                {"framework": "FastAPI", "file": "backend/main.py", "reason": "FastAPI 엔트리포인트"},
            ],
            "sample_functions": [
                {
                    "file": "backend/main.py",
                    "func_name": "create_app",
                    "docstring": "FastAPI application startup and route registration",
                    "lang": "python",
                },
                {
                    "file": "src/App.jsx",
                    "func_name": "App",
                    "docstring": "React root component for the desktop shell",
                    "lang": "javascript",
                },
            ],
            "key_modules": [],
        }

        mapped = _build_reverse_module_mapping(system_scan)
        backend_main = next(item for item in mapped if "backend/main.py" in item["description"])
        frontend_app = next(item for item in mapped if "src/App.jsx" in item["description"])

        self.assertEqual(backend_main["layer"], "Application")
        self.assertNotEqual(backend_main["layer"], "Presentation")
        self.assertEqual(frontend_app["layer"], "Presentation")

    def test_file_inventory_drives_reverse_mapping_and_dedupes_key_modules(self):
        system_scan = {
            "detected_frameworks": ["FastAPI"],
            "framework_evidence": [{"framework": "FastAPI", "file": "backend/main.py", "reason": "entrypoint"}],
            "sample_functions": [
                {"file": "backend/main.py", "func_name": "create_app", "docstring": "app startup", "lang": "python"},
                {"file": "backend/orchestration/pipeline_runner.py", "func_name": "run_analysis", "docstring": "pipeline execution", "lang": "python"},
            ],
            "file_inventory": [
                {"file": "backend/main.py", "lang": "python", "function_count": 2, "internal_imports": ["backend/orchestration/pipeline_runner.py"], "raw_imports": ["orchestration.pipeline_runner"], "is_entrypoint": True},
                {"file": "backend/orchestration/pipeline_runner.py", "lang": "python", "function_count": 3, "internal_imports": [], "raw_imports": [], "is_entrypoint": False},
                {"file": "backend/pipeline/utils.py", "lang": "python", "function_count": 1, "internal_imports": [], "raw_imports": [], "is_entrypoint": False},
            ],
            "key_modules": ["backend/orchestration/pipeline_runner.py (파이프라인 실행 관리)"],
        }

        mapped = _build_reverse_module_mapping(system_scan)

        self.assertEqual(len(mapped), 3)
        self.assertTrue(all(item.get("file_path") for item in mapped))
        self.assertTrue(all(item.get("canonical_id") for item in mapped))
        self.assertTrue(all(item.get("source_kind") for item in mapped))
        pipeline_items = [item for item in mapped if item["file_path"] == "backend/orchestration/pipeline_runner.py"]
        self.assertEqual(len(pipeline_items), 1)


if __name__ == "__main__":
    unittest.main()
