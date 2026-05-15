from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from pipeline.core.state import PipelineState

# --- 노드 임포트 ---
from pipeline.domain.dev.nodes.dev_task_planner import dev_task_planner_node
from pipeline.domain.dev.nodes.feature_queue_controller import develop_feature_queue_controller_node
from pipeline.domain.dev.nodes.main_agent import develop_main_agent_node
from pipeline.domain.dev.nodes.uiux_agent import develop_uiux_agent_node
from pipeline.domain.dev.nodes.uiux_qa_agent import develop_uiux_qa_agent_node
from pipeline.domain.dev.nodes.domain_gates import (
    develop_uiux_domain_gate_node,
    develop_backend_domain_gate_node,
    develop_frontend_domain_gate_node,
)
from pipeline.domain.dev.nodes.backend_agent import develop_backend_agent_node
from pipeline.domain.dev.nodes.backend_codegen import develop_backend_codegen_node
from pipeline.domain.dev.nodes.backend_qa_agent import develop_backend_qa_agent_node
from pipeline.domain.dev.nodes.backend_codegen_verifier import (
    develop_backend_codegen_verifier_node,
    develop_backend_codegen_repair_node,
    develop_backend_codegen_reverifier_node,
    develop_backend_runtime_blocker_node,
)
from pipeline.domain.dev.nodes.frontend_agent import develop_frontend_agent_node
from pipeline.domain.dev.nodes.frontend_codegen import develop_frontend_codegen_node
from pipeline.domain.dev.nodes.frontend_qa_agent import develop_frontend_qa_agent_node
from pipeline.domain.dev.nodes.frontend_codegen_verifier import (
    develop_frontend_codegen_verifier_node,
    develop_frontend_codegen_repair_node,
    develop_frontend_codegen_reverifier_node,
    develop_frontend_runtime_blocker_node,
)
from pipeline.domain.dev.nodes.global_sync_gate import develop_global_fe_sync_gate_node
from pipeline.domain.dev.nodes.fullstack_runtime_verifier import develop_fullstack_runtime_verifier_node
from pipeline.domain.dev.nodes.integration_qa_gate import develop_integration_qa_gate_node
from pipeline.domain.dev.nodes.branch_pr_orchestrator import develop_branch_pr_orchestrator_node
from pipeline.domain.dev.nodes.embedding import develop_embedding_node
from pipeline.domain.dev.nodes.feature_completion import develop_feature_completion_node
from pipeline.domain.dev.nodes.fallback_handler import develop_fallback_handler_node
from pipeline.domain.dev.nodes.loop_controller import develop_loop_controller_node
from pipeline.domain.dev.message_contracts import attach_dev_contract_outputs

# --- 헬퍼 함수 ---
def _selected_domains(state: PipelineState) -> set[str]:
    plan = state.get("develop_main_plan", {}) or {}
    selected = plan.get("selected_domains") if "selected_domains" in plan else ["uiux", "backend", "frontend"]
    selected = selected or []
    return {str(domain).lower() for domain in selected}


def _normalize_rework_targets(result: dict, selected: set[str] | None = None) -> list[str]:
    allowed = selected or {"uiux", "backend", "frontend"}
    status = str(result.get("status", "") or "").lower()
    targets = [
        str(target).lower()
        for target in (result.get("rework_targets") or [])
        if str(target).lower() in allowed
    ]
    if not targets and status.startswith("rework_"):
        target = status.replace("rework_", "", 1)
        if target in allowed:
            targets = [target]
    return [domain for domain in ["uiux", "backend", "frontend"] if domain in set(targets)]


def _rework_instruction_from_integration(state: PipelineState, domain: str) -> dict:
    integration = state.get("integration_qa_result", {}) or {}
    findings = [str(item) for item in (integration.get("findings") or []) if str(item).strip()]
    return {
        "domain": domain,
        "active": True,
        "source": {
            "integration_status": integration.get("status", ""),
            "global_fe_sync_status": (state.get("global_fe_sync_result", {}) or {}).get("status", ""),
            "domain_gate_status": (state.get(f"{domain}_domain_gate_result", {}) or {}).get("status", ""),
            "domain_qa_status": (state.get(f"{domain}_qa_result", {}) or {}).get("status", ""),
        },
        "findings": list(dict.fromkeys(findings)),
        "actions": ["Resolve integration QA findings assigned to this domain."],
    }


def _with_rework_instruction(spec: dict, instruction: dict) -> dict:
    updated = dict(spec or {})
    updated["rework_instruction"] = instruction
    dev_task = dict(updated.get("dev_task") or {})
    if dev_task:
        context = dict(dev_task.get("context") or {})
        context["rework_instruction"] = instruction
        dev_task["context"] = context
        updated["dev_task"] = dev_task
    return updated

# --- 엄격한 라우팅 로직 (Strict Routing) ---

def _route_after_main_agent(state: PipelineState) -> str:
    selected = _selected_domains(state)
    if "uiux" in selected: return "uiux"
    if "backend" in selected: return "backend"
    if "frontend" in selected: return "frontend"
    return "block"

def _route_uiux_domain_gate(state: PipelineState) -> str:
    res = state.get("uiux_domain_gate_result", {}) or {}
    status = str(res.get("status", "error")).lower()
    if status == "pass": return "pass"
    if status == "rework": return "retry"
    # [지시사항] blocked/skipped/failed/error/unknown -> block
    return "block"

def _route_after_uiux_gate(state: PipelineState) -> str:
    # 이 라우터는 오직 uiux_gate가 'pass'일 때만 호출되어야 함
    selected = _selected_domains(state)
    if "backend" in selected: return "backend"
    if "frontend" in selected: return "frontend"
    return "block"

def _route_backend_domain_gate(state: PipelineState) -> str:
    res = state.get("backend_domain_gate_result", {}) or {}
    status = str(res.get("status", "error")).lower()
    
    if status == "pass": return "pass"
    if status == "rework": return "retry"
    return "block"

def _route_backend_codegen_verification(state: PipelineState) -> str:
    verify_res = state.get("backend_codegen_verification", {}) or {}
    status = str(verify_res.get("status", "error")).lower()
    failure_type = str(verify_res.get("failure_type", "") or "").lower()
    
    if status in {"pass", "passed"}: return "pass"
    if status == "failed": return "repair"
    # 백엔드 생성이 비활성화된 경우 skipped를 성공으로 간주하여 프론트엔드로 진행
    if status == "skipped" and not state.get("enable_backend_codegen", True):
        return "pass"
    if status == "skipped" and failure_type == "dependency_install_required":
        return "block"
    return "block"

def _route_frontend_domain_gate(state: PipelineState) -> str:
    res = state.get("frontend_domain_gate_result", {}) or {}
    status = str(res.get("status", "error")).lower()
    
    if status == "pass": return "pass"
    if status == "rework": return "retry"
    return "block"

def _route_frontend_codegen_verification(state: PipelineState) -> str:
    verify_res = state.get("frontend_codegen_verification", {}) or {}
    status = str(verify_res.get("status", "error")).lower()
    
    if status in {"pass", "passed"}: return "pass"
    if status == "failed": return "repair"
    # 프론트엔드 생성이 비활성화된 경우 skipped를 성공으로 간주
    if status == "skipped" and not state.get("enable_frontend_codegen", True):
        return "pass"
    return "block"

def _route_global_fe_sync_gate(state: PipelineState) -> str:
    res = state.get("global_fe_sync_result", {}) or {}
    status = str(res.get("status", "error")).lower()
    
    # retry limit 추가 (최대 2회)
    retry_count = int(state.get("global_fe_sync_retry_count", 0) or 0)
    if status in {"rework_uiux", "rework_frontend"} and retry_count >= 2:
        return "block"

    if status == "pass": return "pass"
    if status == "rework_uiux": return "rework_uiux"
    if status == "rework_frontend": return "rework_frontend"
    return "block"

def _route_integration_qa_gate(state: PipelineState) -> str:
    res = state.get("integration_qa_result", {}) or {}
    status = str(res.get("status", "error")).lower()
    
    if status == "pass": return "pass"
    if status in {"rework_uiux", "rework_backend", "rework_frontend"}:
        if int(state.get("develop_integration_rework_count", 0) or 0) >= 1:
            return "block"
        targets = _normalize_rework_targets(res, _selected_domains(state))
        if "uiux" in targets: return "rework_uiux"
        if "backend" in targets: return "rework_backend"
        if "frontend" in targets: return "rework_frontend"
        return "block"
    return "block"


def _develop_rework_dispatcher(state: PipelineState) -> dict:
    integration = state.get("integration_qa_result", {}) or {}
    targets = _normalize_rework_targets(integration, _selected_domains(state))
    if not targets:
        targets = _normalize_rework_targets(integration)

    plan = dict(state.get("develop_main_plan", {}) or {})
    branch_strategy = dict(plan.get("branch_strategy", {}) or {})
    branch_strategy["domain_branches"] = [
        item for item in (branch_strategy.get("domain_branches") or [])
        if item.get("domain") in set(targets)
    ]
    plan["selected_domains"] = targets
    plan["branch_strategy"] = branch_strategy

    rework_instructions = dict(plan.get("rework_instructions", {}) or {})
    result: dict = {
        "develop_main_plan": plan,
        "develop_rework_targets": targets,
        "develop_integration_rework_count": int(state.get("develop_integration_rework_count", 0) or 0) + 1,
        "_thinking": "integration-rework-dispatch",
    }

    for domain in targets:
        instruction = _rework_instruction_from_integration(state, domain)
        rework_instructions[domain] = instruction
        key = f"{domain}_task_spec"
        result[key] = _with_rework_instruction(state.get(key, {}) or {}, instruction)

    plan["rework_instructions"] = rework_instructions
    return result


def _route_rework_dispatcher(state: PipelineState) -> str:
    targets = state.get("develop_rework_targets", []) or []
    targets = [str(target).lower() for target in targets]
    if "uiux" in targets: return "uiux"
    if "backend" in targets: return "backend"
    if "frontend" in targets: return "frontend"
    return "block"

def _route_loop_controller(state: PipelineState) -> str:
    action = str(state.get("develop_next_action", "complete")).lower()
    if action == "next_feature": return "next_feature"
    if action == "retry_main": return "retry_main"
    if action == "complete": return "complete"
    return "block"


def _noop(state: PipelineState) -> dict:
    return {}


def _route_after_backend_runtime(state: PipelineState) -> str:
    return "frontend" if "frontend" in _selected_domains(state) else "integration"


def _route_backend_codegen_reverifier(state: PipelineState) -> str:
    status = str((state.get("backend_codegen_reverify_result", {}) or {}).get("status", "")).lower()
    return "pass" if status in {"pass", "passed"} else "block"


def _route_frontend_codegen_reverifier(state: PipelineState) -> str:
    status = str((state.get("frontend_codegen_reverify_result", {}) or {}).get("status", "")).lower()
    return "pass" if status in {"pass", "passed"} else "block"


def _route_branch_pr_orchestrator(state: PipelineState) -> str:
    result = state.get("branch_pr_result", {}) or {}
    status = str(result.get("status", "") or "").lower()
    if status in {"ready", "completed", "complete"} and (
        bool(result.get("merge_ready")) or bool(result.get("pr_created"))
    ):
        return "embed"
    return "skip"


def _develop_prerequisite_blocker(state: PipelineState) -> dict:
    result = {
        "integration_qa_result": {
            "status": "blocked",
            "reason": "No selected development domain reached Integration QA PASS.",
            "findings": [
                "Branch/PR and RAG embedding require integration_qa_result.status=pass."
            ],
            "rework_targets": [],
        },
        "branch_pr_result": {
            "status": "blocked",
            "merge_ready": False,
            "readiness_checks": [
                {
                    "check": "integration_qa",
                    "status": "missing",
                    "ready": False,
                    "reason": "Integration QA was not executed before PR orchestration.",
                }
            ],
        },
        "develop_next_action": "blocked_prerequisite",
    }
    result.update(attach_dev_contract_outputs(state, result, "develop_prerequisite_blocker"))
    return result

# --- 그래프 구축 ---

def get_develop_pipeline():
    workflow = StateGraph(PipelineState)
    
    # 노드 등록
    workflow.add_node("dev_task_planner", dev_task_planner_node)
    workflow.add_node("develop_feature_queue_controller", develop_feature_queue_controller_node)
    workflow.add_node("develop_main_agent", develop_main_agent_node)
    workflow.add_node("develop_uiux_agent", develop_uiux_agent_node)
    workflow.add_node("develop_uiux_qa_agent", develop_uiux_qa_agent_node)
    workflow.add_node("develop_uiux_domain_gate", develop_uiux_domain_gate_node)
    
    workflow.add_node("develop_backend_agent", develop_backend_agent_node)
    workflow.add_node("develop_backend_qa_agent", develop_backend_qa_agent_node)
    workflow.add_node("develop_backend_domain_gate", develop_backend_domain_gate_node)
    workflow.add_node("develop_backend_codegen", develop_backend_codegen_node)
    workflow.add_node("develop_backend_codegen_verifier", develop_backend_codegen_verifier_node)
    workflow.add_node("develop_backend_codegen_repair", develop_backend_codegen_repair_node)
    workflow.add_node("develop_backend_codegen_reverifier", develop_backend_codegen_reverifier_node)
    workflow.add_node("develop_backend_runtime_blocker", develop_backend_runtime_blocker_node)
    
    workflow.add_node("develop_frontend_agent", develop_frontend_agent_node)
    workflow.add_node("develop_frontend_qa_agent", develop_frontend_qa_agent_node)
    workflow.add_node("develop_frontend_domain_gate", develop_frontend_domain_gate_node)
    workflow.add_node("develop_frontend_codegen", develop_frontend_codegen_node)
    workflow.add_node("develop_frontend_codegen_verifier", develop_frontend_codegen_verifier_node)
    workflow.add_node("develop_frontend_codegen_repair", develop_frontend_codegen_repair_node)
    workflow.add_node("develop_frontend_codegen_reverifier", develop_frontend_codegen_reverifier_node)
    workflow.add_node("develop_frontend_runtime_blocker", develop_frontend_runtime_blocker_node)
    
    workflow.add_node("develop_global_fe_sync_gate", develop_global_fe_sync_gate_node)
    workflow.add_node("develop_fullstack_runtime_verifier", develop_fullstack_runtime_verifier_node)
    workflow.add_node("develop_integration_qa_gate", develop_integration_qa_gate_node)
    workflow.add_node("develop_rework_dispatcher", _develop_rework_dispatcher)
    workflow.add_node("develop_branch_pr_orchestrator", develop_branch_pr_orchestrator_node)
    workflow.add_node("develop_embedding", develop_embedding_node)
    workflow.add_node("develop_prerequisite_blocker", _develop_prerequisite_blocker)
    workflow.add_node("develop_feature_completion", develop_feature_completion_node)
    workflow.add_node("develop_fallback_handler", develop_fallback_handler_node)
    workflow.add_node("develop_loop_controller", develop_loop_controller_node)

    # ── [Edges] ──
    workflow.add_edge(START, "dev_task_planner")
    workflow.add_edge("dev_task_planner", "develop_feature_queue_controller")
    workflow.add_edge("develop_feature_queue_controller", "develop_main_agent")
    
    # 1. Main Agent -> 도메인 분기
    workflow.add_conditional_edges(
        "develop_main_agent",
        _route_after_main_agent,
        {
            "uiux": "develop_uiux_agent",
            "backend": "develop_backend_agent",
            "frontend": "develop_frontend_agent",
            "block": "develop_prerequisite_blocker"
        }
    )

    # 2. UI/UX Flow
    workflow.add_edge("develop_uiux_agent", "develop_uiux_qa_agent")
    workflow.add_edge("develop_uiux_qa_agent", "develop_uiux_domain_gate")
    workflow.add_conditional_edges(
        "develop_uiux_domain_gate",
        _route_uiux_domain_gate,
        {
            "pass": "develop_after_uiux_gate",
            "retry": "develop_uiux_agent",
            "block": "develop_backend_runtime_blocker"
        }
    )
    workflow.add_node("develop_after_uiux_gate", _noop)
    workflow.add_conditional_edges(
        "develop_after_uiux_gate",
        _route_after_uiux_gate,
        {
            "backend": "develop_backend_agent",
            "frontend": "develop_frontend_agent",
            "block": "develop_prerequisite_blocker"
        }
    )

    # 3. Backend Flow
    workflow.add_edge("develop_backend_agent", "develop_backend_qa_agent")
    workflow.add_edge("develop_backend_qa_agent", "develop_backend_domain_gate")
    workflow.add_conditional_edges(
        "develop_backend_domain_gate",
        _route_backend_domain_gate,
        {
            "pass": "develop_backend_codegen",
            "retry": "develop_backend_agent",
            "block": "develop_backend_runtime_blocker"
        }
    )
    workflow.add_edge("develop_backend_codegen", "develop_backend_codegen_verifier")
    workflow.add_conditional_edges(
        "develop_backend_codegen_verifier",
        _route_backend_codegen_verification,
        {
            "pass": "develop_after_backend_runtime",
            "repair": "develop_backend_codegen_repair",
            "block": "develop_backend_runtime_blocker"
        }
    )
    workflow.add_edge("develop_backend_codegen_repair", "develop_backend_codegen_reverifier")
    workflow.add_conditional_edges(
        "develop_backend_codegen_reverifier",
        _route_backend_codegen_reverifier,
        {
            "pass": "develop_after_backend_runtime",
            "block": "develop_backend_runtime_blocker"
        }
    )
    workflow.add_node("develop_after_backend_runtime", _noop)
    workflow.add_conditional_edges(
        "develop_after_backend_runtime",
        _route_after_backend_runtime,
        {
            "frontend": "develop_frontend_agent",
            "integration": "develop_integration_qa_gate"
        }
    )

    # 4. Frontend Flow
    workflow.add_edge("develop_frontend_agent", "develop_frontend_qa_agent")
    workflow.add_edge("develop_frontend_qa_agent", "develop_frontend_domain_gate")
    workflow.add_conditional_edges(
        "develop_frontend_domain_gate",
        _route_frontend_domain_gate,
        {
            "pass": "develop_frontend_codegen",
            "retry": "develop_frontend_agent",
            "block": "develop_frontend_runtime_blocker"
        }
    )
    workflow.add_edge("develop_frontend_codegen", "develop_frontend_codegen_verifier")
    workflow.add_conditional_edges(
        "develop_frontend_codegen_verifier",
        _route_frontend_codegen_verification,
        {
            "pass": "develop_global_fe_sync_gate",
            "repair": "develop_frontend_codegen_repair",
            "block": "develop_frontend_runtime_blocker"
        }
    )
    workflow.add_edge("develop_frontend_codegen_repair", "develop_frontend_codegen_reverifier")
    workflow.add_conditional_edges(
        "develop_frontend_codegen_reverifier",
        _route_frontend_codegen_reverifier,
        {
            "pass": "develop_global_fe_sync_gate",
            "block": "develop_frontend_runtime_blocker"
        }
    )

    # 5. Sync & Integration
    workflow.add_conditional_edges(
        "develop_global_fe_sync_gate",
        _route_global_fe_sync_gate,
        {
            "pass": "develop_fullstack_runtime_verifier",
            "rework_uiux": "develop_uiux_agent",
            "rework_frontend": "develop_frontend_agent",
            "block": "develop_frontend_runtime_blocker"
        }
    )
    workflow.add_edge("develop_fullstack_runtime_verifier", "develop_integration_qa_gate")
    workflow.add_conditional_edges(
        "develop_integration_qa_gate",
        _route_integration_qa_gate,
        {
            "pass": "develop_branch_pr_orchestrator",
            "rework_uiux": "develop_rework_dispatcher",
            "rework_backend": "develop_rework_dispatcher",
            "rework_frontend": "develop_rework_dispatcher",
            "block": "develop_frontend_runtime_blocker"
        }
    )
    workflow.add_conditional_edges(
        "develop_rework_dispatcher",
        _route_rework_dispatcher,
        {
            "uiux": "develop_uiux_agent",
            "backend": "develop_backend_agent",
            "frontend": "develop_frontend_agent",
            "block": "develop_frontend_runtime_blocker",
        }
    )

    # 6. Wrap-up
    workflow.add_conditional_edges(
        "develop_branch_pr_orchestrator",
        _route_branch_pr_orchestrator,
        {
            "embed": "develop_embedding",
            "skip": "develop_feature_completion",
        }
    )
    workflow.add_edge("develop_embedding", "develop_feature_completion")
    workflow.add_edge("develop_prerequisite_blocker", "develop_feature_completion")
    workflow.add_edge("develop_feature_completion", "develop_loop_controller")
    workflow.add_conditional_edges(
        "develop_loop_controller",
        _route_loop_controller,
        {
            "next_feature": "develop_feature_queue_controller",
            "retry_main": "develop_main_agent",
            "complete": END,
            "block": "develop_fallback_handler"
        }
    )
    workflow.add_edge("develop_fallback_handler", END)
    
    workflow.add_edge("develop_backend_runtime_blocker", "develop_feature_completion")
    workflow.add_edge("develop_frontend_runtime_blocker", "develop_feature_completion")

    return workflow.compile()


def get_develop_routing_map() -> dict:
    return {
        "first_node": "dev_task_planner",
        "next_nodes": {
            "dev_task_planner": ["develop_feature_queue_controller"],
            "develop_feature_queue_controller": ["develop_main_agent"],
            "develop_main_agent": ["develop_uiux_agent", "develop_backend_agent", "develop_frontend_agent", "develop_prerequisite_blocker"],
            "develop_uiux_agent": ["develop_uiux_qa_agent"],
            "develop_uiux_qa_agent": ["develop_uiux_domain_gate"],
            "develop_uiux_domain_gate": ["develop_after_uiux_gate", "develop_uiux_agent", "develop_backend_runtime_blocker"],
            "develop_after_uiux_gate": ["develop_backend_agent", "develop_frontend_agent", "develop_prerequisite_blocker"],
            "develop_backend_agent": ["develop_backend_qa_agent"],
            "develop_backend_qa_agent": ["develop_backend_domain_gate"],
            "develop_backend_domain_gate": ["develop_backend_agent", "develop_backend_codegen", "develop_backend_runtime_blocker"],
            "develop_backend_codegen": ["develop_backend_codegen_verifier"],
            "develop_backend_codegen_verifier": ["develop_after_backend_runtime", "develop_backend_codegen_repair", "develop_backend_runtime_blocker"],
            "develop_backend_codegen_repair": ["develop_backend_codegen_reverifier"],
            "develop_backend_codegen_reverifier": ["develop_after_backend_runtime", "develop_backend_runtime_blocker"],
            "develop_after_backend_runtime": ["develop_frontend_agent", "develop_integration_qa_gate"],
            "develop_backend_runtime_blocker": ["develop_feature_completion"],
            "develop_frontend_agent": ["develop_frontend_qa_agent"],
            "develop_frontend_qa_agent": ["develop_frontend_domain_gate"],
            "develop_frontend_domain_gate": ["develop_frontend_agent", "develop_frontend_codegen", "develop_frontend_runtime_blocker"],
            "develop_frontend_codegen": ["develop_frontend_codegen_verifier"],
            "develop_frontend_codegen_verifier": ["develop_global_fe_sync_gate", "develop_frontend_codegen_repair", "develop_frontend_runtime_blocker"],
            "develop_frontend_codegen_repair": ["develop_frontend_codegen_reverifier"],
            "develop_frontend_codegen_reverifier": ["develop_global_fe_sync_gate", "develop_frontend_runtime_blocker"],
            "develop_frontend_runtime_blocker": ["develop_feature_completion"],
            "develop_global_fe_sync_gate": ["develop_frontend_agent", "develop_uiux_agent", "develop_fullstack_runtime_verifier", "develop_frontend_runtime_blocker"],
            "develop_fullstack_runtime_verifier": ["develop_integration_qa_gate"],
            "develop_integration_qa_gate": [
                "develop_branch_pr_orchestrator",
                "develop_rework_dispatcher",
                "develop_frontend_runtime_blocker"
            ],
            "develop_rework_dispatcher": [
                "develop_uiux_agent",
                "develop_backend_agent",
                "develop_frontend_agent",
                "develop_frontend_runtime_blocker",
            ],
            "develop_branch_pr_orchestrator": ["develop_embedding", "develop_feature_completion"],
            "develop_embedding": ["develop_feature_completion"],
            "develop_prerequisite_blocker": ["develop_feature_completion"],
            "develop_feature_completion": ["develop_loop_controller"],
            "develop_loop_controller": ["develop_feature_queue_controller", "develop_main_agent", "develop_fallback_handler"],
            "develop_fallback_handler": [],
        },
        "start_message": "Develop pipeline starting...",
    }
