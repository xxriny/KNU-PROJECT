"""
result_logger — 파이프라인 최종 결과 JSON 로깅

파이프라인 완료 시 backend/Data/ 폴더에 결과를 저장한다.
파일명: YYYYMMDD_HHMMSS_{project_name}.json
"""

import os
import re
import json
from datetime import datetime
from pathlib import Path

from observability.logger import get_logger

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 신규 저장 위치: backend/storage/sessions
DATA_DIR = os.path.join(_BACKEND_DIR, "storage", "sessions")
LOG_DIR = DATA_DIR

# 과거 산출물 정리를 위한 레거시 경로 유지
LEGACY_LOG_DIRS = [
    os.path.join(_BACKEND_DIR, "Data"),
    os.path.join(_BACKEND_DIR, "test", "json"),
]


def _safe_filename(name: str, max_len: int = 40) -> str:
    """Windows/Linux 모두 안전한 파일명으로 변환"""
    safe = re.sub(r'[\\/:*?"<>|\s]+', "_", name)
    safe = safe.strip("._")
    return safe[:max_len] if safe else "unnamed"


def save_result(result: dict) -> str:
    """
    파이프라인 결과를 JSON 파일로 저장.

    Args:
        result: _sanitize_result()를 거친 파이프라인 최종 딕셔너리

    Returns:
        저장된 파일의 절대 경로
    """
    os.makedirs(LOG_DIR, exist_ok=True)

    project_name = (result.get("metadata") or {}).get("project_name", "unnamed")
    run_id = (result.get("metadata") or {}).get("run_id", "")
    safe_name = _safe_filename(project_name)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{ts}_{safe_name}.json"
    filepath = os.path.join(LOG_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    get_logger(run_id).info(f"Result saved → {filepath}")
    return filepath


def delete_session_files(run_id: str) -> int:
    """
    run_id 기반 모든 파일 삭제 (JSON + PROJECT_STATE.md)
    
    Args:
        run_id: 세션 타임스탐프 (YYYYMMDD_HHMMSS format)
    
    Returns:
        삭제된 파일 수
    """
    deleted_count = 0
    log_dirs = []
    for candidate in [LOG_DIR, *LEGACY_LOG_DIRS]:
        if candidate not in log_dirs:
            log_dirs.append(candidate)

    # run_id로 시작하는 모든 파일 삭제 (JSON + PROJECT_STATE.md)
    pattern = f"{run_id}_*"
    logger = get_logger(run_id)
    for log_dir in log_dirs:
        if not os.path.exists(log_dir):
            continue

        for file_path in Path(log_dir).glob(pattern):
            try:
                file_path.unlink()  # 파일 삭제
                logger.info(f"Deleted: {file_path}")
                deleted_count += 1
            except Exception as e:
                logger.error(f"Error deleting {file_path}: {e}")

    logger.info(f"Deleted {deleted_count} files for run_id={run_id}")
    return deleted_count


def delete_exact_file(path: str) -> bool:
    """명시된 파일을 직접 삭제한다. 경로가 비어있거나 없으면 False."""
    if not path:
        return False

    try:
        target = Path(path)
        if not target.exists() or not target.is_file():
            return False
        target.unlink()
        get_logger().info(f"Deleted exact file: {target}")
        return True
    except Exception as e:
        get_logger().error(f"Error deleting exact file {path}: {e}")
        return False

