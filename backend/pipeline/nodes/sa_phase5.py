"""SA Phase 5 — 아키텍처 매핑 노드 (Clean Architecture 4-Layer)"""

import json
from pipeline.state import PipelineState, make_sget
from pipeline.utils import call_structured_with_thinking
from version import DEFAULT_MODEL

from .sa_phase5_schemas import ArchitectureMappingOutput, MAPPING_SYSTEM_PROMPT
from .sa_layer_heuristics import LAYER_BY_CATEGORY, fallback_mapping_info
from .sa_reverse_module import build_reverse_module_mapping

_FIXED_LAYER_ORDER = ["Presentation", "Application", "Domain", "Infrastructure"]


def sa_phase5_node(state: PipelineState) -> dict:
    sget = make_sget(state)

    rtm = sget("requirements_rtm", [])
    action_type = (sget("action_type", "") or "CREATE").strip().upper()
    sa_phase1 = sget("sa_phase1", {}) or {}
    api_key = sget("api_key", "")
    model = sget("model", DEFAULT_MODEL)

    if not rtm:
        if action_type == "REVERSE_ENGINEER":
            reverse_mapping = build_reverse_module_mapping(sa_phase1, api_key=api_key, model=model)
            status = "Pass" if reverse_mapping else "Needs_Clarification"
            thinking = "reverse 모드에서 코드 스캔 기반 계층 매핑 생성" if reverse_mapping else "reverse 모드이지만 매핑 가능한 핵심 모듈이 없음"
            return {
                "sa_phase5": {
                    "status": status,
                    "pattern": "Clean Architecture",
                    "mapped_requirements": reverse_mapping,
                    "layer_order": _FIXED_LAYER_ORDER,
                },
                "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_phase5", "thinking": thinking}],
                "current_step": "sa_phase5_done",
            }
        return {
            "sa_phase5": {
                "status": "Needs_Clarification",
                "pattern": "Clean Architecture",
                "mapped_requirements": [],
                "layer_order": _FIXED_LAYER_ORDER,
            },
            "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_phase5", "thinking": "RTM 없음 - 매핑 생략"}],
            "current_step": "sa_phase5_done",
        }

    rtm_compact = [
        {"REQ_ID": r.get("REQ_ID", ""), "category": r.get("category", ""), "description": r.get("description", "")}
        for r in rtm
    ]
    user_msg = (
        f"다음 요구사항들을 클린 아키텍처 계층에 매핑하세요.\n\n"
        f"```json\n{json.dumps(rtm_compact, ensure_ascii=False, indent=2)}\n```"
    )

    try:
        result, thinking = call_structured_with_thinking(
            api_key=api_key, model=model, schema=ArchitectureMappingOutput,
            system_prompt=MAPPING_SYSTEM_PROMPT, user_msg=user_msg, max_retries=2,
        )

        mapped_dict = {m.REQ_ID: {"layer": m.layer, "reason": m.reason} for m in result.mapped_requirements}
        final_mapped = []
        for req in rtm:
            req_id = req.get("REQ_ID", "")
            fallback = fallback_mapping_info(req)
            info = mapped_dict.get(req_id, {"layer": fallback["layer"], "reason": fallback["reason"]})
            final_mapped.append({
                "REQ_ID": req_id,
                "layer": info["layer"],
                "description": req.get("description", ""),
                "depends_on": req.get("depends_on", []) or [],
                "mapping_reason": info["reason"],
                "layer_confidence": fallback["confidence"],
                "layer_evidence": fallback["evidence"],
            })

        output = {
            "status": "Pass",
            "pattern": result.pattern_name,
            "mapped_requirements": final_mapped,
            "layer_order": _FIXED_LAYER_ORDER,
        }
        thinking_msg = f"패턴 매핑 완료 ({len(final_mapped)}개 요구사항) - {thinking[:100]}..."

    except Exception as e:
        final_mapped = []
        for req in rtm:
            fallback = fallback_mapping_info(req)
            layer = LAYER_BY_CATEGORY.get(req.get("category", ""), fallback["layer"])
            final_mapped.append({
                "REQ_ID": req.get("REQ_ID", ""), "layer": layer,
                "description": req.get("description", ""), "depends_on": req.get("depends_on", []) or [],
                "mapping_reason": "LLM 매핑 실패로 휴리스틱 기반 자동 할당",
                "layer_confidence": fallback["confidence"],
                "layer_evidence": fallback["evidence"],
            })
        output = {
            "status": "Warning_Hallucination_Detected",
            "pattern": "Clean Architecture",
            "mapped_requirements": final_mapped,
            "layer_order": _FIXED_LAYER_ORDER,
        }
        thinking_msg = f"LLM 매핑 실패로 Fallback 적용: {str(e)[:150]}"

    return {
        "sa_phase5": output,
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_phase5", "thinking": thinking_msg}],
        "current_step": "sa_phase5_done",
    }
