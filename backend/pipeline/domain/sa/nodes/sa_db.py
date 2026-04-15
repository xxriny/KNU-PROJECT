"""
SA DB — SA 단계 산출물 지식 벡터 저장소
제시된 'PM & SA RAG - 테이블 정의서(Table 04)'를 준수합니다.
"""

import os
import chromadb
from typing import Optional, List, Dict, Any
from pipeline.core.models.pm_embedding_model import get_pm_embeddings
from observability.logger import get_logger

# backend 디렉토리 위치 계산 (backend/pipeline/domain/sa/nodes/sa_db.py 기준)
# 5단계 상위: nodes -> domain -> pipeline -> backend
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
DB_PATH = os.path.join(_BACKEND_ROOT, "storage", "pm_sa_vector_db")

# 글로벌 ChromaDB 클라이언트 (싱글톤)
_client: Optional[chromadb.PersistentClient] = None
_collection: Optional[chromadb.Collection] = None

def _get_collection():
    global _client, _collection
    if _client is None:
        os.makedirs(DB_PATH, exist_ok=True)
        _client = chromadb.PersistentClient(path=DB_PATH)
        _collection = _client.get_or_create_collection(
            name="sa_artifact_knowledge",
            metadata={"hnsw:space": "cosine"}
        )
    return _collection

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
    SA 단계의 산출물(Table 04)을 RAG에 저장합니다.
    """
    collection = _get_collection()
    
    cid = chunk_id or f"sa_{session_id}_{artifact_type}"
    content_text = artifact_data if isinstance(artifact_data, str) else str(artifact_data)
    
    metadata = {
        "session_id": session_id,
        "chunk_id": cid,
        "version": version,
        "phase": "SA",
        "artifact_type": artifact_type,
        "feature_id": feature_id or ""
    }
    
    upsert_args = {
        "ids": [cid],
        "documents": [content_text],
        "metadatas": [metadata]
    }
    # 벡터가 없을 경우 자동 임베딩 수행 (Table 04 설계 산출물 전체)
    if not vector:
        text_to_embed = f"{artifact_type}: {str(artifact_data)[:2000]}"
        try:
            vector = get_pm_embeddings(text_to_embed)
        except Exception as e:
            logger.warning(f"[SA_DB] Auto-embedding failed: {e}")

    if vector:
        upsert_args["embeddings"] = [vector]
        
    collection.upsert(**upsert_args)
    get_logger(session_id).info(f"[SA_DB] Persisted artifact: {cid} (Type: {artifact_type})")
    return cid

def delete_sa_knowledge(session_id: str) -> int:
    """세션 관련 SA 지식 삭제"""
    collection = _get_collection()
    results = collection.get(where={"session_id": session_id})
    if results["ids"]:
        collection.delete(ids=results["ids"])
        return len(results["ids"])
    return 0

def query_sa_artifacts(query_text: str, n_results: int = 5):
    """유사 설계 검색 (1024차원 수동 임베딩 적용)"""
    collection = _get_collection()
    query_vector = get_pm_embeddings(query_text)
    return collection.query(query_embeddings=[query_vector], n_results=n_results)
