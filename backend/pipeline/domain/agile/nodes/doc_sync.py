"""
Doc Sync Node: SA 결과물 → GitHub 동기화.
result_data 변경 감지 → wiki_publisher 호출 → 동기화 상태 반환.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def _compute_hash(data: dict) -> str:
    """SA 데이터의 안정적 해시."""
    try:
        serialized = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
    except Exception:
        return ""


def sync_docs(
    result_data: dict,
    github_token: str,
    owner: str,
    repo: str,
    previous_hash: str = "",
    page_title: str = "SA 설계 문서",
    project_name: str = "Project",
) -> dict:
    """
    SA 결과물을 GitHub에 동기화.

    Returns:
        dict with keys: synced (bool), hash (str), action (str), message (str)
    """
    sa_data = result_data.get("sa_output", {})
    if isinstance(sa_data, dict) and "data" in sa_data:
        sa_data = sa_data["data"]

    current_hash = _compute_hash(sa_data)

    if current_hash == previous_hash:
        return {
            "synced": False,
            "hash": current_hash,
            "action": "skipped",
            "message": "변경사항 없음 (해시 동일)",
        }

    if not github_token or not owner or not repo:
        return {
            "synced": False,
            "hash": current_hash,
            "action": "skipped",
            "message": "GitHub 설정이 없어 동기화를 건너뜁니다.",
        }

    try:
        from pipeline.domain.agile.wiki_publisher import publish_to_github
        result = publish_to_github(
            result_data=result_data,
            owner=owner,
            repo=repo,
            token=github_token,
            page_title=page_title,
            project_name=project_name,
        )
        return {
            "synced": result.get("success", False),
            "hash": current_hash,
            "action": result.get("action", "unknown"),
            "message": f"GitHub #{result.get('number', '?')} {result.get('action', '')} 완료",
        }
    except Exception as e:
        return {
            "synced": False,
            "hash": current_hash,
            "action": "error",
            "message": str(e),
        }
