"""
Memo DB — 사용자 메모 관리 및 RAG 연동
"""

import os
import chromadb
from datetime import datetime, timezone
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

def add_memo(
    session_id: str,
    memo_text: str,
    selected_text: str = "",
    section: str = "Global",
    detail: str = "",
) -> str:
    """메모를 ChromaDB에 영속화한다.

    Args:
        session_id: 세션 식별자 (또는 'chat_global' 폴백)
        memo_text: 메모의 제목/요약 (카드에 기본 노출)
        selected_text: 드래그-팝오버 메모의 경우 원문 발췌
        section: 영역 라벨 (Idea Chat / RTM / ...)
        detail: 상세 수정 사항 본문 (선택적, 토글 펼침 시 노출 + UPDATE 시 LLM 컨텍스트에 포함)
    """
    collection = _get_collection()
    memo_id = f"memo_{os.urandom(4).hex()}"

    metadata = {
        "session_id": session_id,
        "type": "memo",
        "selected_text": selected_text,
        "section": section,
        "detail": detail,
        "timestamp": os.urandom(4).hex() # dummy unique
    }

    # RAG 연동을 위한 임베딩 — detail이 있으면 함께 묶어 의미 표현을 풍부하게.
    embed_text = f"Memo about {section}: {memo_text}"
    if detail:
        embed_text += f"\nDetail: {detail}"
    try:
        vector = get_pm_embeddings(embed_text)
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


def apply_memos(memo_ids: List[str]) -> int:
    """메모 ID 목록을 'applied' 상태로 표시한다.

    "지적사항 반영 설계 업데이트" 기능에서 UPDATE 분석이 성공한 직후 호출되어,
    메모는 보존하되 메인 뷰에서는 숨기고 "이전 메모 보기" 토글로만 노출되도록
    메타데이터에 `applied=True`, `applied_at=<ISO timestamp>`을 병합한다.

    Args:
        memo_ids: 적용 처리할 메모 ID 목록

    Returns:
        실제로 갱신된 메모 개수 (존재하지 않는 ID는 스킵)
    """
    if not memo_ids:
        return 0

    collection = _get_collection()
    existing = collection.get(ids=memo_ids)
    if not existing or not existing.get("ids"):
        return 0

    ts = datetime.now(timezone.utc).isoformat()
    new_metadatas = []
    for meta in existing.get("metadatas") or []:
        merged = dict(meta or {})
        merged["applied"] = True
        merged["applied_at"] = ts
        new_metadatas.append(merged)

    collection.update(ids=existing["ids"], metadatas=new_metadatas)
    return len(existing["ids"])
