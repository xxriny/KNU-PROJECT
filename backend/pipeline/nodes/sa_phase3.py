"""
SA Phase 3 — 기술 타당성 및 유지보수성 검토 (LLM 기반)
action_type에 따라 '신규 구현 타당성(CREATE)'과 '기존 시스템 유지보수성(REVERSE)'을 분기하여 평가합니다.
"""

from typing import List
from pydantic import BaseModel, Field
from pipeline.state import PipelineState
from pipeline.utils import call_structured
import json

class FeasibilityOutput(BaseModel):
    thinking: str = Field(default="", description="타당성/유지보수성 추론 과정")
    status: str = Field(description="Pass | Fail | Needs_Clarification")
    complexity_score: int = Field(description="0~100 복잡도/기술 부채 점수")
    reasons: List[str] = Field(description="판정 근거 목록 (한국어, 2~4개)")
    alternatives: List[str] = Field(description="대안 또는 리팩토링/위험 완화 방법 (한국어, 1~3개)")
    high_risk_reqs: List[str] = Field(default_factory=list, description="고위험(구현 난이도 또는 유지보수 악성) 요구사항 REQ_ID 목록")

# 1. CREATE/UPDATE용 프롬프트 (구현 타당성 검토)
CREATE_SYSTEM_PROMPT = """\
당신은 소프트웨어 기술 타당성 검토(Feasibility Study) 전문가입니다.
아래 제공된 RTM(요구사항)과 초기 기술 스택을 종합적으로 분석하여,
현재의 기술 수준과 합리적인 예산/시간 범위 내에서 프로젝트가 '신규 구현' 가능한지 검증하세요.

[판정 기준]
- Pass: 현재 스택으로 무리 없이 구현 가능함
- Fail: 현재 스택의 한계로 구현 불가
- Needs_Clarification: 정보 부족 (예: 필수 프레임워크 미지정)

[출력 규칙]
1. 반드시 단일 JSON 객체만 출력하세요.
2. reasons는 구체적인 기술적 근거를 포함하세요.
3. alternatives는 스택 변경, 요구사항 축소 등 구체적인 대안을 제시하세요.
"""

# 2. REVERSE ENGINEER용 프롬프트 (기술 부채 및 유지보수성 검토)
REVERSE_SYSTEM_PROMPT = """\
당신은 소프트웨어 시스템 진단 및 레거시 분석(Technical Debt Analysis) 전문가입니다.
아래 제공된 '이미 구현된 시스템'의 RTM(요구사항)과 파악된 기술 스택을 분석하여,
현재 아키텍처의 지속 가능성과 유지보수성(Maintainability)을 진단하세요.

[판정 기준]
- Pass: 현재 기술 스택과 구조가 안정적이며 유지보수에 문제가 없음
- Fail: 치명적인 기술 부채, 확장성 불가, 또는 심각한 보안/아키텍처 결함 발견
- Needs_Clarification: 시스템의 핵심 뼈대(예: GUI 프레임워크, DB 종류 등)를 코드 스캔만으로 파악할 수 없어 정확한 진단이 불가함

[출력 규칙]
1. 이미 구현된 시스템이므로 "구현할 수 있는가?"를 묻지 마세요. "유지보수와 확장이 가능한가?"를 평가하세요.
2. 핵심 프레임워크(UI, DB 등)가 누락되어 있어도 스캔 커버리지/증거가 충분하면 보수적으로 진단을 진행하세요. 커버리지와 증거가 모두 부족할 때만 Needs_Clarification을 내리세요.
3. complexity_score는 시스템의 복잡도와 '기술 부채(Technical Debt)'의 심각성을 종합하여 0~100으로 산정하세요.
"""


def _validate_rtm_schema(rtm: list) -> tuple[bool, str]:
    if not isinstance(rtm, list) or not rtm:
        return False, "RTM이 비어 있습니다."
    for i, item in enumerate(rtm):
        if not isinstance(item, dict):
            return False, f"RTM[{i}]가 dict 타입이 아닙니다."
        req_id = item.get("REQ_ID") or item.get("req_id")
        if not req_id:
            return False, f"RTM[{i}]에 REQ_ID(req_id) 필드가 없습니다."
    return True, ""


def _validate_phase1_readiness(phase1: dict) -> tuple[bool, str]:
    if not isinstance(phase1, dict) or not phase1:
        return False, "sa_phase1 결과가 없습니다."

    status = str(phase1.get("status", "")).strip()
    if status in {"Fail", "Error"}:
        return False, f"sa_phase1 상태가 {status} 입니다."

    scanned_functions = int(phase1.get("scanned_functions", 0) or 0)
    scanned_files = int(phase1.get("scanned_files", 0) or 0)
    frameworks = phase1.get("detected_frameworks", []) or []
    evidence = phase1.get("framework_evidence", []) or []

    if scanned_functions == 0 and scanned_files == 0 and not frameworks and not evidence:
        return False, "sa_phase1에서 코드/프레임워크 증거를 확보하지 못했습니다."

    return True, ""

def sa_phase3_node(state: PipelineState) -> dict:
    def sget(key, default=None):
        if hasattr(state, "get"):
            val = state.get(key, default)
        else:
            val = getattr(state, key, default)
        return default if val is None else val

    rtm = sget("requirements_rtm", []) or sget("rtm_matrix", []) or []
    context_spec = sget("context_spec", {}) or {}
    tech_stack = context_spec.get("tech_stack_suggestions", []) or []
    
    sa_phase2 = sget("sa_phase2", {}) or {}
    gap_report = sa_phase2.get("gap_report", [])
    sa_phase1 = sget("sa_phase1", {}) or {}

    api_key = sget("api_key", "")
    model = sget("model", "gemini-2.5-flash")
    action_type = (sget("action_type", "") or "CREATE").strip().upper()

    if action_type != "REVERSE_ENGINEER":
        valid_rtm, rtm_err = _validate_rtm_schema(rtm)
        if not valid_rtm:
            output = {
                "status": "Needs_Clarification",
                "complexity_score": 0,
                "decision": "Needs_Clarification",
                "diagnostic_code": "RTM_SCHEMA_INVALID",
                "reasons": [f"RTM 검증 실패: {rtm_err}"],
                "alternatives": ["PM rtm_builder 결과(requirements_rtm/rtm_matrix)를 확인한 뒤 재실행하세요."],
                "high_risk_reqs": [],
            }
            return {
                "sa_phase3": output,
                "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_phase3", "thinking": "RTM 검증 실패 — 검토 생략"}],
                "current_step": "sa_phase3_done",
            }

    if action_type == "REVERSE_ENGINEER" and not rtm:
        ready, reason = _validate_phase1_readiness(sa_phase1)
        if not ready:
            output = {
                "status": "Needs_Clarification",
                "complexity_score": 0,
                "decision": "Needs_Clarification",
                "diagnostic_code": "PHASE1_CONTEXT_INSUFFICIENT",
                "reasons": [f"코드 구조 분석 컨텍스트 부족: {reason}"],
                "alternatives": ["source_dir를 프로젝트 루트로 지정하고 다시 분석하세요."],
                "high_risk_reqs": [],
            }
            return {
                "sa_phase3": output,
                "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_phase3", "thinking": "phase1 컨텍스트 부족 — reverse 진단 생략"}],
                "current_step": "sa_phase3_done",
            }

        user_msg = (
            f"## 1. 구조 평가\n{sa_phase1.get('architecture_assessment', '정보 없음')}\n\n"
            f"## 2. 스캔 통계\n"
            f"- scanned_files: {sa_phase1.get('scanned_files', 0)}\n"
            f"- scanned_functions: {sa_phase1.get('scanned_functions', 0)}\n"
            f"- languages: {sa_phase1.get('languages', {})}\n\n"
            f"## 3. 프레임워크 단서\n"
            f"- detected_frameworks: {json.dumps(sa_phase1.get('detected_frameworks', []), ensure_ascii=False)}\n"
            f"- framework_evidence: {json.dumps(sa_phase1.get('framework_evidence', []), ensure_ascii=False)}\n"
            f"- diagnostic_code: {sa_phase1.get('diagnostic_code', '')}\n\n"
            f"## 4. 핵심 모듈\n{json.dumps(sa_phase1.get('key_modules', []), ensure_ascii=False)}\n\n"
            f"## 5. 구조적 우려사항\n{json.dumps(sa_phase1.get('concerns', []), ensure_ascii=False)}\n\n"
            f"## 6. 추가 분석 포인트\n{json.dumps(sa_phase1.get('recommended_focus', []), ensure_ascii=False)}\n\n"
            f"위 정보를 바탕으로 현재 시스템의 유지보수성과 기술 부채를 진단하세요."
        )

        try:
            result: FeasibilityOutput = call_structured(
                api_key=api_key,
                model=model,
                schema=FeasibilityOutput,
                system_prompt=REVERSE_SYSTEM_PROMPT,
                user_msg=user_msg,
            )
            output = {
                "status": result.status,
                "complexity_score": result.complexity_score,
                "decision": result.status,
                "diagnostic_code": "",
                "reasons": result.reasons,
                "alternatives": result.alternatives,
                "high_risk_reqs": result.high_risk_reqs,
            }
            thinking_msg = f"기술 부채 진단 완료: {result.status} (점수 {result.complexity_score}) — {result.thinking[:120]}"
        except Exception as e:
            output = {
                "status": "Error",
                "complexity_score": 0,
                "decision": "Error",
                "diagnostic_code": "LLM_ANALYSIS_FAILED",
                "reasons": [f"LLM 호출 실패: {str(e)[:200]}"],
                "alternatives": ["API 키 확인 후 재실행"],
                "high_risk_reqs": [],
            }
            thinking_msg = f"reverse 진단 오류: {str(e)[:100]}"

        return {
            "sa_phase3": output,
            "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_phase3", "thinking": thinking_msg}],
            "current_step": "sa_phase3_done",
        }

    # 모드에 따른 프롬프트 분기
    system_prompt = REVERSE_SYSTEM_PROMPT if action_type == "REVERSE_ENGINEER" else CREATE_SYSTEM_PROMPT

    rtm_compact = [{"REQ_ID": r.get("REQ_ID"), "category": r.get("category"), "desc": r.get("description")} for r in rtm]
    tech_str = "\n".join(f"- {t}" for t in tech_stack) if tech_stack else "명시되지 않음"
    gap_report_str = json.dumps(gap_report, ensure_ascii=False, indent=2) if gap_report else "없음"

    user_msg = (
        f"## 1. 파악된 기술 스택\n{tech_str}\n\n"
        f"## 2. 요구사항 목록 (총 {len(rtm)}개)\n```json\n{json.dumps(rtm_compact, ensure_ascii=False)}\n```\n\n"
        f"## 3. 구조적 갭 리포트\n```json\n{gap_report_str}\n```\n\n"
        f"위 정보를 바탕으로 시스템을 엄격하게 진단하세요."
    )

    try:
        result: FeasibilityOutput = call_structured(
            api_key=api_key,
            model=model,
            schema=FeasibilityOutput,
            system_prompt=system_prompt,
            user_msg=user_msg,
        )
        output = {
            "status": result.status,
            "complexity_score": result.complexity_score,
            "decision": result.status,
            "diagnostic_code": "",
            "reasons": result.reasons,
            "alternatives": result.alternatives,
            "high_risk_reqs": result.high_risk_reqs,
        }
        mode_str = "기술 부채 진단" if action_type == "REVERSE_ENGINEER" else "기술 타당성 검토"
        thinking_msg = f"{mode_str} 완료: {result.status} (점수 {result.complexity_score}) — {result.thinking[:120]}"

    except Exception as e:
        output = {
            "status": "Error",
            "complexity_score": 0,
            "decision": "Error",
            "diagnostic_code": "LLM_ANALYSIS_FAILED",
            "reasons": [f"LLM 호출 실패: {str(e)[:200]}"],
            "alternatives": ["API 키 확인 후 재실행"],
            "high_risk_reqs": [],
        }
        thinking_msg = f"검토 오류: {str(e)[:100]}"

    return {
        "sa_phase3": output,
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_phase3", "thinking": thinking_msg}],
        "current_step": "sa_phase3_done",
    }