"""
Modular Analysis graphs (Scan, PM, SA).
"""

from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from pipeline.core.state import PipelineState
from pipeline.core.utils import active_usage_log

# Node Chain Definitions
_SCAN_CHAIN = ("system_scan",)

_PM_CHAIN = (
    "requirement_analyzer",
    "stack_retriever",
    "stack_planner",
    "pm_embedding",
)

_SA_CHAIN = (
    "sa_merge_project",
    "component_scheduler",
    "sa_unified_modeler",
    "sa_advisor",
    "sa_embedding",
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
    planner_output = state.get("stack_planner_output", {})
    mappings = planner_output.get("stack_mapping", [])
    
    if any(m.get("status") == "PENDING_CRAWL" for m in mappings):
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


def _build_scan_pipeline():
    from pipeline.domain.rag.nodes.system_scanner import system_scan_node
    workflow = StateGraph(PipelineState)
    workflow.add_node("system_scan", system_scan_node)
    workflow.add_edge(START, "system_scan")
    workflow.add_edge("system_scan", END)
    return workflow.compile()


def _build_pm_pipeline():
    from pipeline.domain.pm.nodes.requirement_analyzer import requirement_analyzer_node
    from pipeline.domain.pm.nodes.stack_planner import stack_planner_node
    from pipeline.domain.pm.nodes.stack_crawling import stack_crawling_node
    from pipeline.domain.pm.nodes.guardian import guardian_node
    from pipeline.domain.pm.nodes.stack_embedding import stack_embedding_node
    from pipeline.domain.pm.nodes.stack_retriever import stack_retriever_node
    from pipeline.domain.pm.nodes.pm_embedding import pm_embedding_node

    workflow = StateGraph(PipelineState)
    
    # Nodes (Registered directly - wrapped by @pipeline_node)
    workflow.add_node("requirement_analyzer", requirement_analyzer_node)
    workflow.add_node("stack_planner", stack_planner_node)
    workflow.add_node("stack_crawling", stack_crawling_node)
    workflow.add_node("guardian", guardian_node)
    workflow.add_node("stack_embedding", stack_embedding_node)
    workflow.add_node("stack_retriever", stack_retriever_node)
    workflow.add_node("pm_embedding", pm_embedding_node)

    # Edges
    workflow.add_edge(START, "requirement_analyzer")
    workflow.add_edge("requirement_analyzer", "stack_retriever")
    workflow.add_edge("stack_retriever", "stack_planner")
    
    # Conditional Loop Edge
    workflow.add_conditional_edges(
        "stack_planner",
        _route_stack_planning,
        {
            "loop": "stack_crawling",
            "finish": "pm_embedding",
            "error": END
        }
    )
    
    # Feedback loop
    workflow.add_edge("stack_crawling", "guardian")
    workflow.add_edge("guardian", "stack_embedding")
    workflow.add_edge("stack_embedding", "stack_planner")
    
    # PM Embedding 이후 종료
    workflow.add_conditional_edges(
        "pm_embedding",
        _route_pm_integration,
        {
            "continue": END,
            "error": END
        }
    )
    
    return workflow.compile()


def _build_sa_pipeline():
    from pipeline.domain.sa.nodes.merge_project import sa_merge_project_node
    from pipeline.domain.sa.nodes.component_scheduler import component_scheduler_node
    from pipeline.domain.sa.nodes.sa_unified_modeler import sa_unified_modeler_node
    from pipeline.domain.sa.nodes.sa_advisor import sa_advisor_node
    from pipeline.domain.sa.nodes.sa_embedding import sa_embedding_node

    workflow = StateGraph(PipelineState)
    workflow.add_node("sa_merge_project", sa_merge_project_node)
    workflow.add_node("component_scheduler", component_scheduler_node)
    workflow.add_node("sa_unified_modeler", sa_unified_modeler_node)
    workflow.add_node("sa_advisor", sa_advisor_node)
    workflow.add_node("sa_embedding", sa_embedding_node)

    workflow.add_edge(START, "sa_merge_project")
    workflow.add_edge("sa_merge_project", "component_scheduler")
    workflow.add_edge("component_scheduler", "sa_unified_modeler")
    workflow.add_edge("sa_unified_modeler", "sa_advisor")
    workflow.add_edge("sa_advisor", "sa_embedding")
    workflow.add_edge("sa_embedding", END)

    return workflow.compile()


def get_scan_pipeline():
    return _PipelineRegistry.get_or_build("scan_pipeline", _build_scan_pipeline)


def get_pm_pipeline():
    return _PipelineRegistry.get_or_build("pm_pipeline", _build_pm_pipeline)


def get_sa_pipeline():
    return _PipelineRegistry.get_or_build("sa_pipeline", _build_sa_pipeline)


def get_scan_routing_map() -> dict:
    return {
        "first_node": _SCAN_CHAIN[0],
        "next_nodes": {},
        "start_message": "프로젝트 코드 분석 시작...",
    }


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
    """Full PM-SA pipeline (pm_analysis/sa_analysis removed, advisor handles QA)."""
    from pipeline.domain.rag.nodes.system_scanner import system_scan_node
    from pipeline.domain.pm.nodes.requirement_analyzer import requirement_analyzer_node
    from pipeline.domain.pm.nodes.stack_retriever import stack_retriever_node
    from pipeline.domain.pm.nodes.stack_planner import stack_planner_node
    from pipeline.domain.pm.nodes.pm_embedding import pm_embedding_node
    from pipeline.domain.sa.nodes.merge_project import sa_merge_project_node
    from pipeline.domain.sa.nodes.component_scheduler import component_scheduler_node
    from pipeline.domain.sa.nodes.sa_unified_modeler import sa_unified_modeler_node
    from pipeline.domain.sa.nodes.sa_advisor import sa_advisor_node
    from pipeline.domain.sa.nodes.sa_embedding import sa_embedding_node

    workflow = StateGraph(PipelineState)
    # Scan
    workflow.add_node("system_scan", system_scan_node)
    # PM
    workflow.add_node("requirement_analyzer", requirement_analyzer_node)
    workflow.add_node("stack_retriever", stack_retriever_node)
    workflow.add_node("stack_planner", stack_planner_node)
    workflow.add_node("pm_embedding", pm_embedding_node)
    # SA
    workflow.add_node("sa_merge_project", sa_merge_project_node)
    workflow.add_node("component_scheduler", component_scheduler_node)
    workflow.add_node("sa_unified_modeler", sa_unified_modeler_node)
    workflow.add_node("sa_advisor", sa_advisor_node)
    workflow.add_node("sa_embedding", sa_embedding_node)

    # Edges
    workflow.add_edge(START, "system_scan")
    workflow.add_edge("system_scan", "requirement_analyzer")
    workflow.add_edge("requirement_analyzer", "stack_retriever")
    workflow.add_edge("stack_retriever", "stack_planner")
    workflow.add_edge("stack_planner", "pm_embedding")
    workflow.add_edge("pm_embedding", "sa_merge_project")
    workflow.add_edge("sa_merge_project", "component_scheduler")
    workflow.add_edge("component_scheduler", "sa_unified_modeler")
    workflow.add_edge("sa_unified_modeler", "sa_advisor")
    workflow.add_edge("sa_advisor", "sa_embedding")
    workflow.add_edge("sa_embedding", END)
    
    return workflow.compile()


def get_pipeline_routing_map(action_type: str = "CREATE") -> dict:
    """Compatibility shim."""
    chain = _SCAN_CHAIN + _PM_CHAIN + _SA_CHAIN
    return {
        "first_node": chain[0],
        "next_nodes": _chain_to_next_nodes(chain),
        "start_message": "전체 분석 파이프라인 시작...",
    }
