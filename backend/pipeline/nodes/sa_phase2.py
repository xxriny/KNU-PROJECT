import json
from pydantic import BaseModel, Field
from typing import List
from pipeline.state import PipelineState, make_sget
from pipeline.utils import call_structured_with_thinking
from version import DEFAULT_MODEL

class RequirementImpact(BaseModel):
    req_id: str = Field(description="요구사항 ID")
    impact_level: str = Field(description="High | Medium | Low (시스템 파괴 및 데이터 흐름 변경 위험도 기준)")
    change_type: str = Field(description="Create | Modify | Delete")
    side_effects: str = Field(description="예상 부작용 및 주의사항 (한국어 1~2문장)")

class GapReportOutput(BaseModel):
    thinking: str = Field(default="", description="영향도 분석 추론 과정 (3줄 이내)")
    overall_risk: str = Field(description="프로젝트 전체의 아키텍처 수정 위험도 요약")
    gap_report: List[RequirementImpact] = Field(description="요구사항별 상세 영향도 분석")

IMPACT_SYSTEM_PROMPT = """\
당신은 시스템 아키텍트(SA)입니다.
신규 요구사항(RTM)이 기존 소스 코드에 미치는 영향도(Impact Analysis)를 분석하세요.

[규칙]
1. 제공된 '수정 예상 파일 목록'과 '요구사항'을 바탕으로 기존 데이터 흐름이 어떻게 변화할지 역추적하세요.
2. 각 요구사항별로 impact_level을 평가하세요. 단순 UI 변경은 Low, DB 스키마 및 코어 로직 변경은 High입니다. 비즈니스 우선순위와 기술적 Impact를 구별하세요.
3. 발생할 수 있는 부작용(side_effects)을 구체적으로 작성하세요."""

def sa_phase2_node(state: PipelineState) -> dict:
    sget = make_sget(state)

    action_type = sget("action_type", "CREATE")
    
    if action_type == "CREATE":
        return {
            "sa_phase2": {
                "status": "Skipped",
                "requirement_count": len(sget("requirements_rtm", [])),
                "gap_report": []
            },
            "thinking_log": sget("thinking_log", []) + [{"node": "sa_phase2", "thinking": "CREATE 모드 감지. 기존 코드 영향도 분석 스킵."}],
            "current_step": "sa_phase2_done",
        }

    rtm = sget("requirements_rtm", [])
    semantic_graph = sget("semantic_graph", {}) or {}

    touched_files = set()
    for node in semantic_graph.get("nodes", []) or []:
        for link in node.get("code_links", []) or []:
            file_path = link.get("file")
            if file_path:
                touched_files.add(file_path)

    if not rtm:
        msg = "영향도 분석에 필요한 요구사항/RTM 데이터가 부족합니다."
        return {
            "sa_phase2": {"status": "Needs_Clarification", "gap_report": []},
            "thinking_log": sget("thinking_log", []) + [{"node": "sa_phase2", "thinking": msg}],
            "current_step": "sa_phase2_done",
        }

    rtm_summary = json.dumps(
        [{"REQ_ID": r.get("REQ_ID"), "category": r.get("category"), "desc": r.get("description")} for r in rtm],
        ensure_ascii=False
    )
    
    user_msg = (
        f"=== 신규 요구사항 (RTM) ===\n{rtm_summary}\n\n"
        f"=== AST 기반 수정 예상 파일 목록 ===\n{list(touched_files)}\n\n"
        f"위 정보를 바탕으로 기존 시스템에 미치는 영향도와 예상 부작용을 분석하세요."
    )

    try:
        result, thinking = call_structured_with_thinking(
            api_key=sget("api_key", ""),
            model=sget("model", DEFAULT_MODEL),
            schema=GapReportOutput,
            system_prompt=IMPACT_SYSTEM_PROMPT,
            user_msg=user_msg,
            max_retries=2
        )
        
        output = {
            "status": "Pass",
            "requirement_count": len(rtm),
            "touched_files": sorted(touched_files),
            "overall_risk": result.overall_risk,
            "gap_report": [r.model_dump() for r in result.gap_report]
        }
        thinking_msg = thinking
        
    except Exception as e:
        output = {
            "status": "Error",
            "requirement_count": len(rtm),
            "touched_files": sorted(touched_files),
            "gap_report": [
                {"req_id": r.get("REQ_ID", ""), "impact_level": "unknown", "change_type": "modify", "side_effects": f"분석 실패: {e}"}
                for r in rtm
            ]
        }
        thinking_msg = f"LLM 분석 실패로 인한 Fallback: {e}"

    return {
        "sa_phase2": output,
        "thinking_log": sget("thinking_log", []) + [{"node": "sa_phase2", "thinking": thinking_msg}],
        "current_step": "sa_phase2_done",
    }

