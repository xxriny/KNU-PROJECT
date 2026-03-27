"""
SA Phase 7 — 추상 인터페이스 및 가이드라인 설계
"""

from pipeline.state import PipelineState


def sa_phase7_node(state: PipelineState) -> dict:
    def sget(key, default=None):
        if hasattr(state, "get"):
            val = state.get(key, default)
        else:
            val = getattr(state, key, default)
        return default if val is None else val

    phase5 = sget("sa_phase5", {}) or {}
    mapped = phase5.get("mapped_requirements", []) or []

    contracts = []
    for item in mapped:
        req_id = item.get("REQ_ID", "")
        layer = item.get("layer", "application")
        if not req_id:
            continue
        contracts.append({
            "contract_id": f"IF-{req_id}",
            "layer": layer,
            "input": {"req_id": req_id, "payload": "object"},
            "output": {"status": "string", "result": "object"},
        })

    output = {
        "status": "Pass" if contracts else "Needs_Clarification",
        "interface_contracts": contracts,
        "guardrails": [
            "presentation 레이어는 infrastructure 직접 호출 금지",
            "모든 외부 I/O는 application 인터페이스를 통해 접근",
            "보안 민감 연산은 security 정책 검증 후 실행",
        ],
    }

    return {
        "sa_phase7": output,
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_phase7", "thinking": "추상 인터페이스 및 가이드라인 설계 완료"}],
        "current_step": "sa_phase7_done",
    }
