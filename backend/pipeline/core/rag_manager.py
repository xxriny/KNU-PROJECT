"""
RAG Manager — 통합 지식 관리 및 적응형 검색 (Phase 2)
기존 pm_db, stack_db, memo_db를 통합하여 컨텍스트를 최적화합니다.
"""

from typing import List, Dict, Any, Optional
from observability.logger import get_logger
from pipeline.core.utils import call_structured

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
        """
        PM 산출물 검색 - 계층형 처리 및 중복 요약
        """
        from pipeline.domain.pm.nodes.pm_db import query_pm_artifacts
        raw_results = query_pm_artifacts(query, n_results=n_results)
        items = self._format_chroma_results(raw_results)
        
        # [Adaptive Logic] 계층형 필터링: 동일 feature_id에 대해 가장 유사도가 높은 것만 본문을 유지
        seen_features = {}
        optimized_items = []
        
        for item in items:
            f_id = item["metadata"].get("feature_id")
            a_type = item["metadata"].get("artifact_type")
            
            # feature_id가 있고 이미 처리된 경우 요약 모드로 전환
            if f_id and f_id in seen_features:
                item["content"] = f"[요약] {a_type} (ID: {f_id}) - 중복 컨텍스트 생략 (캐시 또는 상단 결과 참조)"
                item["is_summary"] = True
            else:
                if f_id: seen_features[f_id] = True
                item["is_summary"] = False
            
            optimized_items.append(item)
            
        return optimized_items

    def _search_stack(self, query: str, n_results: int, session_id: Optional[str]) -> List[Dict[str, Any]]:
        """
        기술 스택 검색 - 정밀 필터링
        """
        from pipeline.domain.pm.nodes.stack_db import search_tech_stacks
        # 기존 search_tech_stacks는 이미 정제된 결과를 반환함
        return search_tech_stacks(query, top_k=n_results)

    def _search_memo(self, query: str, n_results: int, session_id: Optional[str]) -> List[Dict[str, Any]]:
        """
        사용자 메모 검색 - 단순 조회
        """
        from pipeline.domain.pm.nodes.memo_db import query_memos
        results = query_memos(query, n_results=n_results)
        return self._format_chroma_results(results)

    def _format_chroma_results(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """ChromaDB 원시 결과를 표준 리스트 형식으로 변환"""
        formatted = []
        if not results or not results.get("ids"):
            return formatted
            
        for i in range(len(results["ids"][0])):
            formatted.append({
                "id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i] if "distances" in results else 0
            })
        return formatted

# 싱글톤 인스턴스
rag_manager = RAGManager()
