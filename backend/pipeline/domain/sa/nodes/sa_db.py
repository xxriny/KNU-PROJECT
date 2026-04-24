"""
SA DB — SA 단계 산출물 통합 벡터 저장소 (PM-SA 통합 구조 준수)
'PM & SA RAG - 테이블 정의서(Table 04)'에 따라 PM과 동일한 컬렉션을 사용하되 phase="SA"로 구분합니다.
"""

import os
from typing import Optional, List, Dict, Any
from pipeline.domain.pm.nodes.pm_db import _get_collection, upsert_pm_artifact
from observability.logger import get_logger

logger = get_logger()

def upsert_sa_artifact(
    session_id: str,
    artifact_data: Dict[str, Any],
    chunk_id: Optional[str] = None,
    feature_id: Optional[str] = None,
    artifact_type: str = "SA_ARCH_BUNDLE",
    version: str = "v1.0",
    vector: Optional[List[float]] = None
) -> str:
    """
    SA 설계 산출물을 통합 RAG(pm_artifact_knowledge)에 저장합니다.
    내부적으로 upsert_pm_artifact를 재사용하되, SA 전용 메타데이터를 보강할 수 있습니다.
    """
    # 1. chunk_id 생성 (없을 경우)
    cid = chunk_id or f"sa_{session_id}_{artifact_type}"
    
    # 2. 통합 DB 업서트 로직 호출 (pm_db.py의 로직 재사용)
    # PM DB 유틸리티를 사용하지만, 내부 메타데이터 처리는 artifact_type 등으로 자동 분기됨
    try:
        return upsert_pm_artifact(
            session_id=session_id,
            artifact_data=artifact_data,
            chunk_id=cid,
            feature_id=feature_id,
            artifact_type=artifact_type,
            version=version,
            vector=vector,
            phase="SA"
        )
    except Exception as e:
        logger.error(f"[SA_DB] Failed to upsert SA artifact: {e}")
        raise

def query_sa_artifacts(query_text: str, n_results: int = 5):
    """통합 RAG에서 SA 관련 지식 검색 (필요 시 phase="SA" 필터링 추가 가능)"""
    from pipeline.domain.pm.nodes.pm_db import query_pm_artifacts
    return query_pm_artifacts(query_text, n_results=n_results)
