"""
LangGraph builder for the navi_v3 Dev Tracking pipeline.
"""

from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from pipeline.core.state import PipelineState
from pipeline.domain.dev_tracking import nodes


_DEV_TRACKING_CHAIN = (
    "dev_task_planner",
    "branch_fetcher",
    "reverse_analyzer",
    "code_inventory_builder",
    "forensic_profiler",
    "spec_loader",
    "gap_analyzer",
    "dev_knowledge_loader",
    "intent_classifier",
    "milestone_tracker",
    "pm_report_generator",
    "pr_comment_notifier",
    "pr_status_check_updater",
    "task_coordinator",
    "analysis_persister",
    "develop_embedding",
    "develop_loop_controller",
)

_BLOCKING_ACTIONS = {"blocked", "pm_approval_pending"}


class _PipelineRegistry:
    _cache: dict[str, object] = {}

    @classmethod
    def get_or_build(cls, key: str, builder_fn):
        if key not in cls._cache:
            cls._cache[key] = builder_fn()
        return cls._cache[key]


def _with_timeline(
    name: str,
    fn: Callable[..., dict[str, Any]],
    *,
    uses_shared_db: bool = False,
):
    def _node(state: PipelineState) -> dict[str, Any]:
        state_dict = dict(state)
        if uses_shared_db:
            result = fn(state_dict, state_dict.get("_shared_db"))
        else:
            result = fn(state_dict)
        timeline = list(state_dict.get("timeline") or [])
        timeline.append(
            {
                "node": name,
                "status": result.get("status", ""),
                "next_action": result.get("dev_tracking_next_action", ""),
                "error_type": result.get("error_type", ""),
            }
        )
        return {**result, "timeline": timeline}

    return _node


def _route_after_step(state: PipelineState) -> str:
    if state.get("dev_tracking_next_action") in _BLOCKING_ACTIONS:
        return "end"
    return "continue"


def _route_after_gap_analysis(state: PipelineState) -> str:
    if state.get("dev_tracking_next_action") in _BLOCKING_ACTIONS:
        return "end"
    if state.get("dev_tracking_next_action") == "intent_classifier":
        return "intent"
    return "milestone"


def _build_dev_tracking_pipeline():
    workflow = StateGraph(PipelineState)

    workflow.add_node("dev_task_planner", _with_timeline("dev_task_planner", nodes.dev_task_planner))
    workflow.add_node("branch_fetcher", _with_timeline("branch_fetcher", nodes.branch_fetcher))
    workflow.add_node("reverse_analyzer", _with_timeline("reverse_analyzer", nodes.reverse_analyzer))
    workflow.add_node("code_inventory_builder", _with_timeline("code_inventory_builder", nodes.code_inventory_builder))
    workflow.add_node("forensic_profiler", _with_timeline("forensic_profiler", nodes.forensic_profiler))
    workflow.add_node("spec_loader", _with_timeline("spec_loader", nodes.spec_loader, uses_shared_db=True))
    workflow.add_node("gap_analyzer", _with_timeline("gap_analyzer", nodes.gap_analyzer))
    workflow.add_node(
        "dev_knowledge_loader",
        _with_timeline("dev_knowledge_loader", nodes.dev_knowledge_loader, uses_shared_db=True),
    )
    workflow.add_node("intent_classifier", _with_timeline("intent_classifier", nodes.intent_classifier))
    workflow.add_node("milestone_tracker", _with_timeline("milestone_tracker", nodes.milestone_tracker))
    workflow.add_node("pm_report_generator", _with_timeline("pm_report_generator", nodes.pm_report_generator))
    workflow.add_node("pr_comment_notifier", _with_timeline("pr_comment_notifier", nodes.pr_comment_notifier))
    workflow.add_node(
        "pr_status_check_updater",
        _with_timeline("pr_status_check_updater", nodes.pr_status_check_updater),
    )
    workflow.add_node("task_coordinator", _with_timeline("task_coordinator", nodes.task_coordinator))
    workflow.add_node(
        "analysis_persister",
        _with_timeline("analysis_persister", nodes.analysis_persister, uses_shared_db=True),
    )
    workflow.add_node(
        "develop_embedding",
        _with_timeline("develop_embedding", nodes.develop_embedding, uses_shared_db=True),
    )
    workflow.add_node("develop_loop_controller", _with_timeline("develop_loop_controller", nodes.develop_loop_controller))

    workflow.add_edge(START, "dev_task_planner")
    workflow.add_conditional_edges(
        "dev_task_planner",
        _route_after_step,
        {"continue": "branch_fetcher", "end": END},
    )
    workflow.add_conditional_edges(
        "branch_fetcher",
        _route_after_step,
        {"continue": "reverse_analyzer", "end": END},
    )
    workflow.add_edge("reverse_analyzer", "code_inventory_builder")
    workflow.add_conditional_edges(
        "code_inventory_builder",
        _route_after_step,
        {"continue": "forensic_profiler", "end": END},
    )
    workflow.add_edge("forensic_profiler", "spec_loader")
    workflow.add_edge("spec_loader", "gap_analyzer")
    workflow.add_conditional_edges(
        "gap_analyzer",
        _route_after_gap_analysis,
        {"intent": "dev_knowledge_loader", "milestone": "milestone_tracker", "end": END},
    )
    workflow.add_edge("dev_knowledge_loader", "intent_classifier")
    workflow.add_edge("intent_classifier", "milestone_tracker")
    workflow.add_edge("milestone_tracker", "pm_report_generator")
    workflow.add_edge("pm_report_generator", "pr_comment_notifier")
    workflow.add_edge("pr_comment_notifier", "pr_status_check_updater")
    workflow.add_edge("pr_status_check_updater", "task_coordinator")
    workflow.add_edge("task_coordinator", "analysis_persister")
    workflow.add_edge("analysis_persister", "develop_embedding")
    workflow.add_edge("develop_embedding", "develop_loop_controller")
    workflow.add_edge("develop_loop_controller", END)

    return workflow.compile()


def get_dev_tracking_pipeline():
    return _PipelineRegistry.get_or_build("dev_tracking_pipeline", _build_dev_tracking_pipeline)


def get_dev_tracking_routing_map() -> dict:
    return {
        "first_node": _DEV_TRACKING_CHAIN[0],
        "next_nodes": {
            "dev_task_planner": ["branch_fetcher"],
            "branch_fetcher": ["reverse_analyzer"],
            "reverse_analyzer": ["code_inventory_builder"],
            "code_inventory_builder": ["forensic_profiler"],
            "forensic_profiler": ["spec_loader"],
            "spec_loader": ["gap_analyzer"],
            "gap_analyzer": ["dev_knowledge_loader", "milestone_tracker"],
            "dev_knowledge_loader": ["intent_classifier"],
            "intent_classifier": ["milestone_tracker"],
            "milestone_tracker": ["pm_report_generator"],
            "pm_report_generator": ["pr_comment_notifier"],
            "pr_comment_notifier": ["pr_status_check_updater"],
            "pr_status_check_updater": ["task_coordinator"],
            "task_coordinator": ["analysis_persister"],
            "analysis_persister": ["develop_embedding"],
            "develop_embedding": ["develop_loop_controller"],
            "develop_loop_controller": [],
        },
        "start_message": "Dev Tracking PR 분석 시작...",
    }
