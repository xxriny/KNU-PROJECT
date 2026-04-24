"""
Code Retriever Node
project_code_knowledge 컬렉션에서 쿼리와 유사한 코드 청크를 검색합니다.
Develop_Pipeline이 직접 호출할 수 있는 standalone 함수도 제공합니다.
"""

from typing import Any, Dict, List, Optional

from pipeline.core.state import PipelineState, make_sget
from pipeline.domain.rag.nodes.project_db import query_project_code
from observability.logger import get_logger

logger = get_logger()


def retrieve_project_code(
    query: str,
    session_id: Optional[str] = None,
    n_results: int = 10,
) -> List[Dict[str, Any]]:
    """REST 엔드포인트나 외부 파이프라인에서 직접 호출하는 검색 함수."""
    if not query.strip():
        return []
    return query_project_code(query, session_id=session_id, n_results=n_results)


def code_retriever_node(state: PipelineState) -> Dict[str, Any]:
    sget = make_sget(state)
    query = sget("rag_query_input", "") or ""
    run_id = sget("run_id", None)

    logger.info(f"[code_retriever] query={query!r:.60s}")

    if not query.strip():
        logger.warning("[code_retriever] rag_query_input이 비어있어 검색을 건너뜁니다.")
        return {"rag_query_result": []}

    results = retrieve_project_code(query, session_id=run_id)
    logger.info(f"[code_retriever] {len(results)}개 청크 검색됨")

    return {"rag_query_result": results}
