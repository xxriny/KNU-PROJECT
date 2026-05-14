from __future__ import annotations

import pipeline.domain.dev.nodes.branch_pr_orchestrator as branch_pr_orchestrator
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
    assert result["git_action"] == "CREATE_PR"
    assert result["pr_creation"]["mode"] == "draft_only"
    assert result["pr_created"] is False
    assert result["pr_description"]["rtm_coverage"].startswith("100%")
    assert Path(result["pr_drafts"][0]["draft_path"]).is_file()


def test_branch_pr_orchestrator_blocks_before_side_effects_without_integration_pass(tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")
    state = {
        **_base_state(target_repo),
        "develop_main_plan": {
            "branch_strategy": {
                "base_branch": "develop",
                "domain_branches": [{"domain": "backend", "branch": "feature/login-backend"}],
            }
        },
        "backend_domain_gate_result": {"status": "pass"},
        "integration_qa_result": {"status": "failed"},
    }

    result = develop_branch_pr_orchestrator_node(state)["branch_pr_result"]

    branches = subprocess.run(
        ["git", "branch", "--list", "feature/login-backend"],
        cwd=target_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert result["status"] == "blocked"
    assert result["merge_ready"] is False
    assert result["branch_execution"] == []
    assert result["pr_drafts"] == []
    assert "feature/login-backend" not in branches
    assert not (target_repo / "DOCS" / "pr_drafts").exists()


def test_branch_pr_orchestrator_can_create_pr_with_gh_cli(tmp_path: Path, monkeypatch) -> None:
    target_repo = _init_git_repo(tmp_path / "target")
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/example/repo.git"],
        cwd=target_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    calls: list[tuple[list[str], str]] = []

    def fake_run_gh(args: list[str], cwd: str) -> tuple[int, str, str]:
        calls.append((args, cwd))
        if args[:2] == ["auth", "status"]:
            return 0, "Logged in to github.com", ""
        return 0, "https://github.example/pull/1", ""

    monkeypatch.setattr(branch_pr_orchestrator.shutil, "which", lambda name: "gh" if name == "gh" else None)
    monkeypatch.setattr(branch_pr_orchestrator, "_run_gh", fake_run_gh)

    state = {
        **_base_state(target_repo),
        "develop_main_plan": {
            "branch_strategy": {
                "base_branch": "develop",
                "create_pr": True,
                "domain_branches": [{"domain": "backend", "branch": "feature/login-backend"}],
            }
        },
        "changed_files_manifest": ["backend/api/login.py"],
        "backend_domain_gate_result": {"status": "pass"},
        "frontend_domain_gate_result": {"status": "pass"},
        "uiux_domain_gate_result": {"status": "pass"},
        "global_fe_sync_result": {"status": "pass"},
        "integration_qa_result": {"status": "pass", "report": {"rtm_coverage": "100%"}},
    }

    result = develop_branch_pr_orchestrator_node(state)["branch_pr_result"]

    assert result["status"] == "ready"
    assert result["pr_created"] is True
    assert result["pr_creation"]["mode"] == "gh_cli"
    assert result["pr_creation"]["remote_policy"]["status"] == "pass"
    assert result["pr_creation"]["remote_policy"]["provider"] == "github"
    assert result["pr_creation"]["results"][0]["url"] == "https://github.example/pull/1"
    assert result["changed_files_manifest"] == ["backend/api/login.py"]
    assert calls
    assert calls[0][0] == ["auth", "status"]
    pr_calls = [call for call in calls if call[0][:2] == ["pr", "create"]]
    assert pr_calls
    assert "--draft" in pr_calls[0][0]
    assert pr_calls[0][1] == str(target_repo)


def test_branch_pr_orchestrator_can_create_actual_commit_for_manifest_files(tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")
    changed_file = target_repo / "backend" / "api" / "login.py"
    changed_file.parent.mkdir(parents=True)
    changed_file.write_text("def login():\n    return {'ok': True}\n", encoding="utf-8")

    state = {
        **_base_state(target_repo),
        "develop_main_plan": {
            "selected_domains": ["backend"],
            "branch_strategy": {
                "base_branch": "develop",
                "enable_git_commit": True,
                "domain_branches": [{"domain": "backend", "branch": "feature/login-backend"}],
            }
        },
        "changed_files_manifest": [{"domain": "backend", "path": "backend/api/login.py"}],
        "backend_domain_gate_result": {"status": "pass"},
        "integration_qa_result": {"status": "pass"},
    }

    result = develop_branch_pr_orchestrator_node(state)["branch_pr_result"]

    log = subprocess.run(
        ["git", "log", "feature/login-backend", "--oneline", "-1"],
        cwd=target_repo,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    committed_files = subprocess.run(
        ["git", "show", "--name-only", "--format=", "feature/login-backend"],
        cwd=target_repo,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout

    assert result["status"] == "ready"
    assert result["merge_ready"] is True
    assert result["commit_plan"]["enabled"] is True
    assert result["commit_plan"]["mode"] == "actual"
    assert result["commit_plan"]["execution"]["status"] == "committed"
    assert result["commit_plan"]["execution"]["results"][0]["status"] == "committed"
    assert "feat: 사용자 로그인 API와 화면을 추가한다" in log
    assert "backend/api/login.py" in committed_files


def test_branch_pr_orchestrator_blocks_multi_branch_commit_for_unassigned_files(tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")
    changed_file = target_repo / "shared" / "config.json"
    changed_file.parent.mkdir(parents=True)
    changed_file.write_text('{"enabled": true}\n', encoding="utf-8")

    state = {
        **_base_state(target_repo),
        "develop_main_plan": {
            "selected_domains": ["backend", "frontend"],
            "branch_strategy": {
                "base_branch": "develop",
                "enable_git_commit": True,
                "domain_branches": [
                    {"domain": "backend", "branch": "feature/login-backend"},
                    {"domain": "frontend", "branch": "feature/login-frontend"},
                ],
            },
        },
        "changed_files_manifest": ["shared/config.json"],
        "backend_domain_gate_result": {"status": "pass"},
        "frontend_domain_gate_result": {"status": "pass"},
        "integration_qa_result": {"status": "pass"},
    }

    result = develop_branch_pr_orchestrator_node(state)["branch_pr_result"]

    assert result["status"] == "blocked"
    assert result["merge_ready"] is False
    assert result["commit_plan"]["execution"]["status"] == "blocked"
    assert "without a domain" in result["commit_plan"]["execution"]["results"][0]["reason"]


def test_branch_pr_orchestrator_blocks_when_requested_pr_cli_is_unavailable(tmp_path: Path, monkeypatch) -> None:
    target_repo = _init_git_repo(tmp_path / "target")
    monkeypatch.setattr(branch_pr_orchestrator.shutil, "which", lambda name: None)

    state = {
        **_base_state(target_repo),
        "develop_main_plan": {
            "branch_strategy": {
                "base_branch": "develop",
                "create_pr": True,
                "domain_branches": [{"domain": "backend", "branch": "feature/login-backend"}],
            }
        },
        "backend_domain_gate_result": {"status": "pass"},
        "frontend_domain_gate_result": {"status": "pass"},
        "uiux_domain_gate_result": {"status": "pass"},
        "global_fe_sync_result": {"status": "pass"},
        "integration_qa_result": {"status": "pass"},
    }

    result = develop_branch_pr_orchestrator_node(state)["branch_pr_result"]

    assert result["status"] == "blocked"
    assert result["merge_ready"] is False
    assert result["pr_created"] is False
    assert result["pr_creation"]["results"][0]["status"] == "error"
    assert "GitHub CLI" in result["pr_creation"]["results"][0]["reason"]


def test_branch_pr_orchestrator_blocks_remote_pr_without_origin_remote(tmp_path: Path, monkeypatch) -> None:
    target_repo = _init_git_repo(tmp_path / "target")
    calls: list[list[str]] = []

    def fake_run_gh(args: list[str], cwd: str) -> tuple[int, str, str]:
        calls.append(args)
        if args[:2] == ["auth", "status"]:
            return 0, "Logged in to github.com", ""
        return 0, "https://github.example/pull/1", ""

    monkeypatch.setattr(branch_pr_orchestrator.shutil, "which", lambda name: "gh" if name == "gh" else None)
    monkeypatch.setattr(branch_pr_orchestrator, "_run_gh", fake_run_gh)

    state = {
        **_base_state(target_repo),
        "develop_main_plan": {
            "branch_strategy": {
                "base_branch": "develop",
                "create_pr": True,
                "domain_branches": [{"domain": "backend", "branch": "feature/login-backend"}],
            }
        },
        "backend_domain_gate_result": {"status": "pass"},
        "frontend_domain_gate_result": {"status": "pass"},
        "uiux_domain_gate_result": {"status": "pass"},
        "global_fe_sync_result": {"status": "pass"},
        "integration_qa_result": {"status": "pass"},
    }

    result = develop_branch_pr_orchestrator_node(state)["branch_pr_result"]

    assert result["status"] == "blocked"
    assert result["merge_ready"] is False
    assert result["pr_creation"]["remote_policy"]["status"] == "fail"
    assert result["pr_creation"]["remote_policy"]["remote_url"] == ""
    assert result["pr_creation"]["results"][0]["status"] == "error"
    assert "remote_repository" in result["pr_creation"]["results"][0]["reason"]
    assert ["auth", "status"] in calls
    assert not [args for args in calls if args[:2] == ["pr", "create"]]
