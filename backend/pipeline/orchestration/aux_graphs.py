"""
보조(비분석) 파이프라인.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from pipeline.core.state import PipelineState
from pipeline.domain.chat.idea_chat import idea_chat_node
from pipeline.domain.dev.nodes.backend_agent import develop_backend_agent_node
from pipeline.domain.dev.nodes.backend_qa_agent import develop_backend_qa_agent_node
from pipeline.domain.dev.nodes.branch_pr_orchestrator import develop_branch_pr_orchestrator_node
from pipeline.domain.dev.nodes.domain_gates import (
    develop_backend_domain_gate_node,
    develop_frontend_domain_gate_node,
    develop_uiux_domain_gate_node,
)
from pipeline.domain.dev.nodes.embedding import develop_embedding_node
from pipeline.domain.dev.nodes.frontend_agent import develop_frontend_agent_node
from pipeline.domain.dev.nodes.frontend_qa_agent import develop_frontend_qa_agent_node
from pipeline.domain.dev.nodes.global_sync_gate import develop_global_fe_sync_gate_node
from pipeline.domain.dev.nodes.integration_qa_gate import develop_integration_qa_gate_node
from pipeline.domain.dev.nodes.loop_controller import develop_loop_controller_node
from pipeline.domain.dev.nodes.main_agent import develop_main_agent_node
from pipeline.domain.dev.nodes.uiux_agent import develop_uiux_agent_node
from pipeline.domain.dev.nodes.uiux_qa_agent import develop_uiux_qa_agent_node


class _PipelineRegistry:
    _cache: dict[str, object] = {}

    @classmethod
    def get_or_build(cls, key: str, builder_fn):
        if key not in cls._cache:
            cls._cache[key] = builder_fn()
        return cls._cache[key]


def get_idea_pipeline():
    """아이디어 발전 파이프라인 (START -> idea_chat -> END)"""

    def _build():
        workflow = StateGraph(PipelineState)
        workflow.add_node("idea_chat", idea_chat_node)
        workflow.add_edge(START, "idea_chat")
        workflow.add_edge("idea_chat", END)
        return workflow.compile()

    return _PipelineRegistry.get_or_build("idea_chat", _build)


def get_idea_chat_routing_map() -> dict:
    return {
        "first_node": "idea_chat",
        "next_nodes": {"idea_chat": []},
        "start_message": "아이디어 탐색 중...",
    }


def _route_uiux_domain_gate(state: PipelineState) -> str:
    status = str((state.get("uiux_domain_gate_result", {}) or {}).get("status", "pass")).lower()
    return "retry" if status == "rework" else "pass"


def _route_backend_domain_gate(state: PipelineState) -> str:
    status = str((state.get("backend_domain_gate_result", {}) or {}).get("status", "pass")).lower()
    return "retry" if status == "rework" else "pass"


def _route_frontend_domain_gate(state: PipelineState) -> str:
    status = str((state.get("frontend_domain_gate_result", {}) or {}).get("status", "pass")).lower()
    return "retry" if status == "rework" else "pass"


def _route_global_fe_sync_gate(state: PipelineState) -> str:
    status = str((state.get("global_fe_sync_result", {}) or {}).get("status", "pass")).lower()
    if status == "rework_uiux":
        return "rework_uiux"
    if status == "rework_frontend":
        return "rework_frontend"
    return "pass"


def _route_integration_qa_gate(state: PipelineState) -> str:
    status = str((state.get("integration_qa_result", {}) or {}).get("status", "pass")).lower()
    if status == "rework_uiux":
        return "rework_uiux"
    if status == "rework_backend":
        return "rework_backend"
    if status == "rework_frontend":
        return "rework_frontend"
    return "pass"


def _route_loop_controller(state: PipelineState) -> str:
    action = str(state.get("develop_next_action", "complete")).lower()
    if action == "retry_main":
        return "retry_main"
    return "complete"

"""development pipeline."""

def get_develop_pipeline():
    """Multi-agent development pipeline."""

    def _build():
        workflow = StateGraph(PipelineState)
        workflow.add_node("develop_main_agent", develop_main_agent_node)
        workflow.add_node("develop_uiux_agent", develop_uiux_agent_node)
        workflow.add_node("develop_backend_agent", develop_backend_agent_node)
        workflow.add_node("develop_frontend_agent", develop_frontend_agent_node)
        workflow.add_node("develop_uiux_qa_agent", develop_uiux_qa_agent_node)
        workflow.add_node("develop_backend_qa_agent", develop_backend_qa_agent_node)
        workflow.add_node("develop_frontend_qa_agent", develop_frontend_qa_agent_node)
        workflow.add_node("develop_uiux_domain_gate", develop_uiux_domain_gate_node)
        workflow.add_node("develop_backend_domain_gate", develop_backend_domain_gate_node)
        workflow.add_node("develop_frontend_domain_gate", develop_frontend_domain_gate_node)
        workflow.add_node("develop_global_fe_sync_gate", develop_global_fe_sync_gate_node)
        workflow.add_node("develop_integration_qa_gate", develop_integration_qa_gate_node)
        workflow.add_node("develop_branch_pr_orchestrator", develop_branch_pr_orchestrator_node)
        workflow.add_node("develop_embedding", develop_embedding_node)
        workflow.add_node("develop_loop_controller", develop_loop_controller_node)

        workflow.add_edge(START, "develop_main_agent")

        workflow.add_edge("develop_main_agent", "develop_uiux_agent")
        workflow.add_edge("develop_main_agent", "develop_backend_agent")
        workflow.add_edge("develop_main_agent", "develop_frontend_agent")

        workflow.add_edge("develop_uiux_agent", "develop_uiux_qa_agent")
        workflow.add_edge("develop_uiux_qa_agent", "develop_uiux_domain_gate")
        workflow.add_conditional_edges(
            "develop_uiux_domain_gate",
            _route_uiux_domain_gate,
            {
                "retry": "develop_uiux_agent",
                "pass": "develop_global_fe_sync_gate",
            },
        )

        workflow.add_edge("develop_backend_agent", "develop_backend_qa_agent")
        workflow.add_edge("develop_backend_qa_agent", "develop_backend_domain_gate")
        workflow.add_conditional_edges(
            "develop_backend_domain_gate",
            _route_backend_domain_gate,
            {
                "retry": "develop_backend_agent",
                "pass": "develop_global_fe_sync_gate",
            },
        )

        workflow.add_edge("develop_frontend_agent", "develop_frontend_qa_agent")
        workflow.add_edge("develop_frontend_qa_agent", "develop_frontend_domain_gate")
        workflow.add_conditional_edges(
            "develop_frontend_domain_gate",
            _route_frontend_domain_gate,
            {
                "retry": "develop_frontend_agent",
                "pass": "develop_global_fe_sync_gate",
            },
        )

        workflow.add_conditional_edges(
            "develop_global_fe_sync_gate",
            _route_global_fe_sync_gate,
            {
                "rework_uiux": "develop_uiux_agent",
                "rework_frontend": "develop_frontend_agent",
                "pass": "develop_integration_qa_gate",
            },
        )

        workflow.add_conditional_edges(
            "develop_integration_qa_gate",
            _route_integration_qa_gate,
            {
                "rework_uiux": "develop_uiux_agent",
                "rework_backend": "develop_backend_agent",
                "rework_frontend": "develop_frontend_agent",
                "pass": "develop_branch_pr_orchestrator",
            },
        )

        workflow.add_edge("develop_branch_pr_orchestrator", "develop_embedding")
        workflow.add_edge("develop_embedding", "develop_loop_controller")
        workflow.add_conditional_edges(
            "develop_loop_controller",
            _route_loop_controller,
            {
                "retry_main": "develop_main_agent",
                "complete": END,
            },
        )
        return workflow.compile()

    return _PipelineRegistry.get_or_build("develop_pipeline", _build)


def get_develop_routing_map() -> dict:
    return {
        "first_node": "develop_main_agent",
        "next_nodes": {
            "develop_main_agent": [
                "develop_uiux_agent",
                "develop_backend_agent",
                "develop_frontend_agent",
            ],
            "develop_uiux_agent": ["develop_uiux_qa_agent"],
            "develop_uiux_qa_agent": ["develop_uiux_domain_gate"],
            "develop_uiux_domain_gate": ["develop_uiux_agent", "develop_global_fe_sync_gate"],
            "develop_backend_agent": ["develop_backend_qa_agent"],
            "develop_backend_qa_agent": ["develop_backend_domain_gate"],
            "develop_backend_domain_gate": ["develop_backend_agent", "develop_global_fe_sync_gate"],
            "develop_frontend_agent": ["develop_frontend_qa_agent"],
            "develop_frontend_qa_agent": ["develop_frontend_domain_gate"],
            "develop_frontend_domain_gate": ["develop_frontend_agent", "develop_global_fe_sync_gate"],
            "develop_global_fe_sync_gate": ["develop_frontend_agent", "develop_uiux_agent", "develop_integration_qa_gate"],
            "develop_integration_qa_gate": [
                "develop_uiux_agent",
                "develop_backend_agent",
                "develop_frontend_agent",
                "develop_branch_pr_orchestrator",
            ],
            "develop_branch_pr_orchestrator": ["develop_embedding"],
            "develop_embedding": ["develop_loop_controller"],
            "develop_loop_controller": ["develop_main_agent"],
        },
        "start_message": "Develop pipeline starting...",
    }
