"""
Memo DB — 사용자 메모 관리 및 RAG 연동
"""

import os
import chromadb
from typing import Optional, List, Dict, Any
from pipeline.core.models.pm_embedding_model import get_pm_embeddings
from observability.logger import get_logger

# backend 디렉토리 위치 계산
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
DB_PATH = os.path.join(_BACKEND_ROOT, "storage", "pm_sa_vector_db")

_client: Optional[chromadb.PersistentClient] = None
_collection: Optional[chromadb.Collection] = None

def _get_collection():
    global _client, _collection
    if _client is None:
        os.makedirs(DB_PATH, exist_ok=True)
        _client = chromadb.PersistentClient(path=DB_PATH)
        _collection = _client.get_or_create_collection(
            name="user_memos",
            metadata={"hnsw:space": "cosine"}
        )
    return _collection

def add_memo(session_id: str, memo_text: str, selected_text: str = "", section: str = "Global") -> str:
    collection = _get_collection()
    memo_id = f"memo_{os.urandom(4).hex()}"
    
    metadata = {
        "session_id": session_id,
        "type": "memo",
        "selected_text": selected_text,
        "section": section,
        "timestamp": os.urandom(4).hex() # dummy unique
    }
    
    # RAG 연동을 위한 임베딩
    try:
        vector = get_pm_embeddings(f"Memo about {section}: {memo_text}")
    except:
        vector = None
        
    upsert_args = {
        "ids": [memo_id],
        "documents": [memo_text],
        "metadatas": [metadata]
    }
    if vector:
        upsert_args["embeddings"] = [vector]
        
    collection.upsert(**upsert_args)
    return memo_id

def get_memos(session_id: Optional[str] = None) -> List[Dict]:
    collection = _get_collection()
    if session_id:
        results = collection.get(where={"session_id": session_id})
    else:
        results = collection.get()
        
    memos = []
    for i in range(len(results["ids"])):
        memos.append({
            "id": results["ids"][i],
            "text": results["documents"][i],
            "metadata": results["metadatas"][i]
        })
    return memos

def delete_memo(memo_id: str):
    collection = _get_collection()
    collection.delete(ids=[memo_id])

def query_memos(query_text: str, n_results: int = 5):
    """유사 메모 검색"""
    collection = _get_collection()
    try:
        query_vector = get_pm_embeddings(query_text)
        return collection.query(query_embeddings=[query_vector], n_results=n_results)
    except:
        return collection.query(query_texts=[query_text], n_results=n_results)
