import os
import sys
import asyncio
import hashlib
import hmac
import json
import subprocess
import types


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from pipeline.domain.dev_tracking.test.dev_tracking_test_utils import (
    _fake_user,
    _github_pr_payload,
    _valid_payload,
)

# author: xxrin
# 원본 대형 Dev Tracking 테스트 파일에서 기능 단위로 분리한 테스트 모듈이다.

def test_dev_task_planner_valid_payload_creates_pr_context():
    from pipeline.domain.dev_tracking.nodes import dev_task_planner

    result = dev_task_planner(_valid_payload())

    assert result["status"] == "PASS"
    assert result["dev_tracking_next_action"] == "branch_fetcher"
    assert result["pr_context"]["owner"] == "xxrin"
    assert result["pr_context"]["repo"] == "navigator"
    assert result["pr_context"]["pr_number"] == 1
    assert result["pr_context"]["branch_name"] == "feature/dev-tracking"

def test_dev_task_planner_invalid_payload_reports_missing_head_sha():
    from pipeline.domain.dev_tracking.nodes import dev_task_planner

    payload = _valid_payload()
    payload["pull_request"]["head_sha"] = ""

    result = dev_task_planner(payload)

    assert result["status"] == "FAIL"
    assert result["error_type"] == "INVALID_WEBHOOK_PAYLOAD"
    assert result["dev_tracking_next_action"] == "blocked"
    assert any("pull_request.head_sha" in item for item in result["errors"])

def test_code_inventory_builder_scans_temp_project(tmp_path):
    from pipeline.domain.dev_tracking.nodes import code_inventory_builder

    api_dir = tmp_path / "app" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "users.py").write_text(
        "def list_users():\n"
        "    return []\n",
        encoding="utf-8",
    )
    component_dir = tmp_path / "src" / "components"
    component_dir.mkdir(parents=True)
    (component_dir / "UserList.jsx").write_text(
        "export function UserList() {\n"
        "  return null;\n"
        "}\n",
        encoding="utf-8",
    )

    result = code_inventory_builder({"source_dir": str(tmp_path)})

    assert result["status"] == "PASS"
    assert result["dev_tracking_next_action"] == "forensic_profiler"
    assert result["code_inventory"]["summary"]["file_count"] == 2
    assert result["code_inventory"]["summary"]["symbol_count"] >= 2

def test_pr_inventory_prioritizes_changed_files():
    from pipeline.domain.dev_tracking.nodes import _prioritize_inventory_for_pr

    inventory = {
        "files": [
            {"file": "src/unchanged.py", "internal_imports": []},
            {"file": "src/changed.py", "internal_imports": ["src/helper.py"]},
            {"file": "src/helper.py", "internal_imports": []},
        ],
        "symbols_by_file": {
            "src/changed.py": [{"name": "changed"}],
            "src/helper.py": [{"name": "helper"}],
            "src/unchanged.py": [{"name": "unchanged"}],
        },
        "summary": {"file_count": 3},
    }

    prioritized = _prioritize_inventory_for_pr(inventory, {"src/changed.py"}, max_files=3)

    assert prioritized["files"][0]["file"] == "src/changed.py"
    assert prioritized["files"][1]["file"] == "src/helper.py"
    assert prioritized["summary"]["changed_file_count"] == 1
    assert "src/changed.py" in prioritized["symbols_by_file"]

def test_split_text_chunks_keeps_chunks_under_limit():
    from pipeline.domain.dev_tracking.nodes import _split_text_chunks

    chunks = _split_text_chunks("\n".join(["x" * 20 for _ in range(10)]), 50)

    assert len(chunks) > 1
    assert all(len(chunk) <= 50 for chunk in chunks)
