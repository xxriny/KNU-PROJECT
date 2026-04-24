"""
Project DB — 코드 청크 지식 벡터 저장소
PROJECT_RAG 테이블 정의서를 준수합니다.
"""

import os
import chromadb
from typing import Optional, List, Dict, Any
from pipeline.core.models.nomic_embed_model import get_nomic_embeddings
from pipeline.domain.rag.schemas import CodeChunk
from observability.logger import get_logger

logger = get_logger()

# backend/pipeline/domain/rag/nodes/project_db.py → 5단계 상위 = backend/
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
DB_PATH = os.path.join(_BACKEND_ROOT, "storage", "project_vector_db")

_client: Optional[chromadb.PersistentClient] = None
_collection: Optional[chromadb.Collection] = None


def _get_collection():
    global _client, _collection
    if _client is None:
        os.makedirs(DB_PATH, exist_ok=True)
        _client = chromadb.PersistentClient(path=DB_PATH)
        _collection = _client.get_or_create_collection(
            name="project_code_knowledge",
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def upsert_code_chunk(
    session_id: str,
    chunk: CodeChunk,
    vector: Optional[List[float]] = None,
) -> str:
    """코드 청크(Table: PROJECT_RAG)를 벡터 저장소에 업서트합니다."""
    collection = _get_collection()

    metadata = {
        "session_id": session_id,
        "chunk_id": chunk.chunk_id,
        "version": chunk.version,
        "feature_id": chunk.feature_id,
        "file_path": chunk.file_path,
        "func_name": chunk.func_name,
        "lang": chunk.lang,
    }

    upsert_args: Dict[str, Any] = {
        "ids": [chunk.chunk_id],
        "documents": [chunk.content_text],
        "metadatas": [metadata],
    }

    if not vector:
        try:
            vector = get_nomic_embeddings(chunk.content_text)
        except Exception as e:
            logger.warning(f"[PROJECT_DB] Auto-embedding failed: {e}")

    if vector:
        upsert_args["embeddings"] = [vector]

    collection.upsert(**upsert_args)
    logger.info(f"[PROJECT_DB] Persisted chunk: {chunk.chunk_id}")
    return chunk.chunk_id


def delete_project_knowledge(session_id: str) -> int:
    """세션 관련 코드 청크 전체 삭제"""
    collection = _get_collection()
    results = collection.get(where={"session_id": session_id})
    if results["ids"]:
        collection.delete(ids=results["ids"])
        return len(results["ids"])
    return 0


def query_project_code(
    query_text: str,
    session_id: Optional[str] = None,
    n_results: int = 10,
) -> List[Dict[str, Any]]:
    """코드 청크 유사도 검색. session_id 지정 시 해당 세션 내에서만 검색."""
    collection = _get_collection()
    query_vector = get_nomic_embeddings(query_text)

    query_kwargs: Dict[str, Any] = {
        "query_embeddings": [query_vector],
        "n_results": n_results,
    }
    if session_id:
        query_kwargs["where"] = {"session_id": session_id}

    raw = collection.query(**query_kwargs)

    results = []
    ids = raw.get("ids", [[]])[0]
    docs = raw.get("documents", [[]])[0]
    metas = raw.get("metadatas", [[]])[0]
    distances = raw.get("distances", [[]])[0]

    for chunk_id, content, meta, dist in zip(ids, docs, metas, distances):
        similarity = round(1.0 - dist / 2.0, 4)  # cosine distance → similarity
        results.append({
            "chunk_id": chunk_id,
            "file_path": meta.get("file_path", ""),
            "func_name": meta.get("func_name", ""),
            "content_text": content,
            "similarity": similarity,
        })

    return results
