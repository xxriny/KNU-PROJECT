"""
보조(비분석) 파이프라인.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from pipeline.core.state import PipelineState
from pipeline.domain.chat.idea_chat import idea_chat_node
from pipeline.domain.dev.nodes.backend_agent import develop_backend_agent_node
from pipeline.domain.dev.nodes.backend_codegen import develop_backend_codegen_node
from pipeline.domain.dev.nodes.backend_codegen_verifier import (
    develop_backend_codegen_repair_node,
    develop_backend_codegen_reverifier_node,
    develop_backend_codegen_verifier_node,
    develop_backend_runtime_blocker_node,
)
from pipeline.domain.dev.nodes.backend_qa_agent import develop_backend_qa_agent_node
from pipeline.domain.dev.nodes.branch_pr_orchestrator import develop_branch_pr_orchestrator_node
from pipeline.domain.dev.nodes.domain_gates import (
    develop_backend_domain_gate_node,
    develop_frontend_domain_gate_node,
    develop_uiux_domain_gate_node,
)
from pipeline.domain.dev.nodes.embedding import develop_embedding_node
from pipeline.domain.dev.nodes.frontend_agent import develop_frontend_agent_node
from pipeline.domain.dev.nodes.frontend_codegen import develop_frontend_codegen_node
from pipeline.domain.dev.nodes.frontend_codegen_verifier import (
    develop_frontend_codegen_repair_node,
    develop_frontend_codegen_reverifier_node,
    develop_frontend_codegen_verifier_node,
    develop_frontend_runtime_blocker_node,
)
from pipeline.domain.dev.nodes.frontend_qa_agent import develop_frontend_qa_agent_node
from pipeline.domain.dev.nodes.fullstack_runtime_verifier import develop_fullstack_runtime_verifier_node
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


def _selected_domains(state: PipelineState) -> set[str]:
    plan = state.get("develop_main_plan", {}) or {}
    selected = plan.get("selected_domains") or ["uiux", "backend", "frontend"]
    return {str(domain).lower() for domain in selected}


def _route_after_main_agent(state: PipelineState) -> str:
    selected = _selected_domains(state)
    if "uiux" in selected:
        return "uiux"
    if "backend" in selected:
        return "backend"
    if "frontend" in selected:
        return "frontend"
    return "complete"


def _route_after_uiux_gate(state: PipelineState) -> str:
    status = str((state.get("uiux_domain_gate_result", {}) or {}).get("status", "pass")).lower()
    if status == "rework":
        return "retry"
    selected = _selected_domains(state)
    if "backend" in selected:
        return "backend"
    if "frontend" in selected:
        return "frontend"
    return "complete"


def _route_after_backend_runtime(state: PipelineState) -> str:
    selected = _selected_domains(state)
    return "frontend" if "frontend" in selected else "integration"


def _route_backend_codegen_verification(state: PipelineState) -> str:
    codegen_status = str((state.get("backend_codegen_result", {}) or {}).get("status", "")).lower()
    if codegen_status == "error":
        return "block"
    status = str((state.get("backend_codegen_verification", {}) or {}).get("status", "skipped")).lower()
    return "repair" if status == "failed" else "pass"


def _route_backend_codegen_repair(state: PipelineState) -> str:
    status = str((state.get("backend_codegen_repair_result", {}) or {}).get("status", "")).lower()
    return "reverify" if status in {"repaired", "no_changes"} else "block"


def _route_backend_codegen_reverification(state: PipelineState) -> str:
    status = str((state.get("backend_codegen_reverify_result", {}) or {}).get("status", "skipped")).lower()
    return "block" if status == "failed" else "pass"


def _route_frontend_domain_gate(state: PipelineState) -> str:
    status = str((state.get("frontend_domain_gate_result", {}) or {}).get("status", "pass")).lower()
    return "retry" if status == "rework" else "pass"


def _route_frontend_codegen_verification(state: PipelineState) -> str:
    codegen_status = str((state.get("frontend_codegen_result", {}) or {}).get("status", "")).lower()
    if codegen_status == "error":
        return "block"
    status = str((state.get("frontend_codegen_verification", {}) or {}).get("status", "skipped")).lower()
    return "repair" if status == "failed" else "pass"


def _route_frontend_codegen_repair(state: PipelineState) -> str:
    status = str((state.get("frontend_codegen_repair_result", {}) or {}).get("status", "")).lower()
    return "reverify" if status in {"repaired", "no_changes"} else "block"


def _route_frontend_codegen_reverification(state: PipelineState) -> str:
    status = str((state.get("frontend_codegen_reverify_result", {}) or {}).get("status", "skipped")).lower()
    return "block" if status == "failed" else "pass"


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
        workflow.add_node("develop_backend_codegen", develop_backend_codegen_node)
        workflow.add_node("develop_backend_codegen_verifier", develop_backend_codegen_verifier_node)
        workflow.add_node("develop_backend_codegen_repair", develop_backend_codegen_repair_node)
        workflow.add_node("develop_backend_codegen_reverifier", develop_backend_codegen_reverifier_node)
        workflow.add_node("develop_backend_runtime_blocker", develop_backend_runtime_blocker_node)
        workflow.add_node("develop_frontend_agent", develop_frontend_agent_node)
        workflow.add_node("develop_frontend_codegen", develop_frontend_codegen_node)
        workflow.add_node("develop_frontend_codegen_verifier", develop_frontend_codegen_verifier_node)
        workflow.add_node("develop_frontend_codegen_repair", develop_frontend_codegen_repair_node)
        workflow.add_node("develop_frontend_codegen_reverifier", develop_frontend_codegen_reverifier_node)
        workflow.add_node("develop_frontend_runtime_blocker", develop_frontend_runtime_blocker_node)
        workflow.add_node("develop_uiux_qa_agent", develop_uiux_qa_agent_node)
        workflow.add_node("develop_backend_qa_agent", develop_backend_qa_agent_node)
        workflow.add_node("develop_frontend_qa_agent", develop_frontend_qa_agent_node)
        workflow.add_node("develop_uiux_domain_gate", develop_uiux_domain_gate_node)
        workflow.add_node("develop_backend_domain_gate", develop_backend_domain_gate_node)
        workflow.add_node("develop_frontend_domain_gate", develop_frontend_domain_gate_node)
        workflow.add_node("develop_global_fe_sync_gate", develop_global_fe_sync_gate_node)
        workflow.add_node("develop_fullstack_runtime_verifier", develop_fullstack_runtime_verifier_node)
        workflow.add_node("develop_integration_qa_gate", develop_integration_qa_gate_node)
        workflow.add_node("develop_branch_pr_orchestrator", develop_branch_pr_orchestrator_node)
        workflow.add_node("develop_embedding", develop_embedding_node)
        workflow.add_node("develop_loop_controller", develop_loop_controller_node)

        workflow.add_edge(START, "develop_main_agent")
        workflow.add_conditional_edges(
            "develop_main_agent",
            _route_after_main_agent,
            {
                "uiux": "develop_uiux_agent",
                "backend": "develop_backend_agent",
                "frontend": "develop_frontend_agent",
                "complete": "develop_branch_pr_orchestrator",
            },
        )

        workflow.add_edge("develop_uiux_agent", "develop_uiux_qa_agent")
        workflow.add_edge("develop_uiux_qa_agent", "develop_uiux_domain_gate")
        workflow.add_conditional_edges(
            "develop_uiux_domain_gate",
            _route_after_uiux_gate,
            {
                "retry": "develop_uiux_agent",
                "backend": "develop_backend_agent",
                "frontend": "develop_frontend_agent",
                "complete": "develop_branch_pr_orchestrator",
            },
        )

        workflow.add_edge("develop_backend_agent", "develop_backend_qa_agent")
        workflow.add_edge("develop_backend_qa_agent", "develop_backend_domain_gate")
        workflow.add_conditional_edges(
            "develop_backend_domain_gate",
            _route_backend_domain_gate,
            {
                "retry": "develop_backend_agent",
                "pass": "develop_backend_codegen",
            },
        )
        workflow.add_edge("develop_backend_codegen", "develop_backend_codegen_verifier")
        workflow.add_conditional_edges(
            "develop_backend_codegen_verifier",
            _route_backend_codegen_verification,
            {
                "pass": "develop_after_backend_runtime",
                "repair": "develop_backend_codegen_repair",
                "block": "develop_backend_runtime_blocker",
            },
        )
        workflow.add_conditional_edges(
            "develop_backend_codegen_repair",
            _route_backend_codegen_repair,
            {
                "reverify": "develop_backend_codegen_reverifier",
                "block": "develop_backend_runtime_blocker",
            },
        )
        workflow.add_conditional_edges(
            "develop_backend_codegen_reverifier",
            _route_backend_codegen_reverification,
            {
                "pass": "develop_after_backend_runtime",
                "block": "develop_backend_runtime_blocker",
            },
        )
        workflow.add_edge("develop_backend_runtime_blocker", END)
        workflow.add_node("develop_after_backend_runtime", lambda state: {})
        workflow.add_conditional_edges(
            "develop_after_backend_runtime",
            _route_after_backend_runtime,
            {
                "frontend": "develop_frontend_agent",
                "integration": "develop_integration_qa_gate",
            },
        )

        workflow.add_edge("develop_frontend_agent", "develop_frontend_qa_agent")
        workflow.add_edge("develop_frontend_qa_agent", "develop_frontend_domain_gate")
        workflow.add_conditional_edges(
            "develop_frontend_domain_gate",
            _route_frontend_domain_gate,
            {
                "retry": "develop_frontend_agent",
                "pass": "develop_frontend_codegen",
            },
        )
        workflow.add_edge("develop_frontend_codegen", "develop_frontend_codegen_verifier")
        workflow.add_conditional_edges(
            "develop_frontend_codegen_verifier",
            _route_frontend_codegen_verification,
            {
                "pass": "develop_global_fe_sync_gate",
                "repair": "develop_frontend_codegen_repair",
                "block": "develop_frontend_runtime_blocker",
            },
        )
        workflow.add_conditional_edges(
            "develop_frontend_codegen_repair",
            _route_frontend_codegen_repair,
            {
                "reverify": "develop_frontend_codegen_reverifier",
                "block": "develop_frontend_runtime_blocker",
            },
        )
        workflow.add_conditional_edges(
            "develop_frontend_codegen_reverifier",
            _route_frontend_codegen_reverification,
            {
                "pass": "develop_global_fe_sync_gate",
                "block": "develop_frontend_runtime_blocker",
            },
        )
        workflow.add_edge("develop_frontend_runtime_blocker", END)

        workflow.add_conditional_edges(
            "develop_global_fe_sync_gate",
            _route_global_fe_sync_gate,
            {
                "rework_uiux": "develop_uiux_agent",
                "rework_frontend": "develop_frontend_agent",
                "pass": "develop_fullstack_runtime_verifier",
            },
        )
        workflow.add_edge("develop_fullstack_runtime_verifier", "develop_integration_qa_gate")

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
            "develop_main_agent": ["develop_uiux_agent", "develop_backend_agent", "develop_frontend_agent", "develop_branch_pr_orchestrator"],
            "develop_uiux_agent": ["develop_uiux_qa_agent"],
            "develop_uiux_qa_agent": ["develop_uiux_domain_gate"],
            "develop_uiux_domain_gate": ["develop_uiux_agent", "develop_backend_agent", "develop_frontend_agent", "develop_branch_pr_orchestrator"],
            "develop_backend_agent": ["develop_backend_qa_agent"],
            "develop_backend_qa_agent": ["develop_backend_domain_gate"],
            "develop_backend_domain_gate": ["develop_backend_agent", "develop_backend_codegen"],
            "develop_backend_codegen": ["develop_backend_codegen_verifier"],
            "develop_backend_codegen_verifier": ["develop_after_backend_runtime", "develop_backend_codegen_repair"],
            "develop_backend_codegen_repair": ["develop_backend_codegen_reverifier", "develop_backend_runtime_blocker"],
            "develop_backend_codegen_reverifier": ["develop_after_backend_runtime", "develop_backend_runtime_blocker"],
            "develop_after_backend_runtime": ["develop_frontend_agent", "develop_integration_qa_gate"],
            "develop_backend_runtime_blocker": [],
            "develop_frontend_agent": ["develop_frontend_qa_agent"],
            "develop_frontend_qa_agent": ["develop_frontend_domain_gate"],
            "develop_frontend_domain_gate": ["develop_frontend_agent", "develop_frontend_codegen"],
            "develop_frontend_codegen": ["develop_frontend_codegen_verifier"],
            "develop_frontend_codegen_verifier": ["develop_global_fe_sync_gate", "develop_frontend_codegen_repair"],
            "develop_frontend_codegen_repair": ["develop_frontend_codegen_reverifier", "develop_frontend_runtime_blocker"],
            "develop_frontend_codegen_reverifier": ["develop_global_fe_sync_gate", "develop_frontend_runtime_blocker"],
            "develop_frontend_runtime_blocker": [],
            "develop_global_fe_sync_gate": ["develop_frontend_agent", "develop_uiux_agent", "develop_fullstack_runtime_verifier"],
            "develop_fullstack_runtime_verifier": ["develop_integration_qa_gate"],
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
