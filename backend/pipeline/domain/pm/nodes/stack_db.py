"""
Stack DB — 기술 스택 지식 벡터 저장소
제시된 'STACK RAG - 테이블 정의서(Table 05)'를 준수하며, 스택 명세 정보만을 전문적으로 관리합니다.
"""

import os
import chromadb
from typing import Optional, List, Dict, Any
from pipeline.core.models.stack_embedding_model import get_stack_embeddings
from observability.logger import get_logger

# backend 디렉토리 위치 계산 (backend/pipeline/domain/pm/nodes/stack_db.py 기준)
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
DB_PATH = os.path.join(_BACKEND_ROOT, "storage", "stack_vector_db")

# 글로벌 ChromaDB 클라이언트 (싱글톤)
_client: Optional[chromadb.PersistentClient] = None
_collection: Optional[chromadb.Collection] = None

def _get_collection():
    global _client, _collection
    if _client is None:
        os.makedirs(DB_PATH, exist_ok=True)
        _client = chromadb.PersistentClient(path=DB_PATH)
        _collection = _client.get_or_create_collection(
            name="tech_stack_knowledge",
            metadata={"hnsw:space": "cosine"}
        )
    return _collection

def upsert_stack_entry(
    session_id: str,
    stack_data: Dict[str, Any],
    stack_id: Optional[str] = None,
    vector: Optional[List[float]] = None
) -> str:
    """
    개별 기술 스택 정보(Table 05)를 RAG에 저장합니다.
    """
    collection = _get_collection()
    
    sid = stack_id or f"stack_{stack_data.get('package_name', 'unknown')}_{session_id}"
    domain = stack_data.get("domain", "unknown")
    package_name = stack_data.get("package_name", "unknown")
    version_req = stack_data.get("version_req", "unknown")
    install_cmd = stack_data.get("install_cmd", "unknown")
    content_text = stack_data.get("content_text", "")
    
    metadata = {
        "session_id": session_id,
        "stack_id": sid,
        "domain": domain,
        "package_name": package_name,
        "version_req": version_req,
        "install_cmd": install_cmd
    }
    
    upsert_args = {
        "ids": [sid],
        "documents": [content_text],
        "metadatas": [metadata]
    }
    # 벡터가 없을 경우 자동 임베딩 수행 (Table 05 기술 스택 지식)
    if not vector:
        text_to_embed = stack_data.get("content_text") or f"{stack_data.get('package_name')}: {str(stack_data)[:1000]}"
        try:
            vector = get_stack_embeddings(text_to_embed)
        except Exception as e:
            logger.warning(f"[StackDB] Auto-embedding failed: {e}")

    if vector:
        upsert_args["embeddings"] = [vector]
        
    collection.upsert(**upsert_args)
    get_logger(session_id).info(f"[StackDB] Persisted stack: {sid} ({package_name})")
    return sid

def delete_session_knowledge(session_id: str) -> int:
    """세션 관련 기술 스택 지식 삭제"""
    collection = _get_collection()
    results = collection.get(where={"session_id": session_id})
    if results["ids"]:
        collection.delete(ids=results["ids"])
        return len(results["ids"])
    return 0

def search_tech_stacks(query: str, top_k: int = 5) -> List[Dict]:
    """유사 사례 기반 기술 스택 검색 (1024차원 수동 임베딩 적용)"""
    collection = _get_collection()
    query_vector = get_stack_embeddings(query)
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=top_k
    )
    
    output = []
    if results["ids"] and len(results["ids"]) > 0:
        for i, doc_id in enumerate(results["ids"][0]):
            metadata = results["metadatas"][0][i]
            output.append({
                "package_name": metadata.get("package_name"),
                "install_cmd": metadata.get("install_cmd"),
                "version_req": metadata.get("version_req"),
                "content": results["documents"][0][i],
                "similarity": 1 - (results["distances"][0][i] / 2) if results["distances"] else 0
            })
    return output
