"""
Modular Analysis graphs (Scan, PM, SA).
"""

from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from pipeline.core.state import PipelineState
from pipeline.core.utils import active_usage_log

# Node Chain Definitions — stack_retriever, pm_embedding, sa_embedding 제거 (RAG 없음)
_PM_CHAIN = (
    "requirement_analyzer",
    "stack_planner",
)

_SA_CHAIN = (
    "sa_merge_project",
    "component_scheduler",
    "sa_unified_modeler",
    "sa_test_analysis",
    "sa_project_structure",
)


class _PipelineRegistry:
    _cache: dict[str, object] = {}

    @classmethod
    def get_or_build(cls, key: str, builder_fn):
        if key not in cls._cache:
            cls._cache[key] = builder_fn()
        return cls._cache[key]


def _check_status(state: PipelineState) -> str:
    if hasattr(state, "get"):
        if state.get("error"):
            return "error"
        metadata = state.get("metadata", {}) or {}
        if metadata.get("status") in {"Needs_Clarification", "Error", "Completed_with_errors"}:
            return "error"
    return "continue"

def _route_stack_planning(state: PipelineState) -> str:
    """Stack Planner의 결과를 보고 추가 크롤링 루프 여부를 결정합니다."""
    # 1. 에러 체크
    if _check_status(state) == "error":
        return "error"
    
    # 2. 루프 횟수 제한 (Max 2회)
    loop_count = state.get("loop_count", 0)
    if loop_count >= 2:
        return "finish"

    # 3. PENDING_CRAWL 존재 여부 체크
    # StackPlannerOutput 스키마의 매핑 필드는 'm' (alias 없음). 'stack_mapping'은 구버전 폴백.
    planner_output = state.get("stack_planner_output", {})
    mappings = planner_output.get("m") or planner_output.get("stack_mapping") or []

    if any(item.get("status") == "PENDING_CRAWL" for item in mappings):
        return "loop"

    return "finish"


def _route_pm_integration(state: PipelineState) -> str:
    """PM Analysis 이후 데이터 정합성(Integration Fail) 여부를 체크하여 차단합니다."""
    # 1. 에러가 있거나 명시적으로 통합 실패한 경우 중단
    if _check_status(state) == "error" or state.get("is_integration_fail"):
        return "error"
    
    return "continue"


def _route_sa_analysis(state: PipelineState) -> str:
    """SA Analysis 결과를 보고 설계 단계로 재시도 여부를 결정합니다. (루프 차단 모드)"""
    # 1. 에러 체크
    if _check_status(state) == "error":
        return "error"
    
    # 2. 루프 차단: 결과에 상관없이 1회 실행 후 종료
    return "finish"


def _chain_to_next_nodes(chain: tuple[str, ...]) -> dict[str, list[str]]:
    return {node: ([chain[i + 1]] if i + 1 < len(chain) else []) for i, node in enumerate(chain)}


def _build_pm_pipeline():
    from pipeline.domain.pm.nodes.requirement_analyzer import requirement_analyzer_node
    from pipeline.domain.pm.nodes.stack_planner import stack_planner_node
    from pipeline.domain.pm.nodes.stack_crawling import stack_crawling_node
    from pipeline.domain.pm.nodes.guardian import guardian_node

    workflow = StateGraph(PipelineState)

    # Nodes — stack_embedding, stack_retriever, pm_embedding 제거 (RAG 없이 guardian 직접 사용)
    workflow.add_node("requirement_analyzer", requirement_analyzer_node)
    workflow.add_node("stack_planner", stack_planner_node)
    workflow.add_node("stack_crawling", stack_crawling_node)
    workflow.add_node("guardian", guardian_node)

    # Edges: requirement_analyzer → stack_planner 직접 연결
    workflow.add_edge(START, "requirement_analyzer")
    workflow.add_edge("requirement_analyzer", "stack_planner")

    # Conditional Loop Edge — finish 시 END로 바로 이동
    workflow.add_conditional_edges(
        "stack_planner",
        _route_stack_planning,
        {
            "loop": "stack_crawling",
            "finish": END,
            "error": END
        }
    )

    # 크롤링 피드백 루프: guardian 이후 stack_embedding 없이 바로 stack_planner
    workflow.add_edge("stack_crawling", "guardian")
    workflow.add_edge("guardian", "stack_planner")

    return workflow.compile()


def _build_sa_pipeline():
    from pipeline.domain.sa.nodes.merge_project import sa_merge_project_node
    from pipeline.domain.sa.nodes.component_scheduler import component_scheduler_node
    from pipeline.domain.sa.nodes.sa_unified_modeler import sa_unified_modeler_node
    from pipeline.domain.sa.nodes.sa_test_analysis import sa_test_analysis_node
    from pipeline.domain.sa.nodes.sa_project_structure import sa_project_structure_node

    workflow = StateGraph(PipelineState)
    # sa_embedding 노드 제거 — SA artifact ChromaDB 저장 불필요
    workflow.add_node("sa_merge_project", sa_merge_project_node)
    workflow.add_node("component_scheduler", component_scheduler_node)
    workflow.add_node("sa_unified_modeler", sa_unified_modeler_node)
    workflow.add_node("sa_test_analysis", sa_test_analysis_node)
    workflow.add_node("sa_project_structure", sa_project_structure_node)

    workflow.add_edge(START, "sa_merge_project")
    workflow.add_edge("sa_merge_project", "component_scheduler")
    workflow.add_edge("component_scheduler", "sa_unified_modeler")
    workflow.add_edge("sa_unified_modeler", "sa_test_analysis")
    workflow.add_edge("sa_test_analysis", "sa_project_structure")
    workflow.add_edge("sa_project_structure", END)

    return workflow.compile()


def get_pm_pipeline():
    return _PipelineRegistry.get_or_build("pm_pipeline", _build_pm_pipeline)


def get_sa_pipeline():
    return _PipelineRegistry.get_or_build("sa_pipeline", _build_sa_pipeline)


def get_pm_routing_map() -> dict:
    return {
        "first_node": _PM_CHAIN[0],
        "next_nodes": _chain_to_next_nodes(_PM_CHAIN),
        "start_message": "PM 분석 시작 (요구사항 원자화)...",
    }


def get_sa_routing_map() -> dict:
    return {
        "first_node": _SA_CHAIN[0],
        "next_nodes": _chain_to_next_nodes(_SA_CHAIN),
        "start_message": "SA 아키텍처 분석 시작...",
    }


def get_analysis_pipeline(action_type: str = "CREATE"):
    """Full RAG-PM-SA pipeline."""
    from pipeline.domain.rag.nodes.code_chunker import code_chunker_node
    from pipeline.domain.rag.nodes.code_embedding import code_embedding_node
    from pipeline.domain.sa.nodes.forensic_profiler import forensic_profiler_node
    from pipeline.domain.pm.nodes.requirement_analyzer import requirement_analyzer_node
    from pipeline.domain.pm.nodes.stack_planner import stack_planner_node
    from pipeline.domain.pm.nodes.stack_crawling import stack_crawling_node
    from pipeline.domain.pm.nodes.guardian import guardian_node
    from pipeline.domain.sa.nodes.merge_project import sa_merge_project_node
    from pipeline.domain.sa.nodes.component_scheduler import component_scheduler_node
    from pipeline.domain.sa.nodes.sa_unified_modeler import sa_unified_modeler_node
    from pipeline.domain.sa.nodes.sa_test_analysis import sa_test_analysis_node
    from pipeline.domain.sa.nodes.sa_project_structure import sa_project_structure_node

    workflow = StateGraph(PipelineState)
    # RAG Ingest (code indexing — 여전히 구조 파악용으로 유지)
    workflow.add_node("code_chunker", code_chunker_node)
    workflow.add_node("code_embedding", code_embedding_node)
    # Forensic
    workflow.add_node("forensic_profiler", forensic_profiler_node)
    # PM — stack_retriever, pm_embedding 제거
    workflow.add_node("requirement_analyzer", requirement_analyzer_node)
    workflow.add_node("stack_planner", stack_planner_node)
    workflow.add_node("stack_crawling", stack_crawling_node)
    workflow.add_node("guardian", guardian_node)
    # SA — sa_embedding 제거
    workflow.add_node("sa_merge_project", sa_merge_project_node)
    workflow.add_node("component_scheduler", component_scheduler_node)
    workflow.add_node("sa_unified_modeler", sa_unified_modeler_node)
    workflow.add_node("sa_test_analysis", sa_test_analysis_node)
    workflow.add_node("sa_project_structure", sa_project_structure_node)

    # Edges
    workflow.add_edge(START, "code_chunker")
    workflow.add_edge("code_chunker", "code_embedding")
    workflow.add_edge("code_embedding", "forensic_profiler")
    workflow.add_edge("forensic_profiler", "requirement_analyzer")
    workflow.add_edge("requirement_analyzer", "stack_planner")

    # Stack Planner 조건부 루프
    workflow.add_conditional_edges(
        "stack_planner",
        _route_stack_planning,
        {
            "loop": "stack_crawling",
            "finish": "sa_merge_project",
            "error": END,
        }
    )
    workflow.add_edge("stack_crawling", "guardian")
    workflow.add_edge("guardian", "stack_planner")

    workflow.add_edge("sa_merge_project", "component_scheduler")
    workflow.add_edge("component_scheduler", "sa_unified_modeler")
    workflow.add_edge("sa_unified_modeler", "sa_test_analysis")
    workflow.add_edge("sa_test_analysis", "sa_project_structure")
    workflow.add_edge("sa_project_structure", END)

    return workflow.compile()


def get_pipeline_routing_map(action_type: str = "CREATE") -> dict:
    """Compatibility shim."""
    # 전체 분석 파이프라인은 RAG ingest → PM → SA 순서로 노드를 나열한다.
    chain = ("code_chunker", "code_embedding") + _PM_CHAIN + _SA_CHAIN
    return {
        "first_node": chain[0],
        "next_nodes": _chain_to_next_nodes(chain),
        "start_message": "전체 분석 파이프라인 시작...",
    }
