"""
ChromaDB 클라이언트 — 벡터 저장소 관리

REQ_ID↔함수 매핑을 영구 벡터 DB에 저장/검색/삭제.
"""

import os
import chromadb
from typing import Optional, List, Dict
from observability.logger import get_logger

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 신규 저장 위치: backend/Data/chroma_db
CHROMA_DB_PATH = os.path.join(_BACKEND_DIR, "Data", "chroma_db")

# 글로벌 ChromaDB 클라이언트 (싱글톤)
_client: Optional[chromadb.PersistentClient] = None
_collection: Optional[chromadb.Collection] = None


def _init_chroma():
    """ChromaDB 클라이언트 초기화 (싱글톤 패턴)"""
    global _client, _collection
    if _client is None:
        os.makedirs(CHROMA_DB_PATH, exist_ok=True)
        _client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        _collection = _client.get_or_create_collection(
            name="pm_agent_knowledge",
            metadata={"hnsw:space": "cosine"}
        )
    return _collection


def add_knowledge(
    run_id: str,
    req_id: str,
    description: str,
    code_links: List[Dict],
    project_name: str = "unknown",
    node: str = "semantic_indexer"
) -> None:
    """
    REQ_ID와 코드 매핑을 ChromaDB에 저장

    Args:
        run_id: 세션 타임스탬프 (YYYYMMDD_HHMMSS)
        req_id: 요구사항 ID (REQ-001 등)
        description: 요구사항 설명
        code_links: [{"file": str, "func_name": str, "lineno": int, "confidence": float}]
        project_name: 프로젝트명
        node: 생성한 노드명 (기본값: semantic_indexer)
    """
    collection = _init_chroma()
    
    # 문서: REQ_ID + 설명 + 코드 위치
    code_str = " | ".join([f"{link['file']}:{link['func_name']}:L{link['lineno']}" 
                           for link in code_links]) if code_links else "no_links"
    document = f"{req_id}: {description} ({code_str})"
    
    # 메타데이터 (검색용 필터)
    metadata = {
        "run_id": run_id,
        "project_name": project_name,
        "req_id": req_id,
        "node": node,
        "code_count": len(code_links),
    }
    
    # 파일/함수 정보 추가 (선택적 메타데이터)
    if code_links:
        metadata["files"] = ",".join(set(link["file"] for link in code_links))
        metadata["funcs"] = ",".join(set(link["func_name"] for link in code_links))
    
    # ChromaDB에 저장 (ID는 run_id + req_id로 유니처)
    doc_id = f"{run_id}:{req_id}"
    collection.upsert(
        ids=[doc_id],
        documents=[document],
        metadatas=[metadata]
    )
    run_id = metadata.get("run_id", "")
    get_logger(run_id).info(f"[ChromaDB] Added: {doc_id}")


def delete_by_run_id(run_id: str) -> int:
    """
    run_id 기반 모든 문서 삭제 (원자적 세션 정리)

    Args:
        run_id: 세션 타임스탬프

    Returns:
        삭제된 문서 수
    """
    collection = _init_chroma()
    
    # 메타데이터 필터로 동일 run_id의 모든 문서 조회
    results = collection.get(where={"run_id": run_id})
    
    if results["ids"]:
        collection.delete(ids=results["ids"])
        get_logger(run_id).info(f"Deleted {len(results['ids'])} documents for run_id={run_id}")
        return len(results["ids"])

    get_logger(run_id).info(f"No documents found for run_id={run_id}")
    return 0


def search_similar(
    query: str,
    top_k: int = 5,
    filter_run_id: Optional[str] = None
) -> List[Dict]:
    """
    유사 REQ_ID 검색

    Args:
        query: 검색 쿼리 ("사용자 인증" 등)
        top_k: 반환할 상위 K개 결과
        filter_run_id: 특정 세션만 검색 (None이면 전체)

    Returns:
        [{"req_id": str, "description": str, "confidence": float, "code_links": [...]}, ...]
    """
    collection = _init_chroma()
    
    # 필터 설정 (선택적)
    where_filter = {"run_id": filter_run_id} if filter_run_id else None
    
    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        where=where_filter
    )
    
    # 결과 포맷팅
    output = []
    if results["ids"] and len(results["ids"]) > 0:
        for i, doc_id in enumerate(results["ids"][0]):
            metadata = results["metadatas"][0][i]
            distance = results["distances"][0][i] if results["distances"] else 0
            
            # Cosine distance → similarity (0~1, 1이 가장 유사)
            similarity = 1 - (distance / 2)
            
            output.append({
                "req_id": metadata.get("req_id", "unknown"),
                "description": results["documents"][0][i],
                "similarity": round(similarity, 3),
                "project": metadata.get("project_name", "unknown"),
                "files": metadata.get("files", "").split(",") if metadata.get("files") else [],
            })
    
    return output


def get_collection_stats() -> Dict:
    """컬렉션 통계 반환 (디버깅용)"""
    collection = _init_chroma()
    count = collection.count()
    return {
        "total_documents": count,
        "collection_name": "pm_agent_knowledge",
        "db_path": CHROMA_DB_PATH,
    }
