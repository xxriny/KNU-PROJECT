"""
SA Phase 3 — 기술 타당성 및 유지보수성 검토 (LLM 기반)
action_type에 따라 '신규 구현 타당성(CREATE)'과 '기존 시스템 유지보수성(REVERSE)'을 분기하여 평가합니다.
"""

import json
import os
from typing import List

from pydantic import BaseModel, Field

from pipeline.state import PipelineState, sget as state_sget
from pipeline.utils import call_structured


MAX_REASONS = 4
MAX_ALTERNATIVES = 3


class ReverseEvidence(BaseModel):
    source_dir: str = ""
    scanned_files: int = 0
    scanned_functions: int = 0
    detected_frameworks: List[str] = Field(default_factory=list)
    framework_evidence_count: int = 0
    language_count: int = 0
    has_tests: bool = False
    has_observability: bool = False
    has_schema_enforcement: bool = False
    has_result_shaping: bool = False
    has_pipeline_routing: bool = False
    has_token_usage_tracking: bool = False
    reverse_has_rtm: bool = False
    evidence_quality_score: int = 0
    evidence_warnings: List[str] = Field(default_factory=list)


class ReverseAssessment(BaseModel):
    status: str
    complexity_score: int
    diagnostic_code: str
    reasons: List[str] = Field(default_factory=list)
    alternatives: List[str] = Field(default_factory=list)
    high_risk_reqs: List[str] = Field(default_factory=list)
    score_breakdown: List[dict] = Field(default_factory=list)
    evidence_summary: dict = Field(default_factory=dict)

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


def _safe_read_text(path: str, limit: int = 200_000) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read(limit)
    except OSError:
        return ""


def _path_exists(root: str, *parts: str) -> bool:
    return bool(root) and os.path.exists(os.path.join(root, *parts))


def _detect_tests(root: str) -> bool:
    if not root or not os.path.isdir(root):
        return False

    for current_root, dirnames, filenames in os.walk(root):
        basename = os.path.basename(current_root).lower()
        if basename in {"test", "tests"}:
            return True
        if any(name.startswith("test_") and name.endswith(".py") for name in filenames):
            return True
        dirnames[:] = [name for name in dirnames if name not in {"__pycache__", ".git", "node_modules", "Data", "dist", "build"}]
    return False


def _clamp_score(value: int) -> int:
    return max(0, min(100, int(value)))


def _append_unique(items: list[str], message: str):
    if message and message not in items:
        items.append(message)


def _collect_reverse_evidence(sa_phase1: dict, source_dir: str, has_rtm: bool) -> ReverseEvidence:
    root = (source_dir or "").strip()
    framework_evidence = sa_phase1.get("framework_evidence", []) or []
    languages = sa_phase1.get("languages", {}) or {}

    has_observability = (
        _path_exists(root, "backend", "observability", "logger.py")
        or _path_exists(root, "backend", "observability", "metrics.py")
        or _path_exists(root, "observability", "logger.py")
    )
    has_result_shaping = (
        _path_exists(root, "backend", "result_shaping", "result_shaper.py")
        or _path_exists(root, "result_shaping", "result_shaper.py")
    )
    graph_path = (
        os.path.join(root, "backend", "pipeline", "graph.py")
        if root else ""
    )
    schemas_path = (
        os.path.join(root, "backend", "pipeline", "schemas.py")
        if root else ""
    )
    utils_path = (
        os.path.join(root, "backend", "pipeline", "utils.py")
        if root else ""
    )
    pm_phase1_path = (
        os.path.join(root, "backend", "pipeline", "nodes", "pm_phase1.py")
        if root else ""
    )
    atomizer_path = (
        os.path.join(root, "backend", "pipeline", "nodes", "atomizer.py")
        if root else ""
    )

    graph_text = _safe_read_text(graph_path)
    schemas_text = _safe_read_text(schemas_path)
    utils_text = _safe_read_text(utils_path)
    pm_phase1_text = _safe_read_text(pm_phase1_path)
    atomizer_text = _safe_read_text(atomizer_path)

    has_pipeline_routing = "StateGraph" in graph_text and "add_conditional_edges" in graph_text
    has_schema_enforcement = "with_structured_output" in utils_text and "BaseModel" in schemas_text
    has_token_usage_tracking = any(
        token in text
        for text in (pm_phase1_text, atomizer_text, utils_text)
        for token in ("call_structured_with_usage", "input_tokens", "output_tokens")
    )

    evidence_quality = 0
    scanned_files = int(sa_phase1.get("scanned_files", 0) or 0)
    scanned_functions = int(sa_phase1.get("scanned_functions", 0) or 0)

    if scanned_files >= 20:
        evidence_quality += 30
    elif scanned_files >= 8:
        evidence_quality += 20
    elif scanned_files > 0:
        evidence_quality += 10

    if scanned_functions >= 120:
        evidence_quality += 30
    elif scanned_functions >= 40:
        evidence_quality += 20
    elif scanned_functions > 0:
        evidence_quality += 10

    if len(framework_evidence) >= 3:
        evidence_quality += 20
    elif len(framework_evidence) >= 1:
        evidence_quality += 10

    if len(languages) >= 2:
        evidence_quality += 10
    elif len(languages) == 1:
        evidence_quality += 5

    if _detect_tests(root):
        evidence_quality += 10

    warnings: list[str] = []
    if evidence_quality < 35:
        _append_unique(warnings, "정량적 코드 증거가 충분하지 않아 reverse 유지보수성 판정의 신뢰도가 낮습니다.")
    if not framework_evidence:
        _append_unique(warnings, "manifest 또는 엔트리포인트 기반 프레임워크 증거가 부족합니다.")
    if not has_rtm:
        _append_unique(warnings, "reverse 모드에 검증된 RTM이 없어 요구사항 단위 위험 식별은 생략됩니다.")

    return ReverseEvidence(
        source_dir=root,
        scanned_files=scanned_files,
        scanned_functions=scanned_functions,
        detected_frameworks=sa_phase1.get("detected_frameworks", []) or [],
        framework_evidence_count=len(framework_evidence),
        language_count=len(languages),
        has_tests=_detect_tests(root),
        has_observability=has_observability,
        has_schema_enforcement=has_schema_enforcement,
        has_result_shaping=has_result_shaping,
        has_pipeline_routing=has_pipeline_routing,
        has_token_usage_tracking=has_token_usage_tracking,
        reverse_has_rtm=has_rtm,
        evidence_quality_score=_clamp_score(evidence_quality),
        evidence_warnings=warnings,
    )


def _collect_reverse_high_risk_reqs(rtm: list, gap_report: list) -> list[str]:
    valid_ids = {
        (item.get("REQ_ID") or item.get("req_id"))
        for item in (rtm or [])
        if isinstance(item, dict) and (item.get("REQ_ID") or item.get("req_id"))
    }
    if not valid_ids:
        return []

    high_risk: list[str] = []
    for item in gap_report or []:
        if not isinstance(item, dict):
            continue
        req_id = item.get("req_id") or item.get("REQ_ID")
        impact_level = str(item.get("impact_level", "")).strip().lower()
        if req_id in valid_ids and impact_level == "high" and req_id not in high_risk:
            high_risk.append(req_id)
    return high_risk


def _assess_reverse_maintainability(sa_phase1: dict, rtm: list, gap_report: list) -> ReverseAssessment:
    evidence = _collect_reverse_evidence(sa_phase1, sa_phase1.get("source_dir", ""), bool(rtm))
    breakdown: list[dict] = []

    def add_score(code: str, delta: int, message: str):
        breakdown.append({"code": code, "delta": delta, "message": message})

    if evidence.evidence_quality_score < 35:
        add_score("LOW_EVIDENCE_QUALITY", 25, "스캔 범위와 정량 증거가 충분하지 않습니다.")
    elif evidence.evidence_quality_score < 55:
        add_score("MEDIUM_EVIDENCE_QUALITY", 10, "스캔 증거는 있으나 유지보수성 판정을 확정하기엔 다소 제한적입니다.")
    else:
        add_score("STRONG_EVIDENCE_QUALITY", -10, "스캔 범위와 프레임워크 증거가 비교적 충분합니다.")

    if evidence.has_tests:
        add_score("TESTS_PRESENT", -15, "테스트 자산이 존재해 회귀 위험을 낮춥니다.")
    else:
        add_score("TESTS_MISSING", 20, "테스트 자산이 없어 변경 안정성을 보장하기 어렵습니다.")

    if evidence.has_observability:
        add_score("OBSERVABILITY_PRESENT", -10, "로깅/메트릭 계층이 있어 운영 추적성이 확보되어 있습니다.")
    else:
        add_score("OBSERVABILITY_MISSING", 15, "로깅/메트릭 계층이 부족해 장애 분석 비용이 커질 수 있습니다.")

    if evidence.has_schema_enforcement:
        add_score("SCHEMA_ENFORCEMENT_PRESENT", -10, "구조화 출력과 스키마 강제가 있어 LLM 출력 안정성을 높입니다.")
    else:
        add_score("SCHEMA_ENFORCEMENT_MISSING", 15, "스키마 강제 근거가 부족해 출력 일관성 리스크가 있습니다.")

    if evidence.has_result_shaping:
        add_score("RESULT_SHAPING_PRESENT", -5, "결과 셰이핑 계층이 있어 최종 출력 계약이 분리되어 있습니다.")
    else:
        add_score("RESULT_SHAPING_MISSING", 10, "결과 셰이핑 계층이 부족해 산출물 계약이 흔들릴 수 있습니다.")

    if evidence.has_pipeline_routing:
        add_score("PIPELINE_ROUTING_PRESENT", -5, "파이프라인 라우팅과 조기 종료 규칙이 명시적으로 분리되어 있습니다.")
    else:
        add_score("PIPELINE_ROUTING_MISSING", 10, "파이프라인 제어 흐름이 불명확합니다.")

    if evidence.has_token_usage_tracking:
        add_score("TOKEN_USAGE_TRACKING_PRESENT", -5, "일부 노드에서 토큰 사용량을 추적하고 있습니다.")
    else:
        add_score("TOKEN_USAGE_TRACKING_MISSING", 10, "토큰 사용량 추적 근거가 부족합니다.")

    if not evidence.reverse_has_rtm:
        add_score("REVERSE_WITHOUT_RTM", 5, "reverse 모드에 검증된 RTM이 없어 요구사항 단위 리스크 식별은 제한됩니다.")

    complexity_score = _clamp_score(sum(item["delta"] for item in breakdown))

    foundational_gaps = sum(
        1
        for key in (
            evidence.has_tests,
            evidence.has_observability,
            evidence.has_schema_enforcement,
            evidence.has_result_shaping,
            evidence.has_pipeline_routing,
        )
        if not key
    )

    if evidence.evidence_quality_score < 35:
        status = "Needs_Clarification"
        diagnostic_code = "REVERSE_EVIDENCE_INSUFFICIENT"
    elif complexity_score >= 75 and foundational_gaps >= 3:
        status = "Fail"
        diagnostic_code = "REVERSE_FOUNDATIONAL_GAPS"
    elif complexity_score >= 50:
        status = "Needs_Clarification"
        diagnostic_code = "REVERSE_MAINTAINABILITY_RISK"
    else:
        status = "Pass"
        diagnostic_code = "REVERSE_RULE_BASED_PASS"

    reasons = [item["message"] for item in breakdown if item["delta"] >= 10]
    if status == "Pass":
        strengths = [item["message"] for item in breakdown if item["delta"] < 0]
        reasons = strengths[:3]
        if evidence.evidence_warnings:
            reasons.extend(evidence.evidence_warnings[:1])

    if status == "Needs_Clarification" and not reasons:
        reasons = evidence.evidence_warnings[:2] or ["유지보수성 판정을 내리기에 충분한 정량 증거가 아직 부족합니다."]
    if status == "Fail" and not reasons:
        reasons = [item["message"] for item in breakdown if item["delta"] > 0][:MAX_REASONS]

    alternatives: list[str] = []
    if not evidence.has_tests:
        alternatives.append("핵심 파이프라인과 RTM 수정 경로에 대한 회귀 테스트를 먼저 보강하세요.")
    if not evidence.has_observability:
        alternatives.append("로깅과 메트릭 계층을 추가해 파이프라인 디버깅 가능성을 높이세요.")
    if not evidence.has_schema_enforcement:
        alternatives.append("LLM 출력에 대한 스키마 강제와 후속 검증 계층을 보강하세요.")
    if evidence.evidence_quality_score < 35:
        alternatives.append("source_dir 범위를 점검하고 더 많은 코드 증거를 수집한 뒤 다시 reverse 분석을 실행하세요.")
    if not evidence.reverse_has_rtm:
        alternatives.append("reverse 결과를 요구사항 단위로 해석하려면 검증된 RTM 또는 traceability 정보도 함께 수집하세요.")

    if not alternatives:
        alternatives.append("현재 구조는 유지보수 가능하므로 기존 강점을 유지하면서 테스트와 추적성을 점진적으로 강화하세요.")

    evidence_summary = {
        "evidence_quality_score": evidence.evidence_quality_score,
        "scanned_files": evidence.scanned_files,
        "scanned_functions": evidence.scanned_functions,
        "framework_evidence_count": evidence.framework_evidence_count,
        "has_tests": evidence.has_tests,
        "has_observability": evidence.has_observability,
        "has_schema_enforcement": evidence.has_schema_enforcement,
        "has_result_shaping": evidence.has_result_shaping,
        "has_pipeline_routing": evidence.has_pipeline_routing,
        "has_token_usage_tracking": evidence.has_token_usage_tracking,
        "warnings": evidence.evidence_warnings,
    }

    return ReverseAssessment(
        status=status,
        complexity_score=complexity_score,
        diagnostic_code=diagnostic_code,
        reasons=reasons[:MAX_REASONS],
        alternatives=alternatives[:MAX_ALTERNATIVES],
        high_risk_reqs=_collect_reverse_high_risk_reqs(rtm, gap_report),
        score_breakdown=breakdown,
        evidence_summary=evidence_summary,
    )

def sa_phase3_node(state: PipelineState) -> dict:
    def sget(key, default=None):
        return state_sget(state, key, default)

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

        assessment = _assess_reverse_maintainability(sa_phase1, rtm, gap_report)
        output = {
            "status": assessment.status,
            "complexity_score": assessment.complexity_score,
            "decision": assessment.status,
            "diagnostic_code": assessment.diagnostic_code,
            "reasons": assessment.reasons,
            "alternatives": assessment.alternatives,
            "high_risk_reqs": assessment.high_risk_reqs,
            "score_breakdown": assessment.score_breakdown,
            "evidence_summary": assessment.evidence_summary,
        }
        thinking_msg = (
            f"reverse 규칙 기반 진단 완료: {assessment.status} "
            f"(점수 {assessment.complexity_score}, 증거 품질 {assessment.evidence_summary.get('evidence_quality_score', 0)})"
        )

        return {
            "sa_phase3": output,
            "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_phase3", "thinking": thinking_msg}],
            "current_step": "sa_phase3_done",
        }

    if action_type == "REVERSE_ENGINEER":
        assessment = _assess_reverse_maintainability(sa_phase1, rtm, gap_report)
        output = {
            "status": assessment.status,
            "complexity_score": assessment.complexity_score,
            "decision": assessment.status,
            "diagnostic_code": assessment.diagnostic_code,
            "reasons": assessment.reasons,
            "alternatives": assessment.alternatives,
            "high_risk_reqs": assessment.high_risk_reqs,
            "score_breakdown": assessment.score_breakdown,
            "evidence_summary": assessment.evidence_summary,
        }
        thinking_msg = (
            f"reverse 규칙 기반 진단 완료: {assessment.status} "
            f"(점수 {assessment.complexity_score}, 증거 품질 {assessment.evidence_summary.get('evidence_quality_score', 0)})"
        )

        return {
            "sa_phase3": output,
            "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_phase3", "thinking": thinking_msg}],
            "current_step": "sa_phase3_done",
        }

    # 모드에 따른 프롬프트 분기
    system_prompt = CREATE_SYSTEM_PROMPT

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

