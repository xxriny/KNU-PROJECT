"""
Modular Analysis graphs (Scan, PM, SA).
"""

from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from pipeline.core.state import PipelineState

# PM nodes
from pipeline.domain.pm.nodes.pm_phase1 import atomizer_node
from pipeline.domain.pm.nodes.pm_phase2 import prioritizer_node
from pipeline.domain.pm.nodes.pm_phase3 import rtm_builder_node
from pipeline.domain.pm.nodes.pm_phase4 import semantic_indexer_node
from pipeline.domain.pm.nodes.pm_phase5 import context_spec_node

# SA nodes
from pipeline.domain.sa.nodes.sa_phase1 import sa_phase1_node
from pipeline.domain.sa.nodes.merge_project import sa_merge_project_node
from pipeline.domain.sa.nodes.sa_phase2 import sa_phase2_node
from pipeline.domain.sa.nodes.sa_phase3 import sa_phase3_node
from pipeline.domain.sa.nodes.sa_phase4 import sa_phase4_node
from pipeline.domain.sa.nodes.sa_phase5 import sa_phase5_node
from pipeline.domain.sa.nodes.sa_phase6 import sa_phase6_node
from pipeline.domain.sa.nodes.sa_phase7 import sa_phase7_node
from pipeline.domain.sa.nodes.sa_phase8 import sa_phase8_node


_SCAN_CHAIN: tuple[str, ...] = (
    "sa_phase1",
)

_PM_CHAIN: tuple[str, ...] = (
    "atomizer",
    "prioritizer",
    "rtm_builder",
    "semantic_indexer",
    "context_spec",
)

_SA_CHAIN: tuple[str, ...] = (
    "sa_merge_project",
    "sa_phase2",
    "sa_phase3",
    "sa_phase4",
    "sa_phase5",
    "sa_phase6",
    "sa_phase7",
    "sa_phase8",
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
        # SA phases stop only on Error
        for phase in [f"sa_phase{i}" for i in range(1, 9)]:
            phase_data = state.get(phase)
            if isinstance(phase_data, dict) and phase_data.get("status") == "Error":
                return "error"
    return "continue"


def _chain_to_next_nodes(chain: tuple[str, ...]) -> dict[str, list[str]]:
    return {node: ([chain[i + 1]] if i + 1 < len(chain) else []) for i, node in enumerate(chain)}


def _build_scan_pipeline():
    workflow = StateGraph(PipelineState)
    workflow.add_node("sa_phase1", sa_phase1_node)
    workflow.add_edge(START, "sa_phase1")
    workflow.add_edge("sa_phase1", END)
    return workflow.compile()


def _build_pm_pipeline():
    workflow = StateGraph(PipelineState)
    workflow.add_node("atomizer", atomizer_node)
    workflow.add_node("prioritizer", prioritizer_node)
    workflow.add_node("rtm_builder", rtm_builder_node)
    workflow.add_node("semantic_indexer", semantic_indexer_node)
    workflow.add_node("context_spec", context_spec_node)

    workflow.add_edge(START, _PM_CHAIN[0])
    for src, dst in zip(_PM_CHAIN[:-1], _PM_CHAIN[1:]):
        workflow.add_conditional_edges(src, _check_status, {"continue": dst, "error": END})
    workflow.add_edge(_PM_CHAIN[-1], END)
    return workflow.compile()


def _build_sa_pipeline():
    workflow = StateGraph(PipelineState)
    workflow.add_node("sa_merge_project", sa_merge_project_node)
    workflow.add_node("sa_phase2", sa_phase2_node)
    workflow.add_node("sa_phase3", sa_phase3_node)
    workflow.add_node("sa_phase4", sa_phase4_node)
    workflow.add_node("sa_phase5", sa_phase5_node)
    workflow.add_node("sa_phase6", sa_phase6_node)
    workflow.add_node("sa_phase7", sa_phase7_node)
    workflow.add_node("sa_phase8", sa_phase8_node)

    workflow.add_edge(START, _SA_CHAIN[0])
    for src, dst in zip(_SA_CHAIN[:-1], _SA_CHAIN[1:]):
        workflow.add_conditional_edges(src, _check_status, {"continue": dst, "error": END})
    workflow.add_edge(_SA_CHAIN[-1], END)
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
    """Compatibility shim: returns full chain for now."""
    workflow = StateGraph(PipelineState)
    # Scan
    workflow.add_node("sa_phase1", sa_phase1_node)
    # PM
    workflow.add_node("atomizer", atomizer_node)
    workflow.add_node("prioritizer", prioritizer_node)
    workflow.add_node("rtm_builder", rtm_builder_node)
    workflow.add_node("semantic_indexer", semantic_indexer_node)
    workflow.add_node("context_spec", context_spec_node)
    # SA
    workflow.add_node("sa_merge_project", sa_merge_project_node)
    workflow.add_node("sa_phase2", sa_phase2_node)
    workflow.add_node("sa_phase3", sa_phase3_node)
    workflow.add_node("sa_phase4", sa_phase4_node)
    workflow.add_node("sa_phase5", sa_phase5_node)
    workflow.add_node("sa_phase6", sa_phase6_node)
    workflow.add_node("sa_phase7", sa_phase7_node)
    workflow.add_node("sa_phase8", sa_phase8_node)

    full_chain = _SCAN_CHAIN + _PM_CHAIN + _SA_CHAIN
    workflow.add_edge(START, full_chain[0])
    for src, dst in zip(full_chain[:-1], full_chain[1:]):
        workflow.add_conditional_edges(src, _check_status, {"continue": dst, "error": END})
    workflow.add_edge(full_chain[-1], END)
    return workflow.compile()


def get_pipeline_routing_map(action_type: str = "CREATE") -> dict:
    """Compatibility shim."""
    chain = _SCAN_CHAIN + _PM_CHAIN + _SA_CHAIN
    return {
        "first_node": chain[0],
        "next_nodes": _chain_to_next_nodes(chain),
        "start_message": "전체 분석 파이프라인 시작...",
    }
