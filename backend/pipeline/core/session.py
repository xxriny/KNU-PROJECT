"""
RAG 영속 식별자 유틸.

run_id는 분석 1회의 타임라인 추적용(매 분석마다 새로 생성)이고,
session_id는 ChromaDB에 적재되는 코드 청크의 영속 키다.
같은 source_dir에 대해서는 항상 같은 session_id가 나오도록 절대경로
SHA1 해시(상위 16자)를 사용한다.
"""

from __future__ import annotations

import hashlib
import os


def compute_project_session_id(source_dir: str) -> str:
    """source_dir 절대경로 기반의 안정적 session_id를 반환.
    Windows 대소문자 및 슬래시 정규화 처리.
    """
    if not source_dir:
        return ""
    abs_path = os.path.abspath(source_dir).lower().replace("\\", "/")
    return hashlib.sha1(abs_path.encode("utf-8")).hexdigest()[:16]
