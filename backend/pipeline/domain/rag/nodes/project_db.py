"""
Project DB — 코드 청크 지식 벡터 저장소
PROJECT_RAG 테이블 정의서를 준수합니다.
"""

import os
import chromadb
from typing import Optional, List, Dict, Any
from pipeline.core.models.google_embed_model import get_google_embeddings
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
            name="project_code_knowledge_v2",
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def upsert_code_chunk(
    session_id: str,
    chunk: CodeChunk,
    vector: Optional[List[float]] = None,
    api_key: str = "",
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
        "docstring": chunk.docstring,
        "lang": chunk.lang,
    }

    upsert_args: Dict[str, Any] = {
        "ids": [chunk.chunk_id],
        "documents": [chunk.content_text],
        "metadatas": [metadata],
    }

    if not vector:
        try:
            vector = get_google_embeddings(chunk.content_text, api_key=api_key)
        except Exception as e:
            logger.warning(f"[PROJECT_DB] Auto-embedding failed: {e}")

    if vector:
        upsert_args["embeddings"] = [vector]

    collection.upsert(**upsert_args)
    logger.info(f"[PROJECT_DB] Persisted chunk: {chunk.chunk_id}")
    return chunk.chunk_id


def upsert_code_chunks_batch(
    session_id: str,
    chunks: List[CodeChunk],
    vectors: List[List[float]]
) -> None:
    """코드 청크 리스트를 배치로 벡터 저장소에 업서트합니다."""
    if not chunks or not vectors or len(chunks) != len(vectors):
        return

    collection = _get_collection()
    
    collection.upsert(
        ids=[c.chunk_id for c in chunks],
        documents=[c.content_text for c in chunks],
        embeddings=vectors,
        metadatas=[{
            "session_id": session_id,
            "chunk_id": c.chunk_id,
            "version": c.version,
            "feature_id": c.feature_id,
            "file_path": c.file_path,
            "func_name": c.func_name,
            "docstring": c.docstring,
            "lang": c.lang,
        } for c in chunks]
    )
    logger.info(f"[PROJECT_DB] Persisted {len(chunks)} chunks in batch.")


def delete_project_knowledge(session_id: str) -> int:
    """세션 관련 코드 청크 전체 삭제"""
    collection = _get_collection()
    results = collection.get(where={"session_id": session_id})
    if results["ids"]:
        collection.delete(ids=results["ids"])
        return len(results["ids"])
    return 0


def count_session_chunks(session_id: str) -> int:
    """주어진 session_id에 적재된 코드 청크 수. 0이면 RAG 인덱스 비어 있음."""
    if not session_id:
        return 0
    try:
        collection = _get_collection()
        results = collection.get(where={"session_id": session_id}, include=[])
        return len(results.get("ids", []) or [])
    except Exception as e:
        logger.warning(f"[PROJECT_DB] count_session_chunks failed: {e}")
        return 0


def has_session_chunks(session_id: str) -> bool:
    """주어진 session_id에 청크가 1개라도 있으면 True."""
    return count_session_chunks(session_id) > 0


def get_session_inventory(session_id: str) -> Dict[str, List[Dict[str, str]]]:
    """세션 내 모든 파일과 해당 파일에 포함된 함수 및 독스트링 목록을 반환"""
    collection = _get_collection()
    results = collection.get(where={"session_id": session_id}, include=["metadatas"])
    metas = results.get("metadatas", []) or []
    
    inventory = {}
    for m in metas:
        path = m.get("file_path", "unknown")
        func = m.get("func_name", "unknown")
        ds = m.get("docstring", "")
        
        if path not in inventory:
            inventory[path] = []
            
        inventory[path].append({"name": func, "summary": ds})
            
    return inventory


def query_project_code(
    query_text: str,
    session_id: Optional[str] = None,
    n_results: int = 10,
    api_key: str = "",
) -> List[Dict[str, Any]]:
    """코드 청크 유사도 검색. (모델 불일치 시 자동 재시도 포함)"""
    from pipeline.core.models.google_embed_model import ALL_EMBED_MODELS, get_google_embeddings, _pad_vector
    from pipeline.core.models.openai_embed_model import get_openai_embeddings
    import os

    collection = _get_collection()
    
    # [CRITICAL] 모델 불일치 대응: 첫 번째 모델로 결과가 없으면 폴백 모델들로 순차 재시도
    for m in ALL_EMBED_MODELS:
        model_name = m["name"]
        provider = m["provider"]
        
        try:
            # 1. 벡터 생성
            if provider == "google":
                query_vector = get_google_embeddings(query_text, api_key=api_key)
            else:
                if not os.environ.get("OPENAI_API_KEY"): continue
                query_vector = _pad_vector(get_openai_embeddings(query_text, model=model_name))
            
            # 2. 검색 실행
            query_kwargs: Dict[str, Any] = {
                "query_embeddings": [query_vector],
                "n_results": n_results,
            }
            if session_id:
                query_kwargs["where"] = {"session_id": session_id}
            
            raw = collection.query(**query_kwargs)
            
            # 3. 결과 확인
            ids = raw.get("ids", [[]])[0]
            if ids and len(ids) > 0:
                docs = raw.get("documents", [[]])[0]
                metas = raw.get("metadatas", [[]])[0]
                distances = raw.get("distances", [[]])[0]

                results = []
                for chunk_id, content, meta, dist in zip(ids, docs, metas, distances):
                    similarity = round(1.0 - dist / 2.0, 4)
                    results.append({
                        "chunk_id": chunk_id,
                        "file_path": meta.get("file_path", ""),
                        "func_name": meta.get("func_name", ""),
                        "content_text": content,
                        "similarity": similarity,
                    })
                logger.info(f"[PROJECT_DB] Found {len(results)} results with model {model_name}")
                return results
            
        except Exception as e:
            logger.warning(f"[PROJECT_DB] Query failed with model {model_name}: {e}")
            continue
            
def get_file_chunks(file_path: str, session_id: str) -> List[Dict[str, Any]]:
    """특정 파일의 모든 청크를 유사도 검색 없이 정확하게 가져옵니다."""
    collection = _get_collection()
    try:
        res = collection.get(
            where={"$and": [{"session_id": session_id}, {"file_path": file_path}]},
            include=["documents", "metadatas"]
        )
        results = []
        for i in range(len(res.get("ids", []))):
            meta = res["metadatas"][i]
            results.append({
                "chunk_id": res["ids"][i],
                "file_path": meta.get("file_path", ""),
                "func_name": meta.get("func_name", ""),
                "content_text": res["documents"][i],
                "similarity": 1.0,  # 직접 조성이므로 1.0
            })
        return results
    except Exception as e:
        logger.warning(f"[PROJECT_DB] get_file_chunks failed for {file_path}: {e}")
        return []
