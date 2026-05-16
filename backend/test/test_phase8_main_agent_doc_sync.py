"""
Phase 5 (main_agent + Doc Sync): 통합 검증
- task_coordinator: create/list/update/execute 검증
- doc_sync: 해시 비교, 변경 감지 검증
- REST endpoint 등록 확인
- 프론트엔드 파일 존재 확인
"""

import os
import sys
import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(os.path.dirname(BACKEND_DIR), "src")
sys.path.insert(0, BACKEND_DIR)


# ── Task Coordinator ──────────────────────────────────────────────────────────

class TestTaskCoordinator:
    def test_import_task_coordinator(self):
        from pipeline.domain.agile.task_coordinator import (
            create_task, list_tasks, get_task, update_task_status,
            execute_approved_task, init_tasks_db,
        )

    def test_create_and_get_task(self):
        from pipeline.domain.agile.task_coordinator import create_task, get_task, init_tasks_db
        init_tasks_db()
        task = create_task(
            task_type="verify_sa",
            title="SA 검증 태스크",
            description="SA 결과물 일관성 검증",
            payload={"sa_data": {"components": [], "apis": [], "tables": []}},
            created_by="test_user",
        )
        assert task["id"]
        assert task["status"] == "pending"
        assert task["task_type"] == "verify_sa"

        fetched = get_task(task["id"])
        assert fetched is not None
        assert fetched["title"] == "SA 검증 태스크"

    def test_list_tasks(self):
        from pipeline.domain.agile.task_coordinator import create_task, list_tasks, init_tasks_db
        init_tasks_db()
        create_task("verify_sa", "테스트 리스트 태스크", created_by="tester")
        tasks = list_tasks()
        assert isinstance(tasks, list)
        assert len(tasks) > 0

    def test_update_task_status(self):
        from pipeline.domain.agile.task_coordinator import create_task, update_task_status, init_tasks_db
        init_tasks_db()
        task = create_task("doc_sync", "문서 동기화", created_by="pm")
        updated = update_task_status(task["id"], "approved", reviewed_by="pm_user")
        assert updated["status"] == "approved"
        assert updated["reviewed_by"] == "pm_user"

    def test_update_nonexistent_task(self):
        from pipeline.domain.agile.task_coordinator import update_task_status, init_tasks_db
        init_tasks_db()
        result = update_task_status("nonexistent-id-000", "approved")
        assert result is None

    def test_execute_approved_task_verify_sa(self):
        from pipeline.domain.agile.task_coordinator import execute_approved_task
        task = {
            "task_type": "verify_sa",
            "payload": {"sa_data": {"components": [], "apis": [], "tables": []}, "api_key": ""},
        }
        result_str = execute_approved_task(task)
        import json
        result = json.loads(result_str)
        assert "coherence_score" in result
        assert "passed" in result

    def test_execute_approved_task_import_issues(self):
        from pipeline.domain.agile.task_coordinator import execute_approved_task
        import json
        task = {
            "task_type": "import_issues",
            "payload": {"issues": [{"title": "bug1"}, {"title": "bug2"}]},
        }
        result_str = execute_approved_task(task)
        result = json.loads(result_str)
        assert result.get("imported") == 2

    def test_list_tasks_by_status(self):
        from pipeline.domain.agile.task_coordinator import create_task, list_tasks, update_task_status, init_tasks_db
        init_tasks_db()
        task = create_task("verify_sa", "상태 필터 테스트")
        update_task_status(task["id"], "rejected")
        rejected_tasks = list_tasks(status="rejected")
        assert any(t["id"] == task["id"] for t in rejected_tasks)


# ── Doc Sync ──────────────────────────────────────────────────────────────────

class TestDocSync:
    def test_import_doc_sync(self):
        from pipeline.domain.agile.nodes.doc_sync import sync_docs, _compute_hash

    def test_hash_consistency(self):
        from pipeline.domain.agile.nodes.doc_sync import _compute_hash
        data = {"components": [{"name": "A"}], "apis": [], "tables": []}
        h1 = _compute_hash(data)
        h2 = _compute_hash(data)
        assert h1 == h2
        assert len(h1) == 16

    def test_hash_changes_with_data(self):
        from pipeline.domain.agile.nodes.doc_sync import _compute_hash
        h1 = _compute_hash({"components": []})
        h2 = _compute_hash({"components": [{"name": "New"}]})
        assert h1 != h2

    def test_sync_skipped_same_hash(self):
        from pipeline.domain.agile.nodes.doc_sync import sync_docs, _compute_hash
        result_data = {"sa_output": {"data": {"components": [], "apis": [], "tables": []}}}
        sa = result_data["sa_output"]["data"]
        h = _compute_hash(sa)
        result = sync_docs(
            result_data=result_data,
            github_token="",
            owner="",
            repo="",
            previous_hash=h,
        )
        assert result["synced"] is False
        assert result["action"] == "skipped"
        assert "해시 동일" in result["message"] or "변경사항" in result["message"]

    def test_sync_skipped_no_github_config(self):
        from pipeline.domain.agile.nodes.doc_sync import sync_docs
        result_data = {"sa_output": {"data": {"components": [{"name": "New"}], "apis": [], "tables": []}}}
        result = sync_docs(
            result_data=result_data,
            github_token="",
            owner="",
            repo="",
            previous_hash="different-hash",
        )
        assert result["synced"] is False
        assert result["action"] == "skipped"

    def test_sync_returns_current_hash(self):
        from pipeline.domain.agile.nodes.doc_sync import sync_docs, _compute_hash
        result_data = {"sa_output": {"data": {"components": [{"name": "Comp"}], "apis": [], "tables": []}}}
        result = sync_docs(result_data=result_data, github_token="", owner="", repo="")
        assert len(result["hash"]) == 16


# ── REST Endpoints ────────────────────────────────────────────────────────────

class TestPhase5RESTEndpoints:
    def test_task_endpoints_registered(self):
        from transport.rest_handler import rest_router
        paths = [r.path for r in rest_router.routes]
        assert "/api/tasks" in paths
        assert "/api/tasks/{task_id}" in paths
        assert "/api/doc-sync" in paths
        assert "/api/github/issues/import" in paths

    def test_task_create_request_model(self):
        from transport.rest_handler import TaskCreateRequest
        req = TaskCreateRequest(task_type="verify_sa", title="테스트")
        assert req.task_type == "verify_sa"
        assert req.payload == {}

    def test_task_update_request_model(self):
        from transport.rest_handler import TaskUpdateRequest
        req = TaskUpdateRequest(status="approved")
        assert req.status == "approved"
        assert req.reviewed_by == ""

    def test_doc_sync_request_model(self):
        from transport.rest_handler import DocSyncRequest
        req = DocSyncRequest(result_data={}, github_token="tok", owner="alice", repo="myrepo")
        assert req.page_title == "SA 설계 문서"
        assert req.previous_hash == ""


# ── Frontend Files ────────────────────────────────────────────────────────────

class TestPhase5FrontendFiles:
    def _fe(self, *parts):
        return os.path.join(FRONTEND_DIR, *parts)

    def test_task_approval_panel_exists(self):
        path = self._fe("components", "resultViewer", "TaskApprovalPanel.jsx")
        assert os.path.exists(path), f"TaskApprovalPanel.jsx 없음: {path}"

    def test_result_viewer_has_task_approval(self):
        path = self._fe("components", "ResultViewer.jsx")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "TaskApprovalPanel" in content
        assert "task_approval" in content

    def test_ui_constants_has_task_approval(self):
        path = self._fe("constants", "uiConstants.js")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "task_approval" in content
        assert "ClipboardList" in content

    def test_task_approval_panel_content(self):
        path = self._fe("components", "resultViewer", "TaskApprovalPanel.jsx")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "/api/tasks" in content
        assert "isPM" in content or "userRole" in content
        assert "approved" in content
        assert "rejected" in content

    def test_task_approval_has_github_import(self):
        path = self._fe("components", "resultViewer", "TaskApprovalPanel.jsx")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "/api/github/issues/import" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
