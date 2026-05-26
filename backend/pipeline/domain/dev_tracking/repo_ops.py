from __future__ import annotations

import subprocess
from pathlib import Path


def _run_git(args: list[str], cwd: str) -> tuple[int, str, str]:
    # author:xxrin
    # 저장소 상태 조회와 브랜치 전환에 쓰는 최소 git 래퍼다.
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
    # PR 코멘트와 상태 확인을 위한 gh 래퍼다. 자동 승인이나 병합에는 쓰지 않는다.
    try:
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
    except FileNotFoundError:
        # author: xxrin
        # 운영 PC에 gh CLI가 없으면 분석 흐름은 계속하고 후속 동작만 경고로 낮춘다.
        return 127, "", "gh CLI is not installed or not available on PATH"
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def _changed_files_from_git(repo_path: Path, base_branch: str = "") -> list[str]:
    # author:xxrin
    # PR diff 대상 파일만 추출한다. 실패해도 분석 전체는 멈추지 않도록 빈 목록으로 떨어진다.
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
