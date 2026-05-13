from __future__ import annotations

from pipeline.domain.dev.test.fixtures import *


def test_branch_pr_orchestrator_uses_source_dir(tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")
    outside_repo = _init_git_repo(tmp_path / "outside")

    state = {
        **_base_state(target_repo),
        "develop_main_plan": {
            "branch_strategy": {
                "base_branch": "develop",
                "domain_branches": [{"domain": "backend", "branch": "feature/login-backend"}],
            }
        },
        "backend_domain_gate_result": {"status": "pass"},
        "frontend_domain_gate_result": {"status": "pass"},
        "uiux_domain_gate_result": {"status": "pass"},
        "global_fe_sync_result": {"status": "pass"},
        "integration_qa_result": {"status": "pass"}, # 통합 QA 통과 전제
    }

    previous_cwd = Path.cwd()
    try:
        # The orchestrator must operate on source_dir, not the process cwd.
        import os

        os.chdir(outside_repo)
        result = develop_branch_pr_orchestrator_node(state)["branch_pr_result"]
    finally:
        os.chdir(previous_cwd)

    branches = subprocess.run(
        ["git", "branch", "--list", "feature/login-backend"],
        cwd=target_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    outside_branches = subprocess.run(
        ["git", "branch", "--list", "feature/login-backend"],
        cwd=outside_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert "feature/login-backend" in branches
    assert "feature/login-backend" not in outside_branches
    assert result["merge_ready"] is True
    assert Path(result["pr_drafts"][0]["draft_path"]).is_file()
