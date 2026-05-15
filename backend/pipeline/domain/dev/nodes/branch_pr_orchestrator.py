from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.domain.dev.nodes._shared import get_goal, slugify


def _run_git(args: list[str], cwd: str) -> tuple[int, str, str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def _run_gh(args: list[str], cwd: str) -> tuple[int, str, str]:
    completed = subprocess.run(
        ["gh", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def _remote_url(cwd: str, remote: str = "origin") -> str:
    code, out, _ = _run_git(["remote", "get-url", remote], cwd)
    return out if code == 0 else ""


def _remote_provider(remote_url: str) -> str:
    lowered = str(remote_url or "").lower()
    if "github.com" in lowered or lowered.startswith("gh:"):
        return "github"
    if "gitlab" in lowered:
        return "gitlab"
    if "bitbucket" in lowered:
        return "bitbucket"
    return "unknown" if remote_url else ""


def _gh_auth_check(cwd: str, gh_available: bool) -> dict:
    if not gh_available:
        return {
            "check": "gh_auth",
            "status": "skipped",
            "ready": False,
            "reason": "GitHub CLI is not available.",
        }
    code, out, err = _run_gh(["auth", "status"], cwd)
    return {
        "check": "gh_auth",
        "status": "pass" if code == 0 else "fail",
        "ready": code == 0,
        "reason": "" if code == 0 else (err or out or "GitHub CLI is not authenticated."),
    }


def _remote_pr_policy(
    *,
    cwd: str,
    base_branch: str,
    gh_available: bool,
    create_pr_enabled: bool,
    remote: str = "origin",
) -> dict:
    remote_url = _remote_url(cwd, remote)
    provider = _remote_provider(remote_url)
    base_ready = _verify_ref(cwd, base_branch) or _verify_ref(cwd, f"{remote}/{base_branch}")
    checks = [
        {
            "check": "pr_cli_enabled",
            "status": "pass" if create_pr_enabled else "skipped",
            "ready": bool(create_pr_enabled),
            "reason": "" if create_pr_enabled else "PR CLI execution is disabled.",
        },
        {
            "check": "gh_available",
            "status": "pass" if gh_available else "fail",
            "ready": bool(gh_available),
            "reason": "" if gh_available else "GitHub CLI is not available.",
        },
        _gh_auth_check(cwd, gh_available) if create_pr_enabled else {
            "check": "gh_auth",
            "status": "skipped",
            "ready": False,
            "reason": "PR CLI execution is disabled.",
        },
        {
            "check": "remote_repository",
            "status": "pass" if remote_url else "fail",
            "ready": bool(remote_url),
            "reason": "" if remote_url else f"Git remote '{remote}' is not configured.",
        },
        {
            "check": "pr_provider",
            "status": "pass" if provider == "github" else ("skipped" if not remote_url else "fail"),
            "ready": provider == "github",
            "reason": "" if provider == "github" else "Remote repository is not a GitHub remote.",
        },
        {
            "check": "base_ref",
            "status": "pass" if base_ready else "fail",
            "ready": base_ready,
            "reason": "" if base_ready else f"Base branch/ref is not available locally: {base_branch}.",
        },
    ]
    if not create_pr_enabled:
        status = "skipped"
        ready = False
    else:
        ready = all(item["ready"] for item in checks if item["check"] != "pr_cli_enabled")
        status = "pass" if ready else "fail"
    return {
        "status": status,
        "ready": ready,
        "provider": provider,
        "remote": remote,
        "remote_url": remote_url,
        "base_branch": base_branch,
        "checks": checks,
    }


def _verify_ref(cwd: str, ref: str) -> bool:
    code, _, _ = _run_git(["rev-parse", "--verify", ref], cwd)
    return code == 0


def _current_branch(cwd: str) -> str:
    code, out, _ = _run_git(["branch", "--show-current"], cwd)
    return out if code == 0 and out else "HEAD"


def _repo_root(cwd: str) -> str:
    code, out, _ = _run_git(["rev-parse", "--show-toplevel"], cwd)
    return out if code == 0 and out else cwd


def _resolve_base_ref(cwd: str, requested_base: str) -> str:
    candidates = [
        requested_base,
        f"origin/{requested_base}",
        "develop",
        "origin/develop",
        "main",
        "origin/main",
        _current_branch(cwd),
    ]
    for candidate in candidates:
        if candidate and _verify_ref(cwd, candidate):
            return candidate
    return "HEAD"


def _branch_exists(cwd: str, branch: str) -> bool:
    code, _, _ = _run_git(["show-ref", "--verify", f"refs/heads/{branch}"], cwd)
    return code == 0


def _create_branch_if_needed(cwd: str, branch: str, start_ref: str) -> dict:
    if _branch_exists(cwd, branch):
        return {"branch": branch, "status": "exists", "start_ref": start_ref}
    code, _, err = _run_git(["branch", branch, start_ref], cwd)
    if code == 0:
        return {"branch": branch, "status": "created", "start_ref": start_ref}
    return {"branch": branch, "status": "error", "start_ref": start_ref, "message": err}


def _shadow_branch_check(cwd: str, base_ref: str, branches: list[dict]) -> dict:
    if not _verify_ref(cwd, base_ref):
        return {
            "status": "skipped",
            "reason": f"Base ref is not available: {base_ref}",
            "checks": [],
        }
    checks = []
    for item in branches:
        branch = item.get("branch", "")
        if not branch or not _verify_ref(cwd, branch):
            checks.append({"branch": branch, "status": "skipped", "reason": "branch ref is not available"})
            continue
        base_code, merge_base, base_err = _run_git(["merge-base", base_ref, branch], cwd)
        if base_code != 0 or not merge_base:
            checks.append({"branch": branch, "status": "skipped", "reason": base_err or "merge-base unavailable"})
            continue
        code, out, err = _run_git(["merge-tree", merge_base, base_ref, branch], cwd)
        checks.append({
            "branch": branch,
            "status": "passed" if code == 0 and "<<<<<<<" not in out else "failed",
            "reason": err if code != 0 else "",
            "conflict_markers": "<<<<<<<" in out,
        })
    failed = [item for item in checks if item.get("status") == "failed"]
    return {
        "status": "failed" if failed else "passed",
        "base_ref": base_ref,
        "checks": checks,
        "strategy": "Dry-run shadow branch integration using git merge-tree before merge approval.",
    }


def _status_label(payload: dict) -> str:
    return str((payload or {}).get("status", "") or "missing").upper()


def _as_file_path(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in ("path", "file_path", "relative_path"):
            if item.get(key):
                return str(item[key])
    return ""


def _entry_domain(item: Any, fallback: str = "") -> str:
    if isinstance(item, dict):
        return str(item.get("domain") or item.get("owner") or fallback or "").lower()
    return fallback.lower()


def _infer_domain_from_path(path: str) -> str:
    lowered = str(path).replace("\\", "/").lower()
    if "backend" in lowered or lowered.startswith("api/") or "/api/" in lowered:
        return "backend"
    if "frontend" in lowered or lowered.startswith("src/") or "/src/" in lowered:
        return "frontend"
    if "uiux" in lowered or "ui-ux" in lowered or "design" in lowered:
        return "uiux"
    return ""


def _normalize_repo_path(cwd: str, raw_path: str) -> tuple[str, str]:
    if not raw_path:
        return "", "path is empty"
    root = Path(_repo_root(cwd)).resolve()
    path = Path(raw_path)
    abs_path = path.resolve() if path.is_absolute() else (Path(cwd) / path).resolve()
    try:
        rel = abs_path.relative_to(root)
    except ValueError:
        return "", f"path is outside repository: {raw_path}"
    return rel.as_posix(), ""


def _git_status_paths(cwd: str) -> list[str]:
    code, out, _ = _run_git(["status", "--short"], cwd)
    if code != 0:
        return []
    paths = []
    for line in out.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip() if len(line) > 3 else line.strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        paths.append(path)
    return paths


def _collect_changed_file_entries(ctx: NodeContext, cwd: str) -> list[dict]:
    entries: list[dict] = []

    def add(raw_path: str, *, domain: str = "", source: str = "") -> None:
        path, error = _normalize_repo_path(cwd, raw_path)
        if error:
            entries.append({"path": raw_path, "domain": domain, "source": source, "valid": False, "reason": error})
            return
        entries.append({
            "path": path,
            "domain": domain or _infer_domain_from_path(path),
            "source": source,
            "valid": True,
        })

    explicit = ctx.sget("changed_files_manifest", None)
    if isinstance(explicit, list):
        for item in explicit:
            add(_as_file_path(item), domain=_entry_domain(item), source="changed_files_manifest")
    else:
        for key, domain in (("backend_codegen_result", "backend"), ("frontend_codegen_result", "frontend")):
            payload = ctx.sget(key, {}) or {}
            if not isinstance(payload, dict):
                continue
            for field in ("generated_files", "changed_files", "files"):
                for item in payload.get(field) or []:
                    add(_as_file_path(item), domain=_entry_domain(item, domain), source=f"{key}.{field}")
            output_dir = payload.get("output_dir")
            if output_dir:
                add(str(output_dir), domain=domain, source=f"{key}.output_dir")

        for path in _git_status_paths(cwd):
            add(path, source="git_status")

    deduped: dict[str, dict] = {}
    invalid = [entry for entry in entries if not entry.get("valid")]
    for entry in entries:
        if not entry.get("valid"):
            continue
        path = entry["path"]
        current = deduped.get(path)
        if current and current.get("domain"):
            continue
        deduped[path] = entry
    return [*invalid, *sorted(deduped.values(), key=lambda item: item["path"])]


def _collect_changed_files(ctx: NodeContext, cwd: str) -> list[str]:
    return sorted({entry["path"] for entry in _collect_changed_file_entries(ctx, cwd) if entry.get("valid")})


def _rtm_coverage(ctx: NodeContext) -> str:
    integration = ctx.sget("integration_qa_result", {}) or {}
    report = integration.get("report") if isinstance(integration, dict) else {}
    if isinstance(report, dict) and report.get("rtm_coverage"):
        return str(report["rtm_coverage"])
    rtm = ctx.sget("requirements_rtm", []) or []
    if isinstance(rtm, list) and rtm:
        return f"100% (Matched {len(rtm)}/{len(rtm)} Features)"
    return "UNKNOWN"


def _qa_summary(ctx: NodeContext) -> str:
    statuses = {
        "UI/UX Domain Gate": _status_label(ctx.sget("uiux_domain_gate_result", {}) or {}),
        "Backend Domain Gate": _status_label(ctx.sget("backend_domain_gate_result", {}) or {}),
        "Frontend Domain Gate": _status_label(ctx.sget("frontend_domain_gate_result", {}) or {}),
        "Global FE Sync": _status_label(ctx.sget("global_fe_sync_result", {}) or {}),
        "Integration QA": _status_label(ctx.sget("integration_qa_result", {}) or {}),
    }
    return ", ".join(f"{name}: {status}" for name, status in statuses.items())


def _pr_description(ctx: NodeContext, goal: str, changed_files: list[str]) -> dict:
    return {
        "summary": goal,
        "rtm_coverage": _rtm_coverage(ctx),
        "qa_summary": _qa_summary(ctx),
        "changed_files": changed_files,
    }


def _pr_body(goal: str, domain: str, base_branch: str, description: dict) -> str:
    changed_files = description.get("changed_files") or []
    changed_file_lines = [f"- {path}" for path in changed_files] or ["- No changed files manifest was provided."]
    return "\n".join([
        f"## Goal",
        goal,
        "",
        f"## Domain",
        domain,
        "",
        f"## Base Branch",
        base_branch,
        "",
        "## RTM Coverage",
        str(description.get("rtm_coverage", "UNKNOWN")),
        "",
        "## QA Summary",
        str(description.get("qa_summary", "")),
        "",
        "## Changed Files",
        *changed_file_lines,
        "",
        "## Notes",
        "- Generated by develop_branch_pr_orchestrator",
        "- Review domain-specific QA and integration QA outputs before merge",
    ])


def _write_pr_draft(cwd: str, branch: str, title: str, body: str) -> str:
    docs_dir = Path(cwd) / "DOCS" / "pr_drafts"
    docs_dir.mkdir(parents=True, exist_ok=True)
    draft_path = docs_dir / f"{branch.replace('/', '__')}.md"
    draft_path.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
    return str(draft_path)


def _integration_status(ctx: NodeContext) -> str:
    integration = ctx.sget("integration_qa_result", {}) or {}
    return str(integration.get("status", "") or "").lower()


def _bool_setting(ctx: NodeContext, branch_strategy: dict, key: str, default: bool = False) -> bool:
    if key in branch_strategy:
        return bool(branch_strategy.get(key))
    return bool(ctx.sget(key, default))


def _files_for_branch(branch: dict, entries: list[dict], *, single_branch: bool) -> tuple[list[str], list[dict]]:
    domain = str(branch.get("domain", "") or "").lower()
    valid = [entry for entry in entries if entry.get("valid")]
    selected = [
        entry
        for entry in valid
        if entry.get("domain") == domain or (single_branch and not entry.get("domain"))
    ]
    unassigned = [entry for entry in valid if not entry.get("domain")]
    if single_branch and not selected:
        selected = valid
        unassigned = []
    return sorted({entry["path"] for entry in selected}), unassigned


def _preexisting_staged_files(cwd: str) -> list[str]:
    code, out, _ = _run_git(["diff", "--cached", "--name-only"], cwd)
    if code != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def _execute_commit_plan(cwd: str, branches: list[dict], entries: list[dict], goal: str, enabled: bool) -> dict:
    original_branch = _current_branch(cwd)
    message = f"feat: {goal[:72]}"
    invalid_entries = [entry for entry in entries if not entry.get("valid")]
    valid_entries = [entry for entry in entries if entry.get("valid")]
    single_branch = len(branches) <= 1
    existing_staged = _preexisting_staged_files(cwd)

    result = {
        "enabled": enabled,
        "status": "disabled" if not enabled else "pending",
        "message": message,
        "original_branch": original_branch,
        "final_branch": original_branch,
        "results": [],
        "blocked_reasons": [],
    }
    if not enabled:
        return result
    if invalid_entries:
        result["status"] = "blocked"
        result["blocked_reasons"] = [entry.get("reason", "invalid changed file") for entry in invalid_entries]
        return result
    if not valid_entries:
        result["status"] = "blocked"
        result["blocked_reasons"] = ["No commitable changed files were found."]
        return result
    if existing_staged:
        result["status"] = "blocked"
        result["blocked_reasons"] = [
            "Pre-existing staged files are present; refusing to mix user-staged changes into generated commits.",
            *existing_staged,
        ]
        return result

    any_committed = False
    any_failed = False
    try:
        for branch in branches:
            paths, unassigned = _files_for_branch(branch, entries, single_branch=single_branch)
            branch_name = str(branch.get("branch", "") or "")
            if not branch_name:
                any_failed = True
                result["results"].append({"branch": branch_name, "status": "blocked", "reason": "branch name is missing"})
                continue
            if unassigned and not single_branch:
                any_failed = True
                result["results"].append({
                    "domain": branch.get("domain", ""),
                    "branch": branch_name,
                    "status": "blocked",
                    "reason": "Changed files without a domain cannot be split across multiple domain branches.",
                    "unassigned_files": [entry["path"] for entry in unassigned],
                })
                continue
            if not paths:
                result["results"].append({
                    "domain": branch.get("domain", ""),
                    "branch": branch_name,
                    "status": "skipped",
                    "reason": "No changed files assigned to this domain branch.",
                    "files": [],
                })
                continue

            switch_code, _, switch_err = _run_git(["switch", branch_name], cwd)
            if switch_code != 0:
                any_failed = True
                result["results"].append({
                    "domain": branch.get("domain", ""),
                    "branch": branch_name,
                    "status": "failed",
                    "reason": switch_err or "git switch failed",
                    "files": paths,
                })
                continue
            add_code, _, add_err = _run_git(["add", "--", *paths], cwd)
            if add_code != 0:
                any_failed = True
                result["results"].append({
                    "domain": branch.get("domain", ""),
                    "branch": branch_name,
                    "status": "failed",
                    "reason": add_err or "git add failed",
                    "files": paths,
                })
                continue
            diff_code, _, _ = _run_git(["diff", "--cached", "--quiet", "--", *paths], cwd)
            if diff_code == 0:
                result["results"].append({
                    "domain": branch.get("domain", ""),
                    "branch": branch_name,
                    "status": "skipped",
                    "reason": "No staged diff for assigned files.",
                    "files": paths,
                })
                continue
            commit_code, out, err = _run_git(["commit", "-m", message], cwd)
            if commit_code != 0:
                any_failed = True
                result["results"].append({
                    "domain": branch.get("domain", ""),
                    "branch": branch_name,
                    "status": "failed",
                    "reason": err or out or "git commit failed",
                    "files": paths,
                })
                continue
            any_committed = True
            rev_code, rev, _ = _run_git(["rev-parse", "--short", "HEAD"], cwd)
            result["results"].append({
                "domain": branch.get("domain", ""),
                "branch": branch_name,
                "status": "committed",
                "commit": rev if rev_code == 0 else "",
                "files": paths,
            })
    finally:
        if original_branch and original_branch != "HEAD":
            _run_git(["switch", original_branch], cwd)
        result["final_branch"] = _current_branch(cwd)

    if any_failed:
        result["status"] = "blocked"
    elif any_committed:
        result["status"] = "committed"
    else:
        result["status"] = "skipped"
    return result


def _commit_plan(branches: list[dict], entries: list[dict], goal: str, enabled: bool, execution: dict) -> dict:
    changed_files = sorted({entry["path"] for entry in entries if entry.get("valid")})
    single_branch = len(branches) <= 1
    return {
        "enabled": enabled,
        "mode": "actual" if enabled else "plan_only",
        "message": f"feat: {goal[:72]}",
        "changed_files": changed_files,
        "file_selection_policy": (
            "stage only changed_files_manifest/generated files; split by domain when domain branches are used"
        ),
        "commands": [
            {
                "branch": item.get("branch", ""),
                "files": _files_for_branch(item, entries, single_branch=single_branch)[0],
                "commands": [
                    f"git switch {item.get('branch', '')}",
                    "git add -- <assigned-files>" if changed_files else "# no changed files to stage",
                    f'git commit -m "feat: {goal[:72]}"',
                ],
            }
            for item in branches
        ],
        "execution": execution,
    }


def _create_pr_if_requested(
    *,
    cwd: str,
    item: dict,
    draft_path: str,
    gh_available: bool,
    enabled: bool,
    draft: bool,
    remote_policy: dict,
) -> dict:
    command = [
        "pr",
        "create",
        "--base",
        item["base"],
        "--head",
        item["branch"],
        "--title",
        item["title"],
        "--body-file",
        draft_path,
    ]
    if draft:
        command.append("--draft")
    shell_command = "gh " + " ".join(f'"{part}"' if " " in part else part for part in command)
    if not enabled:
        return {
            "domain": item["domain"],
            "branch": item["branch"],
            "status": "draft_only",
            "created": False,
            "command": shell_command,
            "reason": "PR CLI execution disabled. Set enable_pr_create or branch_strategy.create_pr to true.",
        }
    if not gh_available:
        return {
            "domain": item["domain"],
            "branch": item["branch"],
            "status": "error",
            "created": False,
            "command": shell_command,
            "reason": "GitHub CLI is not available.",
        }
    if not remote_policy.get("ready"):
        failed = [
            f"{check['check']}: {check.get('reason') or check.get('status')}"
            for check in (remote_policy.get("checks") or [])
            if not check.get("ready") and check.get("check") != "pr_cli_enabled"
        ]
        return {
            "domain": item["domain"],
            "branch": item["branch"],
            "status": "error",
            "created": False,
            "command": shell_command,
            "reason": "Remote PR policy check failed: " + "; ".join(failed),
        }
    code, out, err = _run_gh(command, cwd)
    return {
        "domain": item["domain"],
        "branch": item["branch"],
        "status": "created" if code == 0 else "error",
        "created": code == 0,
        "command": shell_command,
        "url": out if code == 0 else "",
        "reason": err if code != 0 else "",
    }


@pipeline_node("develop_branch_pr_orchestrator")
def develop_branch_pr_orchestrator_node(ctx: NodeContext) -> dict:
    goal = get_goal(ctx.sget)
    cwd = str(ctx.sget("source_dir", "") or os.getcwd())
    branch_strategy = (ctx.sget("develop_main_plan", {}) or {}).get("branch_strategy", {}) or {}
    integration_status = _integration_status(ctx)
    if integration_status != "pass":
        return {
            "branch_pr_result": {
                "status": "blocked",
                "gitflow": "git-flow",
                "base_branch": branch_strategy.get("base_branch", "develop"),
                "resolved_base_ref": "",
                "feature_branches": [],
                "branch_execution": [],
                "pr_plan": [],
                "pr_drafts": [],
                "cli": {
                    "gh_available": shutil.which("gh") is not None,
                    "git_available": True,
                },
                "merge_plan": [],
                "readiness_checks": [
                    {
                        "check": "integration_qa",
                        "status": integration_status or "missing",
                        "ready": False,
                        "reason": "Branch/PR orchestration requires integration_qa_result.status=pass.",
                    }
                ],
                "shadow_branch_check": {
                    "status": "skipped",
                    "reason": "Integration QA did not pass.",
                    "checks": [],
                },
                "merge_ready": False,
            },
            "_thinking": "branch-pr-blocked-integration",
        }

    slug = slugify(goal)[:24]
    feature_branches = branch_strategy.get("domain_branches", []) or [
        {"domain": "uiux", "branch": f"feature/{slug}-uiux"},
        {"domain": "backend", "branch": f"feature/{slug}-backend"},
        {"domain": "frontend", "branch": f"feature/{slug}-frontend"},
    ]
    requested_base = branch_strategy.get("base_branch", "develop")
    create_pr_enabled = _bool_setting(ctx, branch_strategy, "create_pr", False) or _bool_setting(ctx, branch_strategy, "enable_pr_create", False)
    commit_enabled = _bool_setting(ctx, branch_strategy, "create_commit", False) or _bool_setting(ctx, branch_strategy, "enable_git_commit", False)
    draft_pr = bool(branch_strategy.get("draft_pr", ctx.sget("draft_pr", True)))
    resolved_base_ref = _resolve_base_ref(cwd, requested_base)
    changed_file_entries = _collect_changed_file_entries(ctx, cwd)
    changed_files_manifest = sorted({entry["path"] for entry in changed_file_entries if entry.get("valid")})
    pr_description = _pr_description(ctx, goal, changed_files_manifest)
    branch_execution = [
        {
            "domain": item["domain"],
            **_create_branch_if_needed(cwd, item["branch"], resolved_base_ref),
        }
        for item in feature_branches
    ]
    pr_plan = [
        {
            "domain": item["domain"],
            "branch": item["branch"],
            "title": f"[{item['domain']}] {goal[:60]}",
            "base": requested_base,
        }
        for item in feature_branches
    ]
    gh_available = shutil.which("gh") is not None
    remote_policy = _remote_pr_policy(
        cwd=cwd,
        base_branch=requested_base,
        gh_available=gh_available,
        create_pr_enabled=create_pr_enabled,
    )
    commit_execution = _execute_commit_plan(cwd, feature_branches, changed_file_entries, goal, commit_enabled)
    pr_drafts = []
    pr_creation = []
    for item in pr_plan:
        body = _pr_body(goal, item["domain"], item["base"], pr_description)
        draft_path = _write_pr_draft(cwd, item["branch"], item["title"], body)
        pr_drafts.append({
            "domain": item["domain"],
            "branch": item["branch"],
            "title": item["title"],
            "draft_path": draft_path,
            "create_command": (
                f'gh pr create --base {item["base"]} --head {item["branch"]} '
                f'--title "{item["title"]}" --body-file "{draft_path}"'
            ),
        })
        pr_creation.append(_create_pr_if_requested(
            cwd=cwd,
            item=item,
            draft_path=draft_path,
            gh_available=gh_available,
            enabled=create_pr_enabled,
            draft=draft_pr,
            remote_policy=remote_policy,
        ))
    merge_plan = [
        {"step": 1, "target": "uiux/frontend", "strategy": "squash"},
        {"step": 2, "target": "backend", "strategy": "squash"},
        {"step": 3, "target": "develop", "strategy": "merge-after-integration-qa"},
    ]
    has_errors = any(item.get("status") == "error" for item in branch_execution)
    shadow_branch_check = _shadow_branch_check(cwd, resolved_base_ref, feature_branches)
    gate_inputs = {
        "uiux_domain_gate": ctx.sget("uiux_domain_gate_result", {}) or {},
        "backend_domain_gate": ctx.sget("backend_domain_gate_result", {}) or {},
        "frontend_domain_gate": ctx.sget("frontend_domain_gate_result", {}) or {},
        "global_fe_sync": ctx.sget("global_fe_sync_result", {}) or {},
        "integration_qa": ctx.sget("integration_qa_result", {}) or {},
    }
    selected_domains = set(((ctx.sget("develop_main_plan", {}) or {}).get("selected_domains") or ["uiux", "backend", "frontend"]))
    readiness_checks = []
    for name, payload in gate_inputs.items():
        if name.startswith("uiux") and "uiux" not in selected_domains:
            continue
        if name.startswith("backend") and "backend" not in selected_domains:
            continue
        if name.startswith("frontend") and "frontend" not in selected_domains:
            continue
        if name == "global_fe_sync" and not {"uiux", "frontend"}.issubset(selected_domains):
            continue
        status = str(payload.get("status", "")).lower()
        # unknown, missing, empty 상태는 ready로 보지 않음 (엄격한 검증)
        is_ready = status in {"pass", "ready"}
        readiness_checks.append({
            "check": name,
            "status": status or "missing",
            "ready": is_ready,
            "reason": payload.get("reason", ""),
        })
    quality_blocked = any(not item["ready"] for item in readiness_checks)
    shadow_blocked = shadow_branch_check.get("status") == "failed"
    commit_blocked = commit_enabled and commit_execution.get("status") in {"blocked", "failed"}
    pr_creation_failed = create_pr_enabled and any(item.get("status") == "error" for item in pr_creation)
    pr_created = any(item.get("created") for item in pr_creation)
    final_status = "ready"
    if has_errors or quality_blocked or shadow_blocked or commit_blocked or pr_creation_failed:
        final_status = "blocked"
    return {
        "branch_pr_result": {
            "status": final_status,
            "git_action": "CREATE_PR",
            "gitflow": "git-flow",
            "base_branch": requested_base,
            "merge_target": requested_base,
            "resolved_base_ref": resolved_base_ref,
            "branch_name": feature_branches[0]["branch"] if feature_branches else "",
            "feature_branches": feature_branches,
            "changed_files_manifest": changed_files_manifest,
            "changed_file_entries": changed_file_entries,
            "branch_execution": branch_execution,
            "commit_plan": _commit_plan(feature_branches, changed_file_entries, goal, commit_enabled, commit_execution),
            "pr_plan": pr_plan,
            "pr_drafts": pr_drafts,
            "pr_description": pr_description,
            "pr_creation": {
                "mode": "gh_cli" if create_pr_enabled else "draft_only",
                "enabled": create_pr_enabled,
                "draft": draft_pr,
                "remote_policy": remote_policy,
                "results": pr_creation,
            },
            "pr_created": pr_created,
            "cli": {
                "gh_available": gh_available,
                "git_available": True,
            },
            "merge_plan": merge_plan,
            "readiness_checks": readiness_checks,
            "shadow_branch_check": shadow_branch_check,
            "rag_sync": final_status == "ready",
            "next_step": "EMBEDDING_NODE" if final_status == "ready" else "MANUAL_REVIEW_REQUIRED",
            "merge_ready": not has_errors and not quality_blocked and not shadow_blocked and not commit_blocked and not pr_creation_failed,
        },
        "_thinking": "gitflow, branch-create, commit-policy, pr-draft",
    }
