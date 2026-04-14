import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from transport.rest_handler import _allowed_project_roots
from pipeline.orchestration.facade import get_analysis_pipeline, get_idea_pipeline, get_revision_pipeline
from pipeline.orchestration.graph import _check_status
from pipeline.core.action_type import normalize_action_type
from orchestration.pipeline_runner import analysis_pipeline_type


class PipelineSetupTests(unittest.TestCase):
    def test_action_type_normalization_is_shared(self):
        self.assertEqual(normalize_action_type(" update "), "UPDATE")
        self.assertEqual(normalize_action_type("invalid"), "CREATE")
        self.assertEqual(analysis_pipeline_type("invalid"), "analysis_create")

    def test_pipeline_builders_return_compiled_graphs(self):
        self.assertIsNotNone(get_analysis_pipeline())
        self.assertIsNotNone(get_revision_pipeline())
        self.assertIsNotNone(get_idea_pipeline())

    def test_sa_fail_does_not_terminate_pipeline(self):
        route = _check_status({"sa_phase3": {"status": "Fail"}})

        self.assertEqual(route, "continue")

    def test_sa_error_still_terminates_pipeline(self):
        route = _check_status({"sa_phase3": {"status": "Error"}})

        self.assertEqual(route, "error")

    def test_config_exposes_available_models(self):
        with TestClient(app) as client:
            response = client.get("/api/config")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("available_models", payload)
        self.assertIn(payload["default_model"], payload["available_models"])

    def test_read_file_requires_scanned_root(self):
        _allowed_project_roots.clear()
        with tempfile.TemporaryDirectory() as temp_dir:
            allowed_file = os.path.join(temp_dir, "allowed.txt")
            with open(allowed_file, "w", encoding="utf-8") as handle:
                handle.write("inside")

            with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as outside_handle:
                outside_handle.write("outside")
                outside_file = outside_handle.name

            try:
                with TestClient(app) as client:
                    blocked = client.post("/api/read-file", json={"path": allowed_file}).json()
                    self.assertEqual(blocked["status"], "error")

                    scanned = client.post("/api/scan-folder", json={"path": temp_dir}).json()
                    self.assertEqual(scanned["status"], "ok")

                    allowed = client.post("/api/read-file", json={"path": allowed_file}).json()
                    self.assertEqual(allowed["status"], "ok")
                    self.assertEqual(allowed["content"], "inside")

                    denied = client.post("/api/read-file", json={"path": outside_file}).json()
                    self.assertEqual(denied["status"], "error")
            finally:
                os.unlink(outside_file)
                _allowed_project_roots.clear()

    def test_read_file_requires_existing_file(self):
        with TestClient(app) as client:
            response = client.post("/api/read-file", json={"path": "C:/tmp/not_exists.txt"}).json()

        self.assertEqual(response["status"], "error")

    def test_delete_session_uses_run_id_and_exact_project_state_path(self):
        with patch("transport.rest_handler.delete_session_files", return_value=1) as delete_files_mock, \
             patch("transport.rest_handler.delete_exact_file", return_value=True) as delete_exact_mock, \
             patch("pipeline.core.chroma_client.delete_by_run_id", return_value=2):
            with TestClient(app) as client:
                response = client.request(
                    "DELETE",
                    "/api/session/20260326_214400",
                    json={"project_state_path": "C:/tmp/20260326_214400_Test_PROJECT_STATE.md"},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["files_deleted"], 2)
        self.assertEqual(payload["documents_deleted"], 2)
        delete_files_mock.assert_called_once_with("20260326_214400")
        delete_exact_mock.assert_called_once_with("C:/tmp/20260326_214400_Test_PROJECT_STATE.md")


if __name__ == "__main__":
    unittest.main()
