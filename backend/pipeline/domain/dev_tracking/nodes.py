from __future__ import annotations

import json
import os
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from version import DEFAULT_MODEL

from .artifacts import build_dev_gap_report_artifact, persist_dev_knowledge_artifact


"""
Dev Tracking 노드 모음.
코드 생성 중심 dev pipeline을 복원하지 않고, PR/브랜치 분석에 필요한 노드만 새로 둔다.
기존 기능은 공개 helper로만 재사용한다.
"""

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


class DevImplementationProfile(BaseModel):
    detected_apis: list[dict[str, Any]] = Field(default_factory=list)
    detected_components: list[dict[str, Any]] = Field(default_factory=list)
    file_role_map: dict[str, str] = Field(default_factory=dict)
    implementation_summary: str = ""


class DevImplementationProfileResponse(BaseModel):
    implementation_profile: DevImplementationProfile


class DevGapItem(BaseModel):
    gap_id: str
    severity: str = Field(pattern="^(HIGH|MED|LOW)$")
    type: str
    spec_target: str | None = None
    implementation_target: str | None = None
    description: str
    spec_outdated_related: bool = False
    preliminary: bool = False


class DevGapReportResponse(BaseModel):
    gaps: list[DevGapItem] = Field(default_factory=list)


class DevGapIntentItem(BaseModel):
    gap_id: str
    intent: str = Field(pattern="^(INTENTIONAL|UNINTENTIONAL|UNCERTAIN)$")
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    recommended_action: str = Field(
        pattern="^(APPROVE_AS_INTENTIONAL|REQUEST_FIX|PM_REVIEW)$"
    )


class DevGapIntentResponse(BaseModel):
    classifications: list[DevGapIntentItem]


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


def _run_gh(args: list[str], cwd: str, input_text: str | None = None) -> tuple[int, str, str]:
    # author:xxrin
    # 기존 PR에 코멘트만 남기기 위한 gh 래퍼. 자동 merge/approve에는 쓰지 않는다.
    completed = subprocess.run(
        ["gh", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        input=input_text,
        check=False,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def _changed_files_from_git(repo_path: Path, base_branch: str = "") -> list[str]:
    # author: xxrin
    # PR 분석 정확도를 위해 base..HEAD diff에서 변경 파일을 추출하고, 실패 시 빈 목록으로 조용히 degrade한다.
    if not (repo_path / ".git").is_dir():
        return []
    candidates: list[list[str]] = []
    if base_branch:
        candidates.extend(
            [
                ["diff", "--name-only", f"origin/{base_branch}...HEAD"],
                ["diff", "--name-only", f"{base_branch}...HEAD"],
                ["diff", "--name-only", f"{base_branch}..HEAD"],
            ]
        )
    candidates.append(["diff", "--name-only", "HEAD~1..HEAD"])

    for args in candidates:
        code, out, _ = _run_git(args, str(repo_path))
        if code != 0 or not out.strip():
            continue
        files = [
            line.strip().replace("\\", "/")
            for line in out.splitlines()
            if line.strip()
        ]
        if files:
            return files[:300]
    return []


def _changed_file_set(state: dict[str, Any]) -> set[str]:
    checkout = _as_dict(state.get("checkout"))
    candidates = state.get("changed_files") or checkout.get("changed_files") or []
    if not isinstance(candidates, list):
        return set()
    return {
        str(item).replace("\\", "/")
        for item in candidates
        if str(item or "").strip()
    }


def _prioritize_inventory_for_pr(
    inventory: dict[str, Any],
    changed_files: set[str],
    *,
    max_files: int = 240,
    max_symbols: int = 320,
) -> dict[str, Any]:
    # author: xxrin
    # LLM 컨텍스트는 PR 변경 파일을 최우선으로 보존하고 나머지 repo 정보는 제한된 요약으로 뒤에 둔다.
    files = inventory.get("files", []) if isinstance(inventory.get("files"), list) else []
    symbols_by_file = _as_dict(inventory.get("symbols_by_file"))
    if not changed_files:
        selected_files = files[:max_files]
    else:
        changed = [
            item for item in files
            if isinstance(item, dict) and str(item.get("file") or "").replace("\\", "/") in changed_files
        ]
        related_imports = {
            str(path).replace("\\", "/")
            for item in changed
            for path in (item.get("internal_imports") or [])
        }
        related = [
            item for item in files
            if isinstance(item, dict)
            and str(item.get("file") or "").replace("\\", "/") in related_imports
            and item not in changed
        ]
        rest = [item for item in files if item not in changed and item not in related]
        selected_files = [*changed, *related, *rest[: max(0, max_files - len(changed) - len(related))]]

    selected_names = {
        str(item.get("file") or "").replace("\\", "/")
        for item in selected_files
        if isinstance(item, dict)
    }
    selected_symbols: dict[str, list[dict[str, Any]]] = {}
    symbol_count = 0
    for file_name in selected_names:
        items = symbols_by_file.get(file_name) or []
        if not isinstance(items, list):
            continue
        remaining = max_symbols - symbol_count
        if remaining <= 0:
            break
        selected_symbols[file_name] = items[:remaining]
        symbol_count += len(selected_symbols[file_name])

    return {
        "files": selected_files,
        "symbols_by_file": selected_symbols,
        "summary": {
            **_as_dict(inventory.get("summary")),
            "selected_file_count": len(selected_files),
            "selected_symbol_count": symbol_count,
            "changed_file_count": len(changed_files),
        },
    }


def _fallback_reverse_context(source_dir: str, reason: str) -> tuple[str, dict[str, Any]]:
    from pipeline.core.ast_scanner import extract_file_inventory

    files = extract_file_inventory(source_dir, max_files=120)
    context = (
        "Fallback reverse context was generated because the full reverse analyzer "
        f"could not be loaded: {reason}. "
        f"Detected {len(files)} source files."
    )
    return context, {"files": files, "fallback_reason": reason}


def _compress_if_available(
    text: str,
    *,
    enabled: bool,
    rate: float,
    preserve: list[str],
) -> tuple[str, dict[str, Any]]:
    if not enabled or len(text) < 6000:
        return text, {"used": False, "reason": "disabled_or_short_context"}
    try:
        max_chunk_chars = int(os.getenv("NAVIGATOR_PROMPT_COMPRESS_CHUNK_CHARS", "12000") or "12000")
        max_output_chars = int(os.getenv("NAVIGATOR_PROMPT_COMPRESS_OUTPUT_CHARS", "36000") or "36000")
        if max_chunk_chars > 0 and len(text) > max_chunk_chars:
            compressed, meta = _compress_text_in_chunks(
                text,
                rate=rate,
                preserve=preserve,
                max_chunk_chars=max_chunk_chars,
                max_output_chars=max_output_chars,
            )
            return compressed, meta

        from pipeline.core.compressor import get_compressor
        compressed = get_compressor().compress_with_preservation(
            text,
            target_token_rate=rate,
            extra_preserve=preserve,
        )
        return compressed, {
            "used": compressed != text,
            "original_chars": len(text),
            "compressed_chars": len(compressed),
        }
    except Exception as exc:
        return text, {"used": False, "error": str(exc) or type(exc).__name__}


def _split_text_chunks(text: str, max_chars: int) -> list[str]:
    # author: xxrin
    # 긴 JSON/컨텍스트를 줄 단위 chunk로 나눠 압축기가 512 토큰 제한을 넘지 않도록 한다.
    if max_chars <= 0 or len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in text.splitlines():
        line_len = len(line) + 1
        if current and current_len + line_len > max_chars:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        if line_len > max_chars:
            if current:
                chunks.append("\n".join(current))
                current = []
                current_len = 0
            for index in range(0, len(line), max_chars):
                chunks.append(line[index:index + max_chars])
            continue
        current.append(line)
        current_len += line_len
    if current:
        chunks.append("\n".join(current))
    return chunks


def _compress_text_in_chunks(
    text: str,
    *,
    rate: float,
    preserve: list[str],
    max_chunk_chars: int,
    max_output_chars: int,
) -> tuple[str, dict[str, Any]]:
    from pipeline.core.compressor import get_compressor

    compressor = get_compressor()
    chunks = _split_text_chunks(text, max_chunk_chars)
    compressed_parts: list[str] = []
    failed_chunks = 0
    for index, chunk in enumerate(chunks):
        try:
            compressed = compressor.compress_with_preservation(
                chunk,
                target_token_rate=rate,
                extra_preserve=preserve,
            )
        except Exception:
            failed_chunks += 1
            compressed = chunk[:max_chunk_chars]
        compressed_parts.append(f"[chunk {index + 1}/{len(chunks)}]\n{compressed}")

    merged = "\n\n".join(compressed_parts)
    truncated = False
    if max_output_chars > 0 and len(merged) > max_output_chars:
        truncated = True
        merged = merged[:max_output_chars] + "\n... [truncated after chunk compression]"
    return merged, {
        "used": True,
        "mode": "chunked",
        "chunk_count": len(chunks),
        "failed_chunks": failed_chunks,
        "original_chars": len(text),
        "compressed_chars": len(merged),
        "truncated": truncated,
    }


def _call_structured_for_intent(**kwargs):
    from pipeline.core.utils import call_structured

    return call_structured(**kwargs)


def _call_structured_for_forensic(**kwargs):
    from pipeline.core.utils import call_structured

    return call_structured(**kwargs)


def _call_structured_for_gap(**kwargs):
    from pipeline.core.utils import call_structured

    return call_structured(**kwargs)


def _llm_meta(
    mode: str,
    *,
    attempted: bool,
    fallback_used: bool,
    preliminary: bool,
    error: Exception | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = {
        "mode": mode,
        "llm_attempted": attempted,
        "fallback_used": fallback_used,
        "preliminary": preliminary,
        "llm_error_type": type(error).__name__ if error else "",
        "llm_error_message": str(error) if error else "",
        "raw_error": repr(error) if error else "",
    }
    if extra:
        meta.update(extra)
    return meta


def _extend_llm_warnings(
    state: dict[str, Any],
    *,
    node: str,
    message: str,
    error: Exception | None = None,
) -> list[dict[str, Any]]:
    warnings = [
        item
        for item in state.get("llm_warnings") or []
        if isinstance(item, dict)
    ]
    warnings.append(
        {
            "node": node,
            "message": message,
            "llm_error_type": type(error).__name__ if error else "",
            "llm_error_message": str(error) if error else "",
            "raw_error": repr(error) if error else "",
            "requires_pm_review": True,
        }
    )
    return warnings


def _dev_tracking_llm_enabled(state: dict[str, Any], flag_name: str) -> bool:
    # author:xxrin
    # 요청 api_key뿐 아니라 서버 GEMINI_API_KEY fallback까지 반영해야 실제 호출 가능 여부와 일치한다.
    try:
        from pipeline.core.utils import get_effective_key

        get_effective_key(str(state.get("api_key") or ""))
    except Exception:
        return False
    if flag_name in state and state.get(flag_name) is not None:
        return bool(state.get(flag_name))
    return True


def _inventory_file_set(state: dict[str, Any]) -> set[str]:
    inventory = _as_dict(state.get("code_inventory"))
    files = inventory.get("files", []) if isinstance(inventory.get("files"), list) else []
    return {
        str(item.get("file") or "")
        for item in files
        if isinstance(item, dict) and str(item.get("file") or "")
    }


def _validate_llm_implementation_profile(
    profile: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    # author:xxrin
    # 자동 오판 방지를 위해 LLM profiler가 실제 inventory 밖의 파일을 발명하지 못하게 막는다.
    known_files = _inventory_file_set(state)
    role_map = _as_dict(profile.get("file_role_map"))
    if known_files:
        unknown_role_files = sorted(path for path in role_map if path not in known_files)
        if unknown_role_files:
            raise ValueError(f"LLM profiler returned unknown file_role_map files: {unknown_role_files[:5]}")

    for field_name in ("detected_apis", "detected_components"):
        items = profile.get(field_name) or []
        if not isinstance(items, list):
            raise ValueError(f"LLM profiler returned non-list {field_name}")
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"LLM profiler returned invalid {field_name}[{index}]")
            name = str(item.get("name") or "").strip()
            file_path = str(item.get("file") or "").strip()
            if not name or not file_path:
                raise ValueError(f"LLM profiler returned {field_name}[{index}] without name/file")
            if known_files and file_path not in known_files:
                raise ValueError(f"LLM profiler returned unknown {field_name}[{index}].file: {file_path}")
    return profile


def _validate_llm_gap_report(gaps: list[dict[str, Any]], state: dict[str, Any]) -> list[dict[str, Any]]:
    # author:xxrin
    # LLM GAP 결과가 비어 있거나 중복된 식별자를 내면 PM 판단이 흔들리므로 semantic validation을 수행한다.
    seen: set[str] = set()
    for index, gap in enumerate(gaps):
        if not isinstance(gap, dict):
            raise ValueError(f"LLM gap item {index} is not an object")
        gap_id = str(gap.get("gap_id") or "").strip()
        gap_type = str(gap.get("type") or "").strip()
        description = str(gap.get("description") or "").strip()
        severity = str(gap.get("severity") or "").strip()
        if not gap_id or not severity or not gap_type or not description:
            raise ValueError(f"LLM gap item {index} is missing required non-empty fields")
        if gap_id in seen:
            raise ValueError(f"LLM gap report returned duplicate gap_id: {gap_id}")
        seen.add(gap_id)

    if not gaps and _rule_based_gap_report(state, preliminary=True):
        raise ValueError("LLM gap report returned no gaps while rule-based comparison found gaps")
    return gaps


def _validate_llm_intent_classification(
    classifications: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    # author:xxrin
    # 자동 승인과 직접 연결되는 노드라 input GAP과 1:1 매칭 및 preliminary 승인 금지를 강제한다.
    known_gap_ids = {
        str(gap.get("gap_id") or "").strip()
        for gap in gaps
        if isinstance(gap, dict) and str(gap.get("gap_id") or "").strip()
    }
    preliminary_gap_ids = {
        str(gap.get("gap_id") or "").strip()
        for gap in gaps
        if isinstance(gap, dict) and gap.get("preliminary") and str(gap.get("gap_id") or "").strip()
    }
    seen: set[str] = set()
    for index, item in enumerate(classifications):
        if not isinstance(item, dict):
            raise ValueError(f"LLM intent classification {index} is not an object")
        gap_id = str(item.get("gap_id") or "").strip()
        if not gap_id:
            raise ValueError(f"LLM intent classification {index} has empty gap_id")
        if gap_id not in known_gap_ids:
            raise ValueError(f"LLM intent classifier returned unknown gap_id: {gap_id}")
        if gap_id in seen:
            raise ValueError(f"LLM intent classifier returned duplicate gap_id: {gap_id}")
        seen.add(gap_id)
        if not str(item.get("reason") or "").strip():
            raise ValueError(f"LLM intent classification {gap_id} has empty reason")
        confidence = item.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
            raise ValueError(f"LLM intent classification {gap_id} has invalid confidence")
        if gap_id in preliminary_gap_ids and item.get("recommended_action") == "APPROVE_AS_INTENTIONAL":
            raise ValueError(f"LLM intent classifier approved preliminary gap_id: {gap_id}")

    missing = sorted(known_gap_ids - seen)
    if missing:
        raise ValueError(f"LLM intent classifier missed gap_id(s): {missing}")
    return classifications


def dev_task_planner(state: dict[str, Any]) -> dict[str, Any]:
    # author: xxrin
    # PR 이벤트 입력을 공통 컨텍스트(pr_context)로 정규화합니다.
    # 이후 노드가 입력 포맷 차이 없이 동일 키를 안정적으로 참조하도록 하기 위함입니다.
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
        "changed_files": pull_request.get("changed_files") if isinstance(pull_request.get("changed_files"), list) else [],
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
        changed_files = pr_context.get("changed_files") if isinstance(pr_context.get("changed_files"), list) else []
        if not changed_files:
            changed_files = _changed_files_from_git(repo_path, str(pr_context.get("base_branch") or ""))
        checkout["changed_files"] = changed_files
    else:
        checkout["head_sha_matched"] = not expected_sha
        checkout["warning"] = "source_dir is not a git repository; checkout verification skipped"
        checkout["changed_files"] = pr_context.get("changed_files") if isinstance(pr_context.get("changed_files"), list) else []

    return {
        "status": "PASS",
        "source_dir": str(repo_path),
        "checkout": checkout,
        "changed_files": checkout.get("changed_files", []),
        "dev_tracking_next_action": "reverse_analyzer",
        "current_step": "branch_fetcher_done",
    }


def reverse_analyzer(state: dict[str, Any]) -> dict[str, Any]:
    # author:xxrin
    # 기존 역분석 helper를 수정하지 않고 호출해서 project_context를 만든다.
    source_dir = str(state.get("source_dir") or "")
    fallback_warning = ""
    try:
        from orchestration.pipeline_runner import build_reverse_context

        reverse_result = build_reverse_context(source_dir)
    except ModuleNotFoundError as exc:
        fallback_warning = f"REVERSE_CONTEXT_FALLBACK:{exc.name}"
        reverse_result = _fallback_reverse_context(source_dir, str(exc))
    except Exception as exc:
        fallback_warning = f"REVERSE_CONTEXT_FALLBACK:{type(exc).__name__}"
        reverse_result = _fallback_reverse_context(source_dir, str(exc) or type(exc).__name__)
    if isinstance(reverse_result, tuple):
        project_context = reverse_result[0] or ""
        reverse_inventory = reverse_result[1] or {}
    else:
        project_context = reverse_result or ""
        reverse_inventory = {}
    status = "PASS" if project_context else "WARN"
    warnings = [] if project_context else ["REVERSE_CONTEXT_EMPTY"]
    if fallback_warning:
        warnings.append(fallback_warning)
    result = {
        "status": status,
        "project_context": project_context,
        "warnings": warnings,
        "dev_tracking_next_action": "code_inventory_builder",
        "current_step": "reverse_analyzer_done",
    }
    if reverse_inventory:
        result["reverse_code_inventory"] = reverse_inventory
    return result


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


def _rule_based_implementation_profile(state: dict[str, Any]) -> dict[str, Any]:
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
    return implementation_profile


def _llm_implementation_profile(state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    pr_context = _as_dict(state.get("pr_context"))
    changed_files = _changed_file_set(state)
    inventory = _prioritize_inventory_for_pr(_as_dict(state.get("code_inventory")), changed_files)
    context = {
        "code_inventory": inventory,
        "project_context": state.get("project_context", ""),
        "pr_context": pr_context,
        "changed_files": sorted(changed_files),
    }
    user_msg = json.dumps(context, ensure_ascii=False, default=str)
    preserve = [
        str(pr_context.get("branch_name") or ""),
        *[
            str(item.get("file") or "")
            for item in inventory.get("files", [])
            if isinstance(item, dict)
        ][:80],
    ]
    compressed_msg, compression = _compress_if_available(
        user_msg,
        enabled=bool(state.get("compress_prompt", True)),
        rate=float(state.get("compression_rate", 0.55) or 0.55),
        preserve=[item for item in preserve if item],
    )
    result = _call_structured_for_forensic(
        api_key=str(state.get("api_key") or ""),
        model=str(state.get("model") or DEFAULT_MODEL),
        schema=DevImplementationProfileResponse,
        system_prompt = (
            "당신은 PR 분석을 위한 포렌식 코드 프로파일러입니다.\n"
            "\n"
            "목표:\n"
            "- PR에 포함된 소스 파일들을 분석하여 각 파일의 구현상 역할을 분류합니다.\n"
            "- API 후보와 UI/기능 컴포넌트 후보를 식별합니다.\n"
            "- 분석 결과는 반드시 기존 implementation_profile 스키마에 맞춰 반환합니다.\n"
            "\n"
            "분석 기준:\n"
            "- 파일 경로(path)\n"
            "- 파일명 및 디렉터리 구조\n"
            "- 클래스, 함수, 메서드, 라우터, 컨트롤러, 훅, 컴포넌트 등의 심볼(symbol)\n"
            "- 프로젝트 전체 컨텍스트\n"
            "- PR에서 변경된 코드의 목적과 영향 범위\n"
            "\n"
            "분류 지침:\n"
            "- API 엔드포인트, 라우터, 컨트롤러, 서비스 진입점은 detected_apis에 포함합니다.\n"
            "- React/Vue/Svelte 컴포넌트, 화면 단위 모듈, 재사용 가능한 UI 구성요소는 detected_components에 포함합니다.\n"
            "- 각 파일은 구현 목적에 따라 file_role_map에 역할을 매핑합니다.\n"
            "- 구현 요약은 implementation_summary에 간결하게 정리합니다.\n"
            "\n"
            "주의사항:\n"
            "- 추측만으로 존재하지 않는 API나 컴포넌트를 생성하지 마세요.\n"
            "- 테스트 파일, 설정 파일, 문서 파일은 실제 구현 역할과 구분해서 판단하세요.\n"
            "- 파일 내용보다 경로만으로 단정하지 말고, 가능한 경우 심볼과 PR 맥락을 함께 사용하세요.\n"
            "- 불확실한 경우에는 가장 보수적인 역할로 분류하세요.\n"
            "\n"
            "출력 제약:\n"
            "- 반드시 기존 implementation_profile shape만 반환하세요.\n"
            "- 반환 가능한 최상위 키는 다음 네 개뿐입니다:\n"
            "  1. detected_apis\n"
            "  2. detected_components\n"
            "  3. file_role_map\n"
            "  4. implementation_summary\n"
            "- 추가 설명, 마크다운, 자연어 해설, 별도 메타데이터를 출력하지 마세요.\n"
        ),
        user_msg=compressed_msg,
        temperature=0.1,
    )
    implementation_profile = _validate_llm_implementation_profile(
        result.parsed.implementation_profile.model_dump(),
        state,
    )
    return implementation_profile, _llm_meta(
        "llm",
        attempted=True,
        fallback_used=False,
        preliminary=False,
        extra={
            "model": str(state.get("model") or DEFAULT_MODEL),
            "usage": result.usage,
            "cost": result.cost,
            "retry_count": result.retry_count,
            "compression": compression,
        },
    )


def forensic_profiler(state: dict[str, Any]) -> dict[str, Any]:
    # author:xxrin
    # LLM structured output이 primary이고, rule-based는 PM 검토용 preliminary fallback이다.
    meta: dict[str, Any]
    llm_warnings = state.get("llm_warnings") or []
    if _dev_tracking_llm_enabled(state, "use_llm_forensic_profiler"):
        try:
            implementation_profile, meta = _llm_implementation_profile(state)
        except Exception as exc:
            implementation_profile = _rule_based_implementation_profile(state)
            meta = _llm_meta(
                "rule_based_fallback",
                attempted=True,
                fallback_used=True,
                preliminary=True,
                error=exc,
            )
            llm_warnings = _extend_llm_warnings(
                state,
                node="forensic_profiler",
                message="LLM forensic profiling failed; rule-based code role draft requires PM review.",
                error=exc,
            )
    else:
        implementation_profile = _rule_based_implementation_profile(state)
        meta = _llm_meta(
            "rule_based",
            attempted=False,
            fallback_used=False,
            preliminary=True,
        )
    return {
        "status": "PASS",
        "implementation_profile": implementation_profile,
        "forensic_profiler_meta": meta,
        "llm_warnings": llm_warnings,
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


def _rule_based_gap_report(state: dict[str, Any], *, preliminary: bool = False) -> list[dict[str, Any]]:
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
                    "description": f"?ㅺ퀎??API '{name}'媛 援ы쁽 ?꾨낫?먯꽌 諛쒓껄?섏? ?딆븯?듬땲??",
                    "spec_outdated_related": bool(state.get("spec_outdated")),
                    "preliminary": preliminary,
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
                    "description": f"?ㅺ퀎??而댄룷?뚰듃 '{name}'媛 援ы쁽 ?꾨낫?먯꽌 諛쒓껄?섏? ?딆븯?듬땲??",
                    "spec_outdated_related": bool(state.get("spec_outdated")),
                    "preliminary": preliminary,
                }
            )
            index += 1
    return gaps


def _llm_gap_report(state: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    snapshot = _as_dict(state.get("published_spec_snapshot"))
    profile = _as_dict(state.get("implementation_profile"))
    changed_files = _changed_file_set(state)
    context = {
        "published_spec_snapshot": snapshot,
        "implementation_profile": profile,
        "spec_outdated": bool(state.get("spec_outdated")),
        "project_context": state.get("project_context", ""),
        "dev_knowledge_context": state.get("dev_knowledge_context", ""),
        "changed_files": sorted(changed_files),
    }
    user_msg = json.dumps(context, ensure_ascii=False, default=str)
    preserve = [
        *[
            _contract_name(item)
            for item in snapshot.get("api_contracts", [])
            if isinstance(item, dict)
        ],
        *[
            _contract_name(item)
            for item in snapshot.get("component_contracts", [])
            if isinstance(item, dict)
        ],
    ]
    compressed_msg, compression = _compress_if_available(
        user_msg,
        enabled=bool(state.get("compress_prompt", True)),
        rate=float(state.get("compression_rate", 0.55) or 0.55),
        preserve=[item for item in preserve if item],
    )
    result = _call_structured_for_gap(
        api_key=str(state.get("api_key") or ""),
        model=str(state.get("model") or DEFAULT_MODEL),
        schema=DevGapReportResponse,
        # system_prompt=(
        #     "You compare a published product/spec snapshot with a PR implementation profile. "
        #     "Return a gap_report as a list of concrete GAP items. "
        #     "Use severity HIGH for missing required APIs or critical contracts, MED for missing components, "
        #     "and LOW for minor inconsistencies. Include spec_outdated_related when relevant. "
        #     "Do not invent automatic approval conclusions."
        # ),
        system_prompt = (
            "당신은 PR 구현 결과가 제품/기획 스펙을 충족하는지 검증하는 Gap Analysis Agent입니다.\n"
            "\n"
            "당신의 임무는 published product/spec snapshot과 PR implementation_profile을 비교하여 "
            "구체적인 gap_report를 생성하는 것입니다.\n"
            "\n"
            "반드시 반환해야 하는 최상위 필드:\n"
            "- gap_report\n"
            "\n"
            "gap_report 작성 규칙:\n"
            "- gap_report는 GAP item들의 리스트입니다.\n"
            "- 각 GAP item은 스펙 요구사항과 PR 구현 프로필 간의 구체적인 차이를 설명해야 합니다.\n"
            "- GAP item은 반드시 입력으로 제공된 스펙 또는 implementation_profile에서 확인 가능한 근거에 기반해야 합니다.\n"
            "- 추측성 문제, 일반적인 개선 제안, 코드 스타일 의견은 GAP으로 작성하지 마세요.\n"
            "\n"
            "비교 대상:\n"
            "1. API 요구사항\n"
            "   - 스펙에 요구된 endpoint, route, controller, request/response contract, auth requirement를 확인합니다.\n"
            "   - implementation_profile.detected_apis에 해당 API가 없거나 핵심 계약이 확인되지 않으면 GAP으로 기록합니다.\n"
            "\n"
            "2. Component 요구사항\n"
            "   - 스펙에 요구된 화면, UI 컴포넌트, 기능 컴포넌트, 사용자 상호작용 단위를 확인합니다.\n"
            "   - implementation_profile.detected_components 또는 file_role_map에서 확인되지 않으면 GAP으로 기록합니다.\n"
            "\n"
            "3. File role / architecture 요구사항\n"
            "   - 스펙이 특정 계층, 모듈, 책임 분리, 데이터 흐름을 요구하는 경우 file_role_map과 implementation_summary를 비교합니다.\n"
            "   - 핵심 구조가 누락되었거나 역할이 불일치하면 GAP으로 기록합니다.\n"
            "\n"
            "4. Implementation summary\n"
            "   - PR 구현 요약이 스펙의 핵심 사용자 흐름 또는 기능 목표를 충족하는지 확인합니다.\n"
            "   - 구현 범위가 스펙 요구사항보다 부족하면 GAP으로 기록합니다.\n"
            "\n"
            "severity 분류 기준:\n"
            "- HIGH:\n"
            "  - 스펙상 필수 API가 누락된 경우\n"
            "  - request/response contract, 인증, 권한, 데이터 저장, 상태 전이 등 critical contract가 누락 또는 위반된 경우\n"
            "  - 주요 사용자 흐름이 동작할 수 없을 정도의 구현 누락이 있는 경우\n"
            "\n"
            "- MED:\n"
            "  - 스펙상 필요한 UI/기능 컴포넌트가 누락된 경우\n"
            "  - 핵심 API는 있으나 보조 컴포넌트, 화면, 연결 로직이 부족한 경우\n"
            "  - 기능은 일부 구현되었으나 스펙의 주요 요구를 완전히 충족하지 못하는 경우\n"
            "\n"
            "- LOW:\n"
            "  - 명명, 경로, 역할 분류, 요약 표현상의 경미한 불일치\n"
            "  - 기능 동작을 직접 막지는 않지만 스펙과 구현 설명 사이에 작은 차이가 있는 경우\n"
            "\n"
            "spec_outdated_related 사용 기준:\n"
            "- PR 구현이 스펙에 없는 최신 구조, 신규 API, 신규 컴포넌트, 변경된 책임 분리를 명확히 포함하는 경우 true 또는 관련 설명을 포함합니다.\n"
            "- 스펙이 최신 구현을 반영하지 못했을 가능성이 있는 GAP에만 사용합니다.\n"
            "- 단순 구현 누락이나 근거 없는 추측에는 사용하지 마세요.\n"
            "\n"
            "금지사항:\n"
            "- 자동 승인 여부를 판단하지 마세요.\n"
            "- merge 가능, approve 가능, reject 필요 같은 결론을 작성하지 마세요.\n"
            "- 입력에 없는 API, 컴포넌트, 요구사항을 만들어내지 마세요.\n"
            "- 단순 권장사항이나 리팩터링 의견을 GAP으로 만들지 마세요.\n"
            "- 분석 과정이나 내부 추론을 출력하지 마세요.\n"
            "\n"
            "출력은 반드시 gap_report shape만 따르세요.\n"
        ),
        user_msg=compressed_msg,
        temperature=0.1,
    )
    gaps = _validate_llm_gap_report(
        [item.model_dump() for item in result.parsed.gaps],
        state,
    )
    return gaps, _llm_meta(
        "llm",
        attempted=True,
        fallback_used=False,
        preliminary=False,
        extra={
            "model": str(state.get("model") or DEFAULT_MODEL),
            "usage": result.usage,
            "cost": result.cost,
            "retry_count": result.retry_count,
            "compression": compression,
        },
    )


def gap_analyzer(state: dict[str, Any]) -> dict[str, Any]:
    # author:xxrin
    # LLM structured output이 primary이고, rule-based 비교는 PM 검토용 preliminary fallback이다.
    llm_warnings = state.get("llm_warnings") or []
    if _dev_tracking_llm_enabled(state, "use_llm_gap_analyzer"):
        try:
            gaps, analyzer_meta = _llm_gap_report(state)
        except Exception as exc:
            gaps = _rule_based_gap_report(state, preliminary=True)
            analyzer_meta = _llm_meta(
                "rule_based_fallback",
                attempted=True,
                fallback_used=True,
                preliminary=True,
                error=exc,
            )
            llm_warnings = _extend_llm_warnings(
                state,
                node="gap_analyzer",
                message="LLM GAP analysis failed; rule-based GAP draft requires PM review.",
                error=exc,
            )
    else:
        gaps = _rule_based_gap_report(state, preliminary=True)
        analyzer_meta = _llm_meta(
            "rule_based",
            attempted=False,
            fallback_used=False,
            preliminary=True,
        )

    has_high_gap = any(item.get("severity") == "HIGH" for item in gaps)
    return {
        "status": "PASS",
        "gap_report": gaps,
        "gap_analyzer_meta": analyzer_meta,
        "llm_warnings": llm_warnings,
        "has_high_gap": has_high_gap,
        "dev_tracking_next_action": "intent_classifier" if has_high_gap else "milestone_tracker",
        "current_step": "gap_analyzer_done",
    }


def dev_knowledge_loader(state: dict[str, Any], shared_db: Any = None) -> dict[str, Any]:
    # 과거 PM 승인/거절 결정을 intent classifier가 참고할 수 있도록 shared.db 지식을 조회한다.
    if shared_db is None:
        return {
            "status": "SKIPPED",
            "dev_knowledge": {
                "count": 0,
                "context_text": "",
                "reason": "shared_db unavailable",
            },
            "dev_knowledge_context": "",
            "dev_tracking_next_action": state.get("dev_tracking_next_action", "milestone_tracker"),
            "current_step": "dev_knowledge_loader_done",
        }

    pr_context = _as_dict(state.get("pr_context"))
    gap_terms = [
        str(gap.get("spec_target") or gap.get("type") or "")
        for gap in state.get("gap_report") or []
        if isinstance(gap, dict)
    ]
    query = " ".join(
        item
        for item in [
            str(pr_context.get("title") or ""),
            *gap_terms,
        ]
        if item
    ).strip()

    try:
        from .knowledge import query_dev_knowledge_artifacts

        result = query_dev_knowledge_artifacts(
            shared_db,
            team_id=str(state.get("team_id") or ""),
            owner=str(pr_context.get("owner") or ""),
            repo=str(pr_context.get("repo") or ""),
            query=query,
            limit=5,
        )
        return {
            "status": "PASS",
            "dev_knowledge": result,
            "dev_knowledge_context": result.get("context_text", ""),
            "dev_tracking_next_action": state.get("dev_tracking_next_action", "milestone_tracker"),
            "current_step": "dev_knowledge_loader_done",
        }
    except Exception as knowledge_error:
        return {
            "status": "WARN",
            "dev_knowledge": {
                "count": 0,
                "context_text": "",
                "error": str(knowledge_error) or type(knowledge_error).__name__,
            },
            "dev_knowledge_context": "",
            "dev_tracking_next_action": state.get("dev_tracking_next_action", "milestone_tracker"),
            "current_step": "dev_knowledge_loader_done",
        }


def _rule_based_intent_classification(state: dict[str, Any]) -> list[dict[str, Any]]:
    # author:xxrin
    # MVP용 rule-based 의도 분류기. 이후 structured LLM 분류로 교체된다.
    pr_context = _as_dict(state.get("pr_context"))
    title = str(pr_context.get("title") or "").lower()
    description = str(pr_context.get("description") or "").lower()
    text = f"{title}\n{description}"
    knowledge_text = str(state.get("dev_knowledge_context") or "").lower()
    classifications: list[dict[str, Any]] = []
    for gap in state.get("gap_report") or []:
        gap_type = str(gap.get("type") or "").lower()
        target = str(gap.get("spec_target") or "").lower()
        intentional_hint = target and target in text
        approved_knowledge_hint = (
            target
            and target in knowledge_text
            and "approved_intentional_change" in knowledge_text
        )
        rejected_knowledge_hint = (
            target
            and target in knowledge_text
            and "rejected_unintentional_change" in knowledge_text
        )
        if gap.get("spec_outdated_related") and not intentional_hint:
            intent = "UNCERTAIN"
            confidence = 0.55
            action = "PM_REVIEW"
        elif rejected_knowledge_hint:
            intent = "UNINTENTIONAL"
            confidence = 0.78
            action = "REQUEST_FIX"
        elif intentional_hint or approved_knowledge_hint:
            intent = "INTENTIONAL"
            confidence = 0.78 if approved_knowledge_hint else 0.72
            action = "APPROVE_AS_INTENTIONAL"
        else:
            intent = "UNINTENTIONAL" if "missing" in gap_type else "UNCERTAIN"
            confidence = 0.68 if intent == "UNINTENTIONAL" else 0.5
            action = "REQUEST_FIX" if intent == "UNINTENTIONAL" else "PM_REVIEW"
        reason_suffix = " Dev Tracking knowledge was considered." if approved_knowledge_hint or rejected_knowledge_hint else ""
        classifications.append(
            {
                "gap_id": gap.get("gap_id"),
                "intent": intent,
                "confidence": confidence,
                "reason": f"PR title/description and implementation profile were compared for {gap.get('spec_target')}.{reason_suffix}",
                "recommended_action": action,
            }
        )
    return classifications


def _preliminary_uncertain_intent_classification(
    state: dict[str, Any],
    *,
    reason_prefix: str,
) -> list[dict[str, Any]]:
    knowledge_text = str(state.get("dev_knowledge_context") or "").lower()
    classifications: list[dict[str, Any]] = []
    for gap in state.get("gap_report") or []:
        if not isinstance(gap, dict):
            continue
        target = str(gap.get("spec_target") or "").lower()
        approved_knowledge_hint = (
            target
            and target in knowledge_text
            and "approved_intentional_change" in knowledge_text
        )
        reason = (
            f"{reason_prefix} Manual PM review is required before treating "
            f"{gap.get('spec_target')} as intentional or unintentional."
        )
        if approved_knowledge_hint:
            reason += " Existing PM decision notes an APPROVED_INTENTIONAL_CHANGE for the same target, but this run still requires PM review."
        classifications.append(
            {
                "gap_id": gap.get("gap_id"),
                "intent": "UNCERTAIN",
                "confidence": 0.5,
                "reason": reason,
                "recommended_action": "PM_REVIEW",
                "preliminary": True,
            }
        )
    return classifications


def _llm_intent_classification(state: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pr_context = _as_dict(state.get("pr_context"))
    gaps = state.get("gap_report") or []
    preserve = [
        str(pr_context.get("branch_name") or ""),
        *[str(gap.get("gap_id") or "") for gap in gaps if isinstance(gap, dict)],
        *[str(gap.get("spec_target") or "") for gap in gaps if isinstance(gap, dict)],
    ]
    context = {
        "pr_context": pr_context,
        "gap_report": gaps,
        "implementation_summary": _as_dict(state.get("implementation_profile")).get("implementation_summary", ""),
        "project_context": state.get("project_context", ""),
        "dev_tracking_knowledge": state.get("dev_knowledge_context", ""),
        "published_spec_snapshot": state.get("published_spec_snapshot") or {},
        "spec_outdated": bool(state.get("spec_outdated")),
    }
    user_msg = json.dumps(context, ensure_ascii=False, default=str)
    compressed_msg, compression = _compress_if_available(
        user_msg,
        enabled=bool(state.get("compress_prompt", True)),
        rate=float(state.get("compression_rate", 0.55) or 0.55),
        preserve=[item for item in preserve if item],
    )
    #Gap이 의도된 변경인지 / 실수인지 / PM 확인이 필요한지 분류
    # system_prompt = (
    #     "You classify PR implementation gaps for a product manager. "
    #     "For each input gap, return exactly one classification with the same gap_id. "
    #     "intent must be INTENTIONAL, UNINTENTIONAL, or UNCERTAIN. "
    #     "recommended_action must be APPROVE_AS_INTENTIONAL, REQUEST_FIX, or PM_REVIEW. "
    #     "Do not approve missing required APIs unless PR text or spec_outdated evidence supports it."
    # )
    system_prompt = (
    "당신은 Product Manager를 위한 PR Gap Intent Classification Agent입니다.\n"
    "\n"
    "목표:\n"
    "- 입력으로 주어진 각 implementation gap이 의도된 변경인지, 의도하지 않은 누락인지, 판단 불가능한지 분류합니다.\n"
    "- 각 gap에 대해 반드시 하나의 classification만 반환합니다.\n"
    "- 각 classification은 입력 gap의 gap_id를 그대로 유지해야 합니다.\n"
    "\n"
    "분류 대상:\n"
    "- gap_report에서 생성된 개별 GAP item\n"
    "- PR 설명, 커밋 메시지, 변경 의도\n"
    "- spec_outdated_related evidence\n"
    "- product/spec snapshot과 implementation_profile 간의 차이\n"
    "\n"
    "intent 값:\n"
    "- INTENTIONAL: PR 설명, 변경 의도, 또는 spec_outdated evidence를 통해 해당 gap이 의도된 변경이라고 판단되는 경우\n"
    "- UNINTENTIONAL: 스펙상 필요한 구현이 누락되었고, PR 설명이나 outdated evidence에서도 의도된 변경 근거가 없는 경우\n"
    "- UNCERTAIN: 의도 여부를 판단하기에 근거가 부족하거나, 스펙과 PR 맥락이 충돌하는 경우\n"
    "\n"
    "recommended_action 값:\n"
    "- APPROVE_AS_INTENTIONAL: gap이 명확히 의도된 변경이며, PR 텍스트나 spec_outdated evidence로 뒷받침되는 경우\n"
    "- REQUEST_FIX: gap이 의도되지 않은 누락 또는 구현 실수로 보이는 경우\n"
    "- PM_REVIEW: 의도 여부가 불확실하거나 제품/스펙 판단이 필요한 경우\n"
    "\n"
    "판단 규칙:\n"
    "- 각 input gap마다 정확히 하나의 classification을 반환하세요.\n"
    "- classification의 gap_id는 input gap의 gap_id와 반드시 동일해야 합니다.\n"
    "- missing required API, critical contract, 인증/권한, 데이터 무결성 관련 gap은 기본적으로 UNINTENTIONAL로 판단합니다.\n"
    "- 단, PR 텍스트 또는 spec_outdated evidence가 해당 gap이 의도된 변경임을 명확히 뒷받침하는 경우에만 INTENTIONAL로 분류할 수 있습니다.\n"
    "- spec_outdated_related가 true라고 해서 자동으로 INTENTIONAL로 판단하지 마세요. 실제 근거가 있어야 합니다.\n"
    "- 근거가 부족한 경우 APPROVE_AS_INTENTIONAL을 사용하지 말고 PM_REVIEW를 권장하세요.\n"
    "\n"
    "recommended_action 매핑 기준:\n"
    "- intent가 INTENTIONAL이고 근거가 명확하면 recommended_action은 APPROVE_AS_INTENTIONAL입니다.\n"
    "- intent가 UNINTENTIONAL이면 recommended_action은 REQUEST_FIX입니다.\n"
    "- intent가 UNCERTAIN이면 recommended_action은 PM_REVIEW입니다.\n"
    "\n"
    "금지사항:\n"
    "- missing required API를 근거 없이 승인하지 마세요.\n"
    "- PR 텍스트나 spec_outdated evidence 없이 critical gap을 INTENTIONAL로 분류하지 마세요.\n"
    "- 입력에 없는 gap_id를 생성하지 마세요.\n"
    "- 하나의 gap에 여러 classification을 반환하지 마세요.\n"
    "- 전체 PR에 대한 approve/reject/merge 가능 여부를 판단하지 마세요.\n"
    "- 일반적인 개선 제안이나 리팩터링 의견을 추가하지 마세요.\n"
    "\n"
    "출력 제약:\n"
    "- 반드시 classification 결과만 반환하세요.\n"
    "- 추가 설명, 마크다운, 분석 과정, 종합 결론을 출력하지 마세요.\n"
),
    result = _call_structured_for_intent(
        api_key=str(state.get("api_key") or ""),
        model=str(state.get("model") or DEFAULT_MODEL),
        schema=DevGapIntentResponse,
        system_prompt=system_prompt,
        user_msg=compressed_msg,
        temperature=0.1,
    )
    classifications = _validate_llm_intent_classification(
        [item.model_dump() for item in result.parsed.classifications],
        gaps,
    )
    return classifications, _llm_meta(
        "llm",
        attempted=True,
        fallback_used=False,
        preliminary=False,
        extra={
            "model": str(state.get("model") or DEFAULT_MODEL),
            "usage": result.usage,
            "cost": result.cost,
            "retry_count": result.retry_count,
            "compression": compression,
        },
    )


def intent_classifier(state: dict[str, Any]) -> dict[str, Any]:
    classifier_meta: dict[str, Any]
    llm_warnings = state.get("llm_warnings") or []
    use_llm = _dev_tracking_llm_enabled(state, "use_llm_intent_classifier")
    if use_llm and state.get("gap_report"):
        try:
            classifications, classifier_meta = _llm_intent_classification(state)
        except Exception as exc:
            classifications = _preliminary_uncertain_intent_classification(
                state,
                reason_prefix="LLM intent classification failed.",
            )
            classifier_meta = _llm_meta(
                "rule_based_fallback",
                attempted=True,
                fallback_used=True,
                preliminary=True,
                error=exc,
            )
            llm_warnings = _extend_llm_warnings(
                state,
                node="intent_classifier",
                message="LLM intent classification failed; all GAP intents require PM review.",
                error=exc,
            )
    else:
        classifications = _preliminary_uncertain_intent_classification(
            state,
            reason_prefix="LLM intent classification was not attempted because api_key is missing.",
        )
        classifier_meta = _llm_meta(
            "rule_based",
            attempted=False,
            fallback_used=False,
            preliminary=True,
        )
    return {
        "status": "PASS",
        "intent_classification": classifications,
        "intent_classifier_meta": classifier_meta,
        "llm_warnings": llm_warnings,
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
    llm_warnings = [
        item
        for item in state.get("llm_warnings") or []
        if isinstance(item, dict)
    ]
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
        recommended = ["PM_REVIEW"] if gaps or llm_warnings else ["APPROVE_AS_INTENTIONAL"]
    if llm_warnings and "PM_REVIEW" not in recommended:
        recommended.append("PM_REVIEW")
        recommended = sorted(recommended)
    spec_warning = ""
    if state.get("spec_outdated"):
        selected = _as_dict(state.get("published_spec_snapshot"))
        latest = _as_dict(state.get("latest_snapshot"))
        spec_warning = (
            f"媛쒕컻?먮뒗 snapshot {selected.get('version', '?')} 湲곗??쇰줈 ?묒뾽?덉쑝??"
            f"?꾩옱 snapshot {latest.get('version', '?')} ?ㅺ퀎媛 議댁옱?⑸땲??"
        )
    pm_report = {
        "summary": (
            f"PR #{pr_context.get('pr_number')}?먯꽌 GAP {len(gaps)}嫄댁씠 諛쒓껄?섏뿀?듬땲??"
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
        "llm_warnings": llm_warnings,
        "recommended_pm_actions": recommended,
    }
    approval_status = "PENDING_PM_APPROVAL" if gaps or llm_warnings else "NO_GAP_DETECTED"
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


def _desired_status_check_for_state(state: dict[str, Any]) -> tuple[str, str]:
    approval_status = str(state.get("approval_status") or "")
    if approval_status == "NO_GAP_DETECTED":
        return "success", "NAVIGATOR Dev Tracking completed without blocking GAPs."
    if approval_status == "PENDING_PM_APPROVAL":
        return "pending", "NAVIGATOR Dev Tracking is waiting for PM approval."
    if approval_status == "APPROVED_INTENTIONAL_CHANGE":
        return "success", "PM approved the intentional implementation change."
    if approval_status == "REJECTED_UNINTENTIONAL_CHANGE":
        return "failure", "PM rejected the implementation change."
    return "pending", "NAVIGATOR Dev Tracking review is in progress."


def update_pr_status_check(
    state: dict[str, Any],
    status_state: str,
    description: str,
) -> dict[str, Any]:
    # GitHub commit status는 병합 차단/허용 신호다.
    # gh CLI가 없거나 인증이 실패해도 분석 결과 자체는 보존해야 하므로 WARN으로만 기록한다.
    pr_context = _as_dict(state.get("pr_context"))
    owner = str(pr_context.get("owner") or "")
    repo = str(pr_context.get("repo") or "")
    sha = str(pr_context.get("head_sha") or "")
    source_dir = str(state.get("source_dir") or os.getcwd())

    if not owner or not repo or not sha:
        return {
            "status": "SKIPPED",
            "status_updated": False,
            "state": status_state,
            "reason": "owner/repo/head_sha missing",
        }

    payload = {
        "state": status_state,
        "context": "NAVIGATOR Dev Tracking",
        "description": description[:140],
    }
    target_url = str(state.get("approval_url") or state.get("target_url") or "")
    if target_url:
        payload["target_url"] = target_url

    code, out, err = _run_gh(
        [
            "api",
            f"repos/{owner}/{repo}/statuses/{sha}",
            "--method",
            "POST",
            "--input",
            "-",
        ],
        source_dir,
        input_text=json.dumps(payload, ensure_ascii=False),
    )
    return {
        "status": "PASS" if code == 0 else "WARN",
        "status_updated": code == 0,
        "state": status_state,
        "context": payload["context"],
        "description": payload["description"],
        "error": err if code != 0 else "",
        "stdout": out if code == 0 else "",
    }


def pr_status_check_updater(state: dict[str, Any]) -> dict[str, Any]:
    # 분석 직후의 상태를 GitHub commit status에 반영한다.
    # PM 승인이 필요하면 pending, GAP이 없으면 success로 표시한다.
    if not state.get("notify_pr"):
        return {
            "status": "SKIPPED",
            "pr_status_check": {
                "status_updated": False,
                "reason": "notify_pr is false",
            },
            "dev_tracking_next_action": "task_coordinator",
            "current_step": "pr_status_check_updater_done",
        }

    status_state, description = _desired_status_check_for_state(state)
    result = update_pr_status_check(state, status_state, description)
    return {
        "status": result.get("status", "WARN"),
        "pr_status_check": result,
        "dev_tracking_next_action": "task_coordinator",
        "current_step": "pr_status_check_updater_done",
    }


def run_dev_gap_decision_followup(
    task: dict[str, Any],
    decision_status: str,
    reviewed_by: str = "",
    result_payload: dict[str, Any] | None = None,
    shared_db: Any = None,
) -> dict[str, Any]:
    # REST 계층의 기존 import 경로를 유지하기 위한 얇은 wrapper다.
    from .followup import run_dev_gap_decision_followup as run_followup

    return run_followup(
        task,
        decision_status,
        reviewed_by,
        result_payload,
        shared_db,
        run_gh=_run_gh,
    )


def task_coordinator(state: dict[str, Any]) -> dict[str, Any]:
    # author:xxrin
    # PM 승인 대기 작업을 기존 agile_tasks 큐에 저장한다.
    from pipeline.domain.agile.task_coordinator import create_task

    pr_context = _as_dict(state.get("pr_context"))
    pm_report = _as_dict(state.get("pm_report"))
    task = create_task(
        task_type="dev_gap_approval",
        title=f"PR #{pr_context.get('pr_number')} GAP ?뱀씤 ?붿껌",
        description=pm_report.get("summary", "Dev Tracking PM approval requested."),
        area="pm",
        payload={
            "approval_status": state.get("approval_status", "PENDING_PM_APPROVAL"),
            "pr_context": pr_context,
            "pm_report": pm_report,
            "gap_report": state.get("gap_report") or [],
            "intent_classification": state.get("intent_classification") or [],
            "milestone_status": state.get("milestone_status") or {},
            "source_dir": state.get("source_dir") or "",
        },
        created_by=str(_as_dict(state.get("actor")).get("github_id") or state.get("created_by") or ""),
        team_id=str(state.get("team_id") or ""),
        status="pending_approval",
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


def analysis_persister(state: dict[str, Any], shared_db: Any = None) -> dict[str, Any]:
    # author: xxrin
    # 분석 결과와 GAP 분류 결과를 shared.db에 영속 저장합니다.
    # PM 승인 이후에도 추적 가능한 감사 이력과 재조회 가능한 근거 데이터를 남기기 위함입니다.
    if shared_db is None:
        return {
            "status": "SKIPPED",
            "analysis_persistence": {"stored": False, "reason": "shared_db unavailable"},
            "dev_tracking_next_action": "develop_embedding",
            "current_step": "analysis_persister_done",
        }

    from auth.database import Base, shared_engine
    from auth.shared_models import DevGapItem, DevPrAnalysis

    Base.metadata.create_all(
        bind=shared_engine,
        tables=[DevPrAnalysis.__table__, DevGapItem.__table__],
    )

    pr_context = _as_dict(state.get("pr_context"))
    snapshot = _as_dict(state.get("published_spec_snapshot"))
    approval_task = _as_dict(state.get("approval_task"))
    classifications = {
        str(item.get("gap_id") or ""): item
        for item in state.get("intent_classification") or []
        if isinstance(item, dict)
    }
    analysis = DevPrAnalysis(
        team_id=str(state.get("team_id") or ""),
        owner=str(pr_context.get("owner") or ""),
        repo=str(pr_context.get("repo") or ""),
        pr_number=int(pr_context.get("pr_number") or 0),
        branch_name=str(pr_context.get("branch_name") or ""),
        base_branch=str(pr_context.get("base_branch") or ""),
        head_sha=str(pr_context.get("head_sha") or ""),
        source_dir=str(state.get("source_dir") or ""),
        spec_snapshot_id=str(snapshot.get("snapshot_id") or ""),
        approval_status=str(state.get("approval_status") or ""),
        analysis_status=str(state.get("dev_tracking_next_action") or "complete"),
        task_id=str(approval_task.get("task_id") or ""),
        pm_report=json.dumps(state.get("pm_report") or {}, ensure_ascii=False, default=str),
        timeline=json.dumps(state.get("timeline") or [], ensure_ascii=False, default=str),
    )
    shared_db.add(analysis)
    shared_db.flush()

    gap_count = 0
    for gap in state.get("gap_report") or []:
        if not isinstance(gap, dict):
            continue
        gap_id = str(gap.get("gap_id") or "")
        classification = classifications.get(gap_id, {})
        shared_db.add(
            DevGapItem(
                analysis_id=analysis.id,
                gap_id=gap_id,
                severity=str(gap.get("severity") or ""),
                type=str(gap.get("type") or ""),
                spec_target=str(gap.get("spec_target") or ""),
                implementation_target=str(gap.get("implementation_target") or ""),
                intent=str(classification.get("intent") or ""),
                recommended_action=str(classification.get("recommended_action") or ""),
                description=str(gap.get("description") or ""),
            )
        )
        gap_count += 1

    shared_db.commit()
    return {
        "status": "PASS",
        "analysis_persistence": {
            "stored": True,
            "analysis_id": analysis.id,
            "gap_count": gap_count,
        },
        "dev_tracking_next_action": "develop_embedding",
        "current_step": "analysis_persister_done",
    }


def develop_embedding(state: dict[str, Any], shared_db: Any = None) -> dict[str, Any]:
    # author: xxrin
    #  Dev GAP 보고서를 아티팩트로 저장하고 검색 텍스트를 함께 기록합니다.
    # SA/Agile/PM 단계에서 과거 의사결정 컨텍스트를 재사용하기 위함입니다.
    # MVP에서는 RAG 직접 쓰기를 막고, 추후 저장 어댑터가 사용할 metadata를 반환한다.
    # Dev GAP 리포트는 별도 artifacts 모듈에서 정규화하고 shared.db에 저장한다.
    pr_context = _as_dict(state.get("pr_context"))
    gaps = state.get("gap_report") or []
    artifact = build_dev_gap_report_artifact(state)
    persistence = persist_dev_knowledge_artifact(artifact, shared_db)
    return {
        "status": persistence.get("status", "WARN"),
        "embedding_result": {
            "status": "stored" if persistence.get("stored") else "warn",
            "reason": persistence.get("error", ""),
            "artifact_id": persistence.get("artifact_id", ""),
            "metadata": {
                "artifact_type": "DEV_GAP_REPORT",
                "pr_number": pr_context.get("pr_number"),
                "branch_name": pr_context.get("branch_name"),
                "approval_status": state.get("approval_status", "PENDING"),
                "gap_count": len(gaps),
                "has_high_gap": bool(state.get("has_high_gap")),
                "write_enabled": True,
            },
        },
        "dev_tracking_next_action": "develop_loop_controller",
        "current_step": "develop_embedding_done",
    }


def develop_loop_controller(state: dict[str, Any]) -> dict[str, Any]:
    # author: xxrin
    # 승인 상태와 대기 PR 큐를 기준으로 다음 액션을 결정합니다.
    # PM 승인 대기 시 중단하고, 추가 PR이 있으면 연속 처리하도록 흐름을 제어하기 위함입니다.
    # 구버전 feature 루프가 아니라 PR 묶음 처리 기준으로 loop 결정을 내림
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
