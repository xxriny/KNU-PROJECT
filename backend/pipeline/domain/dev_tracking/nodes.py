from __future__ import annotations

import json
import os
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# author:xxrin
# Dev Tracking 노드 모음.
# 코드 생성 중심 dev pipeline을 복원하지 않고, PR/브랜치 분석에 필요한
# 노드만 새로 둔다. 기존 기능은 공개 helper로만 재사용한다.


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _run_git(args: list[str], cwd: str) -> tuple[int, str, str]:
    # author:xxrin
    # 구버전 dev pipeline의 아이디어만 재사용한 작은 git 명령 실행 래퍼.
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
    # author:xxrin
    # 기존 PR에 코멘트만 남기기 위한 gh 래퍼. 자동 merge/approve에는 쓰지 않는다.
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


def dev_task_planner(state: dict[str, Any]) -> dict[str, Any]:
    # author:xxrin
    # GitHub PR/webhook payload를 이후 노드들이 공통으로 쓰는 pr_context로 정리한다.
    repository = _as_dict(state.get("repository"))
    pull_request = _as_dict(state.get("pull_request"))
    actor = _as_dict(state.get("actor"))

    owner = str(repository.get("owner") or "").strip()
    repo = str(repository.get("repo") or "").strip()
    branch_name = str(
        pull_request.get("branch_name")
        or pull_request.get("head_ref")
        or pull_request.get("ref")
        or ""
    ).strip()
    pr_number = pull_request.get("pr_number") or pull_request.get("number")
    head_sha = str(pull_request.get("head_sha") or pull_request.get("sha") or "").strip()

    missing = [
        name
        for name, value in {
            "repository.owner": owner,
            "repository.repo": repo,
            "pull_request.branch_name": branch_name,
            "pull_request.pr_number": pr_number,
            "pull_request.head_sha": head_sha,
        }.items()
        if value in ("", None)
    ]
    if missing:
        return {
            "status": "FAIL",
            "error_type": "INVALID_WEBHOOK_PAYLOAD",
            "errors": [f"Missing {item}" for item in missing],
            "dev_tracking_next_action": "blocked",
            "current_step": "dev_task_planner_failed",
        }

    pr_context = {
        "owner": owner,
        "repo": repo,
        "branch_name": branch_name,
        "base_branch": pull_request.get("base_branch") or pull_request.get("base_ref") or "",
        "pr_number": int(pr_number),
        "head_sha": head_sha,
        "created_at": pull_request.get("branch_created_at") or pull_request.get("created_at") or _now_iso(),
        "title": pull_request.get("title") or "",
        "description": pull_request.get("description") or pull_request.get("body") or "",
        "actor": actor,
    }
    return {
        "status": "PASS",
        "pr_context": pr_context,
        "dev_tracking_next_action": "branch_fetcher",
        "current_step": "dev_task_planner_done",
    }


def branch_fetcher(state: dict[str, Any]) -> dict[str, Any]:
    # author:xxrin
    # PR 브랜치를 로컬에 준비하고 webhook의 head SHA와 실제 checkout 결과를 검증한다.
    pr_context = _as_dict(state.get("pr_context"))
    provided_source_dir = str(state.get("source_dir") or "").strip()
    expected_sha = str(pr_context.get("head_sha") or "").strip()

    if provided_source_dir:
        source_dir = provided_source_dir
    else:
        from connectors.repo_cache import get_local_repo_path

        source_dir = get_local_repo_path(
            str(pr_context.get("owner") or ""),
            str(pr_context.get("repo") or ""),
            state.get("github_oauth_token") or state.get("github_token") or None,
        )

    repo_path = Path(source_dir)
    if not repo_path.is_dir():
        return {
            "status": "FAIL",
            "error_type": "LOCAL_REPO_PATH_MISSING",
            "errors": [f"source_dir does not exist: {source_dir}"],
            "dev_tracking_next_action": "blocked",
            "current_step": "branch_fetcher_failed",
        }

    checkout = {
        "branch_name": pr_context.get("branch_name", ""),
        "head_sha": expected_sha,
        "head_sha_matched": False,
        "source_dir": str(repo_path),
    }

    if (repo_path / ".git").is_dir():
        branch = str(pr_context.get("branch_name") or "")
        if branch and not provided_source_dir:
            _run_git(["fetch", "origin", branch], str(repo_path))
            _run_git(["checkout", branch], str(repo_path))
        code, out, err = _run_git(["rev-parse", "HEAD"], str(repo_path))
        if code != 0:
            return {
                "status": "FAIL",
                "error_type": "HEAD_SHA_READ_FAILED",
                "errors": [err or out],
                "checkout": checkout,
                "dev_tracking_next_action": "blocked",
                "current_step": "branch_fetcher_failed",
            }
        actual_sha = out.strip()
        checkout["actual_sha"] = actual_sha
        checkout["head_sha_matched"] = bool(
            expected_sha and actual_sha.lower().startswith(expected_sha.lower())
        )
        if expected_sha and not checkout["head_sha_matched"]:
            return {
                "status": "FAIL",
                "error_type": "HEAD_SHA_MISMATCH",
                "checkout": checkout,
                "dev_tracking_next_action": "blocked",
                "current_step": "branch_fetcher_failed",
            }
    else:
        checkout["head_sha_matched"] = not expected_sha
        checkout["warning"] = "source_dir is not a git repository; checkout verification skipped"

    return {
        "status": "PASS",
        "source_dir": str(repo_path),
        "checkout": checkout,
        "dev_tracking_next_action": "reverse_analyzer",
        "current_step": "branch_fetcher_done",
    }


def reverse_analyzer(state: dict[str, Any]) -> dict[str, Any]:
    # author:xxrin
    # 기존 역분석 helper를 수정하지 않고 호출해서 project_context를 만든다.
    from orchestration.pipeline_runner import build_reverse_context

    source_dir = str(state.get("source_dir") or "")
    project_context = build_reverse_context(source_dir)
    status = "PASS" if project_context else "WARN"
    return {
        "status": status,
        "project_context": project_context,
        "warnings": [] if project_context else ["REVERSE_CONTEXT_EMPTY"],
        "dev_tracking_next_action": "code_inventory_builder",
        "current_step": "reverse_analyzer_done",
    }


def code_inventory_builder(state: dict[str, Any]) -> dict[str, Any]:
    # author:xxrin
    # 코드 인벤토리만 메모리에 만든다. 이 단계에서는 의도적으로 RAG에 저장하지 않는다.
    from pipeline.core.ast_scanner import extract_file_inventory, extract_functions

    source_dir = str(state.get("source_dir") or "")
    if not Path(source_dir).is_dir():
        return {
            "status": "FAIL",
            "error_type": "CODE_INVENTORY_FAILED",
            "errors": [f"source_dir does not exist: {source_dir}"],
            "dev_tracking_next_action": "blocked",
            "current_step": "code_inventory_builder_failed",
        }

    functions = extract_functions(source_dir, max_functions=500)
    files = extract_file_inventory(source_dir, max_files=600)
    by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in functions:
        file_path = str(item.get("file") or "")
        if not file_path:
            continue
        by_file[file_path].append(
            {
                "name": item.get("func_name") or item.get("name") or "",
                "type": "function",
                "docstring": item.get("docstring") or "",
                "start_line": item.get("lineno") or 0,
                "end_line": item.get("end_lineno") or item.get("lineno") or 0,
                "lang": item.get("lang") or "",
            }
        )

    code_inventory = {
        "files": files,
        "symbols_by_file": dict(by_file),
        "summary": {
            "file_count": len(files),
            "symbol_count": sum(len(items) for items in by_file.values()),
        },
    }
    return {
        "status": "PASS",
        "code_inventory": code_inventory,
        "dev_tracking_next_action": "forensic_profiler",
        "current_step": "code_inventory_builder_done",
    }


def forensic_profiler(state: dict[str, Any]) -> dict[str, Any]:
    # author:xxrin
    # MVP용 rule-based 구현 프로파일러. 나중에 LLM 분석으로 고도화할 자리다.
    inventory = _as_dict(state.get("code_inventory"))
    files = inventory.get("files", []) if isinstance(inventory.get("files"), list) else []
    symbols_by_file = _as_dict(inventory.get("symbols_by_file"))

    detected_apis: list[dict[str, Any]] = []
    detected_components: list[dict[str, Any]] = []
    file_role_map: dict[str, str] = {}
    for item in files:
        if not isinstance(item, dict):
            continue
        path = str(item.get("file") or "")
        lower = path.lower()
        role = "module"
        if any(token in lower for token in ("/api/", "router", "route", "endpoint")):
            role = "api"
            for symbol in symbols_by_file.get(path, []):
                detected_apis.append({"name": symbol.get("name"), "file": path})
        elif lower.endswith((".jsx", ".tsx")) or "/components/" in lower:
            role = "component"
            for symbol in symbols_by_file.get(path, []):
                name = str(symbol.get("name") or "")
                if name[:1].isupper():
                    detected_components.append({"name": name, "file": path})
        elif "test" in lower:
            role = "test"
        elif lower.endswith((".md", ".mdx")):
            role = "doc"
        file_role_map[path] = role

    implementation_profile = {
        "detected_apis": detected_apis,
        "detected_components": detected_components,
        "file_role_map": file_role_map,
        "implementation_summary": (
            f"Detected {len(files)} files, {len(detected_apis)} API candidates, "
            f"and {len(detected_components)} component candidates."
        ),
    }
    return {
        "status": "PASS",
        "implementation_profile": implementation_profile,
        "dev_tracking_next_action": "spec_loader",
        "current_step": "forensic_profiler_done",
    }


def _snapshot_to_dict(snapshot: Any) -> dict[str, Any]:
    if snapshot is None:
        return {}
    data: dict[str, Any] = {}
    raw = getattr(snapshot, "snapshot_data", "") or "{}"
    try:
        data = json.loads(raw)
    except Exception:
        data = {"raw": raw}
    return {
        "snapshot_id": getattr(snapshot, "id", ""),
        "run_id": getattr(snapshot, "run_id", ""),
        "team_id": getattr(snapshot, "team_id", ""),
        "title": getattr(snapshot, "title", ""),
        "description": getattr(snapshot, "description", ""),
        "version": getattr(snapshot, "version", ""),
        "published_at": getattr(snapshot, "published_at", None).isoformat()
        if getattr(snapshot, "published_at", None)
        else "",
        "data": data,
        "api_contracts": _extract_contracts(data, "api"),
        "component_contracts": _extract_contracts(data, "component"),
        "milestone_status": data.get("milestone_status") if isinstance(data, dict) else {},
    }


def _extract_contracts(data: Any, kind: str) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    keys = (
        ["api_contracts", "apis", "api_modeler_output", "backend_apis"]
        if kind == "api"
        else ["component_contracts", "components", "component_scheduler_output"]
    )
    found: list[dict[str, Any]] = []
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            found.extend([item for item in value if isinstance(item, dict)])
        elif isinstance(value, dict):
            nested = value.get("apis" if kind == "api" else "components")
            if isinstance(nested, list):
                found.extend([item for item in nested if isinstance(item, dict)])
    return found


def spec_loader(state: dict[str, Any], shared_db: Any = None) -> dict[str, Any]:
    # author:xxrin
    # PR 생성 시점에 유효했던 published snapshot을 선택한다.
    if shared_db is None:
        return {
            "status": "WARN",
            "error_type": "SPEC_SNAPSHOT_DB_UNAVAILABLE",
            "published_spec_snapshot": {},
            "spec_outdated": False,
            "latest_snapshot": {},
            "dev_tracking_next_action": "gap_analyzer",
            "current_step": "spec_loader_done",
        }

    from auth.shared_models import PublishedSnapshot

    pr_context = _as_dict(state.get("pr_context"))
    branch_created_at = _parse_dt(pr_context.get("created_at")) or datetime.now()
    team_id = state.get("team_id")

    query = shared_db.query(PublishedSnapshot)
    if team_id:
        query = query.filter(PublishedSnapshot.team_id == team_id)

    all_snapshots = query.order_by(PublishedSnapshot.published_at.desc()).all()
    selected = None
    latest = all_snapshots[0] if all_snapshots else None
    for snapshot in all_snapshots:
        published_at = getattr(snapshot, "published_at", None)
        if published_at and published_at <= branch_created_at.replace(tzinfo=None):
            selected = snapshot
            break

    selected_dict = _snapshot_to_dict(selected)
    latest_dict = _snapshot_to_dict(latest)
    spec_outdated = bool(
        selected
        and latest
        and getattr(latest, "published_at", None)
        and getattr(selected, "id", "") != getattr(latest, "id", "")
    )
    status = "PASS" if selected else "WARN"
    return {
        "status": status,
        "error_type": "" if selected else "SPEC_SNAPSHOT_NOT_FOUND",
        "published_spec_snapshot": selected_dict,
        "spec_outdated": spec_outdated,
        "latest_snapshot": latest_dict,
        "dev_tracking_next_action": "gap_analyzer",
        "current_step": "spec_loader_done",
    }


def _contract_name(contract: dict[str, Any]) -> str:
    for key in ("name", "id", "path", "endpoint", "route", "method_path"):
        value = contract.get(key)
        if value:
            return str(value).lower()
    method = contract.get("method")
    url = contract.get("url") or contract.get("uri")
    if method or url:
        return f"{method or ''} {url or ''}".strip().lower()
    return ""


def gap_analyzer(state: dict[str, Any]) -> dict[str, Any]:
    # author:xxrin
    # published contract와 실제 구현 후보를 비교하는 MVP GAP 분석기.
    snapshot = _as_dict(state.get("published_spec_snapshot"))
    profile = _as_dict(state.get("implementation_profile"))
    spec_apis = snapshot.get("api_contracts") or []
    spec_components = snapshot.get("component_contracts") or []
    detected_apis = profile.get("detected_apis") or []
    detected_components = profile.get("detected_components") or []

    detected_api_text = " ".join(
        f"{item.get('name', '')} {item.get('file', '')}".lower()
        for item in detected_apis
        if isinstance(item, dict)
    )
    detected_component_names = {
        str(item.get("name") or "").lower()
        for item in detected_components
        if isinstance(item, dict)
    }

    gaps: list[dict[str, Any]] = []
    index = 1
    for contract in spec_apis:
        if not isinstance(contract, dict):
            continue
        name = _contract_name(contract)
        if name and name not in detected_api_text:
            gaps.append(
                {
                    "gap_id": f"GAP_{index:03d}",
                    "severity": "HIGH",
                    "type": "MISSING_API",
                    "spec_target": name,
                    "implementation_target": None,
                    "description": f"설계된 API '{name}'가 구현 후보에서 발견되지 않았습니다.",
                    "spec_outdated_related": bool(state.get("spec_outdated")),
                }
            )
            index += 1
    for contract in spec_components:
        if not isinstance(contract, dict):
            continue
        name = _contract_name(contract)
        if name and name not in detected_component_names:
            gaps.append(
                {
                    "gap_id": f"GAP_{index:03d}",
                    "severity": "MED",
                    "type": "MISSING_COMPONENT",
                    "spec_target": name,
                    "implementation_target": None,
                    "description": f"설계된 컴포넌트 '{name}'가 구현 후보에서 발견되지 않았습니다.",
                    "spec_outdated_related": bool(state.get("spec_outdated")),
                }
            )
            index += 1

    has_high_gap = any(item.get("severity") == "HIGH" for item in gaps)
    return {
        "status": "PASS",
        "gap_report": gaps,
        "has_high_gap": has_high_gap,
        "dev_tracking_next_action": "intent_classifier" if has_high_gap else "milestone_tracker",
        "current_step": "gap_analyzer_done",
    }


def intent_classifier(state: dict[str, Any]) -> dict[str, Any]:
    # author:xxrin
    # MVP용 rule-based 의도 분류기. 이후 structured LLM 분류로 교체한다.
    pr_context = _as_dict(state.get("pr_context"))
    title = str(pr_context.get("title") or "").lower()
    description = str(pr_context.get("description") or "").lower()
    text = f"{title}\n{description}"
    classifications = []
    for gap in state.get("gap_report") or []:
        gap_type = str(gap.get("type") or "").lower()
        target = str(gap.get("spec_target") or "").lower()
        intentional_hint = target and target in text
        if gap.get("spec_outdated_related") and not intentional_hint:
            intent = "UNCERTAIN"
            confidence = 0.55
            action = "PM_REVIEW"
        elif intentional_hint:
            intent = "INTENTIONAL"
            confidence = 0.72
            action = "APPROVE_AS_INTENTIONAL"
        else:
            intent = "UNINTENTIONAL" if "missing" in gap_type else "UNCERTAIN"
            confidence = 0.68 if intent == "UNINTENTIONAL" else 0.5
            action = "REQUEST_FIX" if intent == "UNINTENTIONAL" else "PM_REVIEW"
        classifications.append(
            {
                "gap_id": gap.get("gap_id"),
                "intent": intent,
                "confidence": confidence,
                "reason": f"PR title/description and implementation profile were compared for {gap.get('spec_target')}.",
                "recommended_action": action,
            }
        )
    return {
        "status": "PASS",
        "intent_classification": classifications,
        "requires_pm_approval": bool(classifications),
        "dev_tracking_next_action": "milestone_tracker",
        "current_step": "intent_classifier_done",
    }


def milestone_tracker(state: dict[str, Any]) -> dict[str, Any]:
    # author:xxrin
    # GAP/의도 분류 결과를 PM이 읽을 수 있는 마일스톤 진행률로 바꾼다.
    gaps = state.get("gap_report") or []
    classifications = state.get("intent_classification") or []
    blocked = sum(
        1
        for item in classifications
        if item.get("recommended_action") in {"REQUEST_FIX", "PM_REVIEW"}
    )
    total = max(1, len(gaps))
    completed = max(0, total - blocked)
    completion_rate = int((completed / total) * 100)
    snapshot_status = _as_dict(_as_dict(state.get("published_spec_snapshot")).get("milestone_status"))
    milestone_status = {
        "milestone_id": snapshot_status.get("milestone_id") or "PR_ANALYSIS",
        "completion_rate": completion_rate,
        "completed_features": completed,
        "total_features": total,
        "blocked_features": blocked,
        "estimated_completion_date": snapshot_status.get("estimated_completion_date") or "",
    }
    return {
        "status": "PASS",
        "milestone_status": milestone_status,
        "dev_tracking_next_action": "pm_report_generator",
        "current_step": "milestone_tracker_done",
    }


def pm_report_generator(state: dict[str, Any]) -> dict[str, Any]:
    # author:xxrin
    # TaskApprovalPanel에서 볼 수 있도록 agile_tasks payload에 들어갈 PM Report를 만든다.
    pr_context = _as_dict(state.get("pr_context"))
    gaps = state.get("gap_report") or []
    classifications = state.get("intent_classification") or []
    high_count = sum(1 for gap in gaps if gap.get("severity") == "HIGH")
    med_count = sum(1 for gap in gaps if gap.get("severity") == "MED")
    low_count = sum(1 for gap in gaps if gap.get("severity") == "LOW")
    recommended = sorted(
        {
            item.get("recommended_action")
            for item in classifications
            if item.get("recommended_action")
        }
    )
    if not recommended:
        recommended = ["APPROVE_AS_INTENTIONAL"] if not gaps else ["PM_REVIEW"]
    spec_warning = ""
    if state.get("spec_outdated"):
        selected = _as_dict(state.get("published_spec_snapshot"))
        latest = _as_dict(state.get("latest_snapshot"))
        spec_warning = (
            f"개발자는 snapshot {selected.get('version', '?')} 기준으로 작업했으나 "
            f"현재 snapshot {latest.get('version', '?')} 설계가 존재합니다."
        )
    pm_report = {
        "summary": (
            f"PR #{pr_context.get('pr_number')}에서 GAP {len(gaps)}건이 발견되었습니다 "
            f"(HIGH {high_count}, MED {med_count}, LOW {low_count})."
        ),
        "pr_summary": {
            "owner": pr_context.get("owner"),
            "repo": pr_context.get("repo"),
            "pr_number": pr_context.get("pr_number"),
            "branch_name": pr_context.get("branch_name"),
            "title": pr_context.get("title"),
        },
        "implementation_summary": _as_dict(state.get("implementation_profile")).get("implementation_summary", ""),
        "gap_summary": gaps,
        "intent_summary": classifications,
        "milestone_summary": state.get("milestone_status") or {},
        "spec_outdated_warning": spec_warning,
        "recommended_pm_actions": recommended,
    }
    approval_status = "PENDING_PM_APPROVAL" if gaps else "NO_GAP_DETECTED"
    return {
        "status": "PASS",
        "pm_report": pm_report,
        "approval_status": approval_status,
        "dev_tracking_next_action": "pr_comment_notifier",
        "current_step": "pm_report_generator_done",
    }


def pr_comment_notifier(state: dict[str, Any]) -> dict[str, Any]:
    # author:xxrin
    # 선택적 PR 알림 노드. 이미 존재하는 PR에 코멘트만 남긴다.
    if not state.get("notify_pr"):
        return {
            "status": "SKIPPED",
            "pr_comment": {
                "comment_created": False,
                "reason": "notify_pr is false",
            },
            "dev_tracking_next_action": "task_coordinator",
            "current_step": "pr_comment_notifier_done",
        }

    pr_context = _as_dict(state.get("pr_context"))
    source_dir = str(state.get("source_dir") or os.getcwd())
    pm_report = _as_dict(state.get("pm_report"))
    body = (
        "## NAVIGATOR Dev Tracking Report\n\n"
        f"{pm_report.get('summary', 'GAP report is ready.')}\n\n"
        "PM approval is required in TaskApprovalPanel."
    )
    code, out, err = _run_gh(["pr", "comment", str(pr_context.get("pr_number")), "--body", body], source_dir)
    return {
        "status": "PASS" if code == 0 else "WARN",
        "pr_comment": {
            "pr_number": pr_context.get("pr_number"),
            "comment_created": code == 0,
            "summary": pm_report.get("summary", ""),
            "error": err if code != 0 else "",
            "stdout": out if code == 0 else "",
        },
        "dev_tracking_next_action": "task_coordinator",
        "current_step": "pr_comment_notifier_done",
    }


def task_coordinator(state: dict[str, Any]) -> dict[str, Any]:
    # author:xxrin
    # PM 승인 대기 작업을 기존 agile_tasks 큐에 저장한다.
    from pipeline.domain.agile.task_coordinator import create_task

    pr_context = _as_dict(state.get("pr_context"))
    pm_report = _as_dict(state.get("pm_report"))
    task = create_task(
        task_type="dev_gap_approval",
        title=f"PR #{pr_context.get('pr_number')} GAP 승인 요청",
        description=pm_report.get("summary", "Dev Tracking PM approval requested."),
        area="pm",
        payload={
            "approval_status": state.get("approval_status", "PENDING_PM_APPROVAL"),
            "pr_context": pr_context,
            "pm_report": pm_report,
            "gap_report": state.get("gap_report") or [],
            "intent_classification": state.get("intent_classification") or [],
            "milestone_status": state.get("milestone_status") or {},
        },
        created_by=str(_as_dict(state.get("actor")).get("github_id") or state.get("created_by") or ""),
        team_id=str(state.get("team_id") or ""),
    )
    return {
        "status": "PASS",
        "approval_task": {
            "task_id": task.get("id"),
            "task_type": task.get("task_type"),
            "status": task.get("status"),
        },
        "dev_tracking_next_action": "develop_embedding",
        "current_step": "task_coordinator_done",
    }


def develop_embedding(state: dict[str, Any]) -> dict[str, Any]:
    # author:xxrin
    # MVP에서는 RAG 쓰기를 막고, 추후 저장 어댑터가 사용할 metadata만 반환한다.
    pr_context = _as_dict(state.get("pr_context"))
    gaps = state.get("gap_report") or []
    return {
        "status": "SKIPPED",
        "embedding_result": {
            "status": "skipped",
            "reason": "RAG write adapter is not enabled in MVP.",
            "metadata": {
                "artifact_type": "DEV_GAP_REPORT",
                "pr_number": pr_context.get("pr_number"),
                "branch_name": pr_context.get("branch_name"),
                "approval_status": state.get("approval_status", "PENDING"),
                "gap_count": len(gaps),
                "has_high_gap": bool(state.get("has_high_gap")),
            },
        },
        "dev_tracking_next_action": "develop_loop_controller",
        "current_step": "develop_embedding_done",
    }


def develop_loop_controller(state: dict[str, Any]) -> dict[str, Any]:
    # author:xxrin
    # 구버전 feature 루프가 아니라 PR 묶음 처리 기준으로 loop 결정을 내린다.
    if state.get("approval_status") == "PENDING_PM_APPROVAL":
        decision = "BLOCKED"
        next_action = "pm_approval_pending"
    elif state.get("pending_pr_queue"):
        decision = "NEXT_PR"
        next_action = "branch_fetcher"
    else:
        decision = "COMPLETE"
        next_action = "complete"
    return {
        "status": "PASS",
        "loop_decision": decision,
        "dev_tracking_next_action": next_action,
        "dev_tracking_loop_count": int(state.get("dev_tracking_loop_count", 0) or 0) + 1,
        "current_step": "develop_loop_controller_done",
    }
