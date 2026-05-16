"""
Repo Cache Manager: GitHub 저장소를 로컬 서버에 캐싱하여 RAG 분석을 지원합니다.
"""

import os
import subprocess
import shutil
from typing import Optional
from observability.logger import get_logger

logger = get_logger()

# backend/connectors/repo_cache.py -> 2단계 상위 = backend/
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(_ROOT, "storage", "repo_cache")

def get_local_repo_path(owner: str, repo: str, token: Optional[str] = None) -> str:
    """
    GitHub 저장소를 로컬 캐시 폴더에 클론하거나 업데이트하고 그 경로를 반환합니다.
    owner/repo 형식이 아니면 원래 경로를 그대로 반환합니다.
    """
    if not owner or not repo:
        return ""

    target_dir = os.path.join(CACHE_DIR, owner, repo)
    
    # 1. 이미 존재하면 업데이트 (git pull)
    if os.path.isdir(os.path.join(target_dir, ".git")):
        try:
            logger.info(f"[RepoCache] Updating {owner}/{repo}...")
            subprocess.run(
                ["git", "pull"],
                cwd=target_dir,
                capture_output=True,
                check=True,
                timeout=30
            )
            return target_dir
        except Exception as e:
            logger.warning(f"[RepoCache] git pull failed: {e}. Re-cloning...")
            shutil.rmtree(target_dir, ignore_errors=True)

    # 2. 신규 클론
    os.makedirs(os.path.dirname(target_dir), exist_ok=True)
    
    # 토큰이 있으면 인증된 URL 사용
    if token:
        clone_url = f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"
    else:
        clone_url = f"https://github.com/{owner}/{repo}.git"

    try:
        logger.info(f"[RepoCache] Cloning {owner}/{repo} to {target_dir}...")
        subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, target_dir],
            capture_output=True,
            check=True,
            timeout=60
        )
        return target_dir
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.decode(errors="replace") if e.stderr else str(e)
        logger.error(f"[RepoCache] Clone failed: {err_msg}")
        # 토큰 노출 방지를 위해 에러 메시지 마스킹
        masked_err = err_msg.replace(token, "***") if token else err_msg
        raise ValueError(f"GitHub 저장소 클론 실패: {masked_err}")
    except Exception as e:
        logger.exception(f"[RepoCache] Unexpected error during clone: {e}")
        raise ValueError(f"저장소 준비 중 오류 발생: {str(e)}")

def is_github_repo_format(path: str) -> bool:
    """path가 'owner/repo' 형식인지 확인."""
    if not path or "/" not in path:
        return False
    # 윈도우 절대 경로(C:/...)나 상대 경로(./)는 제외
    if ":" in path or path.startswith(".") or path.startswith("/") or path.startswith("\\"):
        return False
    parts = path.split("/")
    return len(parts) == 2 and parts[0] and parts[1]
