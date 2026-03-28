"""
SA Phase 3 — REVERSE_ENGINEER 모드 유지보수성 평가 (규칙 기반)
기존 시스템의 코드 증거·프레임워크 식별 결과를 종합하여 유지보수성을 진단합니다.
"""

import os
from typing import List

from pydantic import BaseModel, Field


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


def _grep_any(root: str, tokens: list[str], limit: int = 50_000) -> bool:
    """root 아래 모든 .py 파일을 탐색하여 tokens 중 하나라도 포함하는지 확인.
    파일당 최대 limit 바이트만 읽어 성능을 보호한다."""
    if not root or not os.path.isdir(root):
        return False
    skip_dirs = {"__pycache__", ".git", "node_modules", ".venv", "venv", "Data", "dist", "build"}
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            try:
                with open(os.path.join(current_root, name), encoding="utf-8", errors="replace") as fh:
                    text = fh.read(limit)
                if any(tok in text for tok in tokens):
                    return True
            except OSError:
                continue
    return False


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

    has_pipeline_routing = _grep_any(root, ["StateGraph", "add_conditional_edges"])
    has_schema_enforcement = (
        _grep_any(root, ["with_structured_output"])
        and _grep_any(root, ["BaseModel"])
    )
    has_token_usage_tracking = _grep_any(
        root, ["call_structured_with_usage", "input_tokens", "output_tokens"]
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


def assess_reverse(sget, sa_phase1: dict, rtm: list, gap_report: list) -> dict:
    """REVERSE_ENGINEER 모드의 유지보수성 평가. 결과 dict와 thinking 메시지를 반환."""
    if not rtm:
        ready, reason = _validate_phase1_readiness(sa_phase1)
        if not ready:
            return {
                "output": {
                    "status": "Needs_Clarification",
                    "complexity_score": 0,
                    "decision": "Needs_Clarification",
                    "diagnostic_code": "PHASE1_CONTEXT_INSUFFICIENT",
                    "reasons": [f"코드 구조 분석 컨텍스트 부족: {reason}"],
                    "alternatives": ["source_dir를 프로젝트 루트로 지정하고 다시 분석하세요."],
                    "high_risk_reqs": [],
                },
                "thinking_msg": "phase1 컨텍스트 부족 — reverse 진단 생략",
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
    return {"output": output, "thinking_msg": thinking_msg}
