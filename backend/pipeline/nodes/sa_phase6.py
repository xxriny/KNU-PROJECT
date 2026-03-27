"""
SA Phase 6 — 시스템 권한 및 보안 경계 설계
"""

from pipeline.state import PipelineState


def sa_phase6_node(state: PipelineState) -> dict:
    def sget(key, default=None):
        if hasattr(state, "get"):
            val = state.get(key, default)
        else:
            val = getattr(state, key, default)
        return default if val is None else val

    phase5 = sget("sa_phase5", {}) or {}
    mapped = phase5.get("mapped_requirements", []) or []

    authz = []
    for item in mapped:
        req_id = item.get("REQ_ID", "")
        if not req_id:
            continue
        authz.append({"req_id": req_id, "role": "admin", "access": "write"})
        authz.append({"req_id": req_id, "role": "user", "access": "read"})

    output = {
        "status": "Pass" if mapped else "Needs_Clarification",
        "rbac_roles": ["admin", "user", "service"],
        "authz_matrix": authz,
        "trust_boundaries": [
            "presentation -> application",
            "application -> domain",
            "application -> infrastructure",
        ],
    }

    return {
        "sa_phase6": output,
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_phase6", "thinking": "시스템 권한 및 보안 경계 설계 완료"}],
        "current_step": "sa_phase6_done",
    }
