"""
Stack Retriever Node (Adaptive RAG)
분석된 요구사항(Features)을 바탕으로 RAG(StackDB)에서 가장 관련성 높은 기술 스택을 선별합니다.
"""

from typing import Dict, Any, List
from pipeline.core.state import PipelineState, make_sget
from pipeline.domain.pm.nodes.stack_db import search_tech_stacks
from observability.logger import get_logger

logger = get_logger()

def stack_retriever_node(state: PipelineState) -> Dict[str, Any]:
    sget = make_sget(state)
    logger.info("=== [Node Entry] stack_retriever_node ===")
    
    features = sget("features", [])
    if not features:
        logger.warning("No features found to search. Skipping RAG.")
        return {"stack_rag_context": "No features provided for RAG search."}

    # 1. 검색 쿼리 생성 (단순 요약 조합)
    # 복잡한 LLM 기반 쿼리 생성 대신, 주요 기능 설명들을 결합하여 의미 정보를 보존합니다.
    query_parts = []
    for f in features[:10]: # 토큰 절약을 위해 상위 10개 기능만 쿼리 재료로 사용
        query_parts.append(f.get("description", ""))
    
    search_query = " ".join(query_parts)
    
    try:
        # 2. RAG Manager를 통한 적응형 검색 (Phase 2)
        from pipeline.core.rag_manager import rag_manager
        results = rag_manager.adaptive_search(search_query, context_type="stack", n_results=10)
        
        if not results:
            logger.info("No matching stacks found via RAGManager.")
            return {"stack_rag_context": "No approved stacks matching requirements were found in RAG."}
            
        # 3. 컨텍스트 포맷팅
        context_lines = ["# Approved Tech Stacks (Relevant to your requirements):"]
        for res in results:
            # RAGManager는 표준화된 형식을 반환하므로 필드 접근 방식 확인 필요
            line = f"- {res['package_name']} (v{res['version_req']}): {res['content']}"
            if res.get('install_cmd'):
                line += f" | Install: {res['install_cmd']}"
            context_lines.append(line)
            
        rag_context = "\n".join(context_lines)
        
        logger.info(f"RAG Retrieval Success: Found {len(results)} relevant stacks via RAGManager.")
        
        return {
            "stack_rag_context": rag_context,
            "thinking_log": (sget("thinking_log", []) or []) + [
                {"node": "stack_retriever", "thinking": f"RAG에서 관련 기술 스택 {len(results)}개를 선별하여 컨텍스트에 주입했습니다."}
            ]
        }
        
    except Exception as e:
        logger.error(f"Stack retrieval failed: {e}")
        return {
            "stack_rag_context": f"Error during RAG retrieval: {str(e)}",
            "thinking_log": (sget("thinking_log", []) or []) + [
                {"node": "stack_retriever", "thinking": "RAG 검색 중 오류가 발생하여 기본 컨텍스트로 진행합니다."}
            ]
        }
