"""
Stack DB — 기술 스택 지식 벡터 저장소 (PM Domain 전용)
기존 ChromaDB 클라이언트를 PM 도메인에 수렴시키고, 새로운 임베딩 모델 도입을 위한 기반을 마련합니다.
"""

import os
import chromadb
from typing import Optional, List, Dict
from observability.logger import get_logger

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
# 신규 저장 위치: backend/storage/vector_db
DB_PATH = os.path.join(_BACKEND_DIR, "storage", "vector_db")

# 글로벌 ChromaDB 클라이언트 (싱글톤)
_client: Optional[chromadb.PersistentClient] = None
_collection: Optional[chromadb.Collection] = None

def _init_db():
    """DB 초기화 (신규 경로 유지)"""
    global _client, _collection
    if _client is None:
        os.makedirs(DB_PATH, exist_ok=True)
        _client = chromadb.PersistentClient(path=DB_PATH)
        _collection = _client.get_or_create_collection(
            name="pm_tech_stack_knowledge",
            metadata={"hnsw:space": "cosine"}
        )
    return _collection

def upsert_bundle_knowledge(
    run_id: str,
    bundle_data: Dict,
    project_name: str = "unknown"
) -> None:
    """
    PM_BUNDLE의 최종 확정 스택 정보를 지식화하여 저장합니다.
    """
    collection = _init_db()
    
    rtm = bundle_data.get("data", {}).get("rtm", [])
    stacks = bundle_data.get("data", {}).get("tech_stacks", [])
    
    # 기능별로 루프를 돌며 지식화
    for feature in rtm:
        feat_id = feature.get("feature_id")
        desc = feature.get("description", "")
        
        # 해당 기능에 매핑된 APPROVED 스택 찾기
        feat_stacks = [s for s in stacks if s.get("feature_id") == feat_id and s.get("status") == "APPROVED"]
        if not feat_stacks:
            continue
            
        stack_info = ", ".join([f"{s.get('package')} ({s.get('domain')})" for s in feat_stacks])
        document = f"Feature: {desc} | Recommended Stacks: {stack_info}"
        
        metadata = {
            "run_id": run_id,
            "project_name": project_name,
            "feature_id": feat_id,
            "type": "pm_final_bundle"
        }
        
        doc_id = f"{run_id}:{feat_id}"
        collection.upsert(
            ids=[doc_id],
            documents=[document],
            metadatas=[metadata]
        )
        
    get_logger(run_id).info(f"[StackDB] Persisted {len(rtm)} features to knowledge base.")

def delete_session_knowledge(run_id: str) -> int:
    """세션 관련 지식 삭제 (세션 정리용)"""
    collection = _init_db()
    results = collection.get(where={"run_id": run_id})
    if results["ids"]:
        collection.delete(ids=results["ids"])
        return len(results["ids"])
    return 0

def search_tech_stacks(query: str, top_k: int = 5) -> List[Dict]:
    """유사 사례 기반 기술 스택 검색"""
    collection = _init_db()
    results = collection.query(
        query_texts=[query],
        n_results=top_k
    )
    
    output = []
    if results["ids"] and len(results["ids"]) > 0:
        for i, doc_id in enumerate(results["ids"][0]):
            metadata = results["metadatas"][0][i]
            output.append({
                "description": results["documents"][0][i],
                "similarity": 1 - (results["distances"][0][i] / 2) if results["distances"] else 0,
                "project": metadata.get("project_name", "unknown")
            })
    return output
