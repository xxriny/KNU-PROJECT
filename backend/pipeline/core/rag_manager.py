"""
RAG Manager — 통합 지식 관리 및 적응형 검색 (Phase 2)
기존 pm_db, stack_db, memo_db를 통합하여 컨텍스트를 최적화합니다.
"""

from typing import List, Dict, Any, Optional
from observability.logger import get_logger
from pipeline.core.utils import call_structured, format_chroma_results

logger = get_logger()

class RAGManager:
    """
    RAG 검색 전략을 중앙에서 제어하는 관리자.
    계층형 청킹과 적응형 검색(Adaptive Retrieval)을 수행합니다.
    """

    def __init__(self):
        # 향후 전략 확장을 위한 설정값
        self.strategies = {
            "pm": "hierarchical",  # 긴 문서는 계층형으로
            "stack": "targeted",   # 기술 스택은 정밀 타겟팅
            "memo": "simple"       # 메모는 단순 조회 중심
        }

    def adaptive_search(
        self, 
        query: str, 
        context_type: str = "pm", 
        n_results: int = 5,
        session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        쿼리 성격에 따라 검색 전략을 동적으로 선택하여 수행합니다.
        """
        logger.info(f"[RAGManager] Searching {context_type} with query: {query[:50]}...")
        
        if context_type == "pm":
            return self._search_pm(query, n_results, session_id)
        elif context_type == "stack":
            return self._search_stack(query, n_results, session_id)
        else:
            return self._search_memo(query, n_results, session_id)

    def _search_pm(self, query: str, n_results: int, session_id: Optional[str]) -> List[Dict[str, Any]]:
        # PM/SA RAG 제거 — 빈 결과 반환
        logger.info("[RAGManager] _search_pm: ChromaDB removed, returning empty")
        return []

    def _search_stack(self, query: str, n_results: int, session_id: Optional[str]) -> List[Dict[str, Any]]:
        # Stack RAG 제거 — guardian 크롤링으로 대체됨
        logger.info("[RAGManager] _search_stack: ChromaDB removed, returning empty")
        return []

    def _search_memo(self, query: str, n_results: int, session_id: Optional[str]) -> List[Dict[str, Any]]:
        # Memo DB ChromaDB 제거 — SQLAlchemy로 이전됨
        logger.info("[RAGManager] _search_memo: ChromaDB removed, returning empty")
        return []

# 싱글톤 인스턴스
rag_manager = RAGManager()
