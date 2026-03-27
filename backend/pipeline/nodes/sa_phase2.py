"""
SA Phase 2 — 기존 코드 영향도 분석 (Gap Report)
"""

from pipeline.state import PipelineState


def sa_phase2_node(state: PipelineState) -> dict:
    def sget(key, default=None):
        if hasattr(state, "get"):
            val = state.get(key, default)
        else:
            val = getattr(state, key, default)
        return default if val is None else val

    rtm = sget("requirements_rtm", []) or sget("rtm_matrix", []) or []
    semantic_graph = sget("semantic_graph", {}) or {}

    touched_files = set()
    for node in semantic_graph.get("nodes", []) or []:
        for link in node.get("code_links", []) or []:
            file_path = link.get("file")
            if file_path:
                touched_files.add(file_path)

    high_risk = [r.get("REQ_ID") for r in rtm if r.get("priority") == "Must-have"]
    output = {
        "status": "Pass" if rtm else "Needs_Clarification",
        "requirement_count": len(rtm),
        "touched_files": sorted(touched_files),
        "high_risk_requirements": [rid for rid in high_risk if rid],
        "gap_report": [
            {
                "req_id": r.get("REQ_ID", ""),
                "category": r.get("category", ""),
                "impact_level": "high" if r.get("priority") == "Must-have" else "medium",
                "change_type": "modify",
            }
            for r in rtm
        ],
    }

    msg = "기존 코드 영향도 분석 완료" if rtm else "영향도 분석에 필요한 요구사항/RTM 데이터가 부족합니다."
    return {
        "sa_phase2": output,
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_phase2", "thinking": msg}],
        "current_step": "sa_phase2_done",
    }
