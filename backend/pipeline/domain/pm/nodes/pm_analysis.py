"""
PM Analysis Node (QA-PM)
Requirement Analyzer의 RTM과 Stack Planner의 기술 스택 매핑을 통합하여
최종 PM_BUNDLE을 생성하고 검증합니다.

페르소나: 최종 품질 통제관(QA-PM)
- 의존성 체크: 의존 관계에 있는 기능들의 스택이 호환되는지 확인
- 누락 체크: 모든 기능에 스택이 매핑되었는지 확인
- 데이터 압축: 순수 JSON으로 정제된 PM_BUNDLE 생성
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, List

from pipeline.core.state import PipelineState, make_sget
from pipeline.core.utils import call_structured
from pipeline.domain.pm.schemas import PMAnalysisOutput, PMBundle
from observability.logger import get_logger
from version import DEFAULT_MODEL

logger = get_logger()

PM_ANALYSIS_SYSTEM_PROMPT = """# 역할: 통합 분석가 (QA-PM)
## 목표: 기능 명세와 기술 스택의 논리적 일관성 검증 및 PM_BUNDLE 생성.
## 규칙:
1. 의존성 체크: 기능 간 의존 시 기술적 호환성 확인 (예: FastAPI와 Django 혼용 금지).
2. 누락 체크: 기능은 있으나 매핑된 스택이 없으면 `warnings`에 추가.
3. 데이터 정제: 순수 JSON 정제. PENDING_CRAWL 상태 유지.
4. 지표 계산: `coverage_rate` = APPROVED 개수 / 전체 기능 개수.
"""


def _build_user_message(features: List[Dict], stack_mapping: List[Dict]) -> str:
    """LLM에게 전달할 입력 메시지 구성"""
    rtm_summary = json.dumps(
        [{"id": f.get("id"), "cat": f.get("cat"),
          "desc": f.get("desc"), "pri": f.get("pri"),
          "deps": f.get("deps", []),
          "tc": f.get("tc", "")}
         for f in features],
        ensure_ascii=False, indent=2
    )
    stack_summary = json.dumps(
        [{"f_id": m.get("f_id"), "dom": m.get("dom"),
          "pkg": m.get("pkg"), "status": m.get("status")}
         for m in stack_mapping],
        ensure_ascii=False, indent=2
    )
    return (
        f"### [RTM: 원자화된 기능 목록]\n{rtm_summary}\n\n"
        f"### [TECH_STACKS: 기술 스택 매핑 결과]\n{stack_summary}\n\n"
        "위 두 데이터를 검증하고 최종 PM_BUNDLE을 생성하세요."
    )


def _calculate_coverage(features: List[Dict], stack_mapping: List[Dict]) -> float:
    """APPROVED 스택이 매핑된 기능 비율 계산"""
    if not features:
        return 0.0
    feature_ids = {f.get("id") for f in features}
    approved_ids = {m.get("f_id") for m in stack_mapping if m.get("status") == "APPROVED"}
    covered = feature_ids & approved_ids
    return round(len(covered) / len(feature_ids), 3)


def pm_analysis_node(state: PipelineState) -> Dict[str, Any]:
    sget = make_sget(state)
    logger.info("=== [Node Entry] pm_analysis_node ===")

    api_key = sget("api_key", "")
    model = sget("model", DEFAULT_MODEL)
    run_id = sget("run_id", datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"))

    # 입력 데이터 수집
    features: List[Dict] = sget("features", [])
    planner_out: Dict = sget("stack_planner_output", {})
    stack_mapping: List[Dict] = planner_out.get("m", [])

    if not features:
        logger.warning("pm_analysis_node: No features found, skipping.")
        return {
            "pm_bundle": {},
            "thinking_log": (sget("thinking_log", []) or []) + [
                {"node": "pm_analysis", "thinking": "features 없음, 번들 생성 생략."}
            ]
        }

    # 사전 계산 (LLM 비용 절감용)
    coverage_rate = _calculate_coverage(features, stack_mapping)
    logger.info(f"Coverage rate (pre-LLM): {coverage_rate:.1%}")

    user_msg = _build_user_message(features, stack_mapping)

    try:
        res = call_structured(
            api_key=api_key,
            model=model,
            schema=PMAnalysisOutput,
            system_prompt=PM_ANALYSIS_SYSTEM_PROMPT,
            user_msg=user_msg,
            temperature=0.05,
        )
        out = res.parsed
        retry_count = res.retry_count

        # LLM이 계산한 coverage_rate가 있으면 사용, 없으면 사전 계산값 사용
        final_coverage = out.coverage_rate if out.coverage_rate > 0 else coverage_rate

        # PM_BUNDLE을 dict로 직렬화
        bundle_dict = out.bundle.model_dump()

        # metadata 보완 (run_id, created_at 등 강제 주입)
        bundle_dict["metadata"]["session_id"] = run_id
        bundle_dict["metadata"]["bundle_id"] = f"{run_id}_PM_BNDL"
        bundle_dict["metadata"]["created_at"] = datetime.now(timezone.utc).isoformat()

        # [Logical Gate] 노드 간 불일치 물리적 검증
        feature_ids = {f.get("id") for f in features}
        mapped_ids = {m.get("f_id") for m in stack_mapping}
        missing_ids = feature_ids - mapped_ids
        
        is_integration_fail = False
        gate_thinking = ""
        if missing_ids:
            is_integration_fail = True
            gate_thinking = f"[INTEGRATION_FAIL] 논리적 불일치 감지: {len(missing_ids)}개의 기능에 스택이 매핑되지 않았습니다. (누락: {list(missing_ids)})"
            logger.error(gate_thinking)

        thinking_msg = (
            f"[QA-PM] Coverage: {final_coverage:.1%} | "
            f"Warnings: {len(out.warnings)} | "
            f"RTM: {len(bundle_dict['data']['rtm'])} items | "
            f"Stacks: {len(bundle_dict['data']['tech_stacks'])} items"
        )
        if gate_thinking:
            thinking_msg = gate_thinking + "\n" + thinking_msg
            
        logger.info(thinking_msg)

        # [Knowledge Persistence] -> pm_embedding_node에서 처리하도록 위임 (Gate 확인 후)

        return {
            "pm_bundle": bundle_dict,
            "pm_coverage_rate": final_coverage,
            "pm_warnings": out.warnings,
            "is_integration_fail": is_integration_fail,
            "total_retries": sget("total_retries", 0) + retry_count,
            "error": gate_thinking if is_integration_fail else None,
            "thinking_log": (sget("thinking_log", []) or []) + [
                {"node": "pm_analysis", "thinking": out.th or thinking_msg}
            ],
            "current_step": "pm_analysis_done",
        }

    except Exception as e:
        logger.exception("pm_analysis_node failed")
        # 폴백: LLM 없이 데이터만 조립
        fallback_bundle = {
            "metadata": {
                "session_id": run_id,
                "bundle_id": f"{run_id}_PM_BNDL",
                "version": "v1.0",
                "phase": "PM",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            "data": {
                "rtm": [
                    {"feature_id": f.get("id"), "category": f.get("category"),
                     "description": f.get("description"), "priority": f.get("priority"),
                     "dependencies": f.get("dependencies", []),
                     "test_criteria": f.get("test_criteria", "")}
                    for f in features
                ],
                "tech_stacks": [
                    {"feature_id": m.get("feature_id"), "domain": m.get("domain"),
                     "package": m.get("package"), "status": m.get("status")}
                    for m in stack_mapping if m.get("status") == "APPROVED"
                ],
            }
        }
        return {
            "pm_bundle": fallback_bundle,
            "pm_coverage_rate": coverage_rate,
            "pm_warnings": [f"LLM 검증 실패 (폴백 사용): {str(e)[:200]}"],
            "thinking_log": (sget("thinking_log", []) or []) + [
                {"node": "pm_analysis", "thinking": f"LLM 실패, 폴백 사용: {e}"}
            ],
            "current_step": "pm_analysis_done",
        }
