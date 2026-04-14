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
from pipeline.core.utils import call_structured_with_usage
from pipeline.domain.pm.schemas import PMAnalysisOutput, PMBundle
from pipeline.domain.pm.nodes.stack_db import upsert_bundle_knowledge
from observability.logger import get_logger
from version import DEFAULT_MODEL

logger = get_logger()

PM_ANALYSIS_SYSTEM_PROMPT = """당신은 PM 파이프라인의 최종 단계인 '통합 분석가(QA-PM)'입니다.
Requirement Analyzer(기능 명세)와 Stack Planner(기술 스택 배정)의 결과물이
논리적으로 일치하는지 최종 확인하고, RAG에 적재될 최종 PM_BUNDLE을 생성합니다.

[핵심 규칙]
1. '의존성 체크': A 기능이 B 기능에 의존한다면, 두 기능의 기술 스택이 호환되는지 검증한다.
   - 예: FEAT_002가 FEAT_001에 의존하는데, 001은 FastAPI이고 002는 Django면 경고를 발행한다.
2. '누락 체크': Analyzer가 만든 모든 기능(feature_id)에 Stack Planner의 결과값이 매핑되었는지 확인한다.
   - 매핑되지 않은 기능은 warnings에 추가하고, tech_stacks에는 포함하지 않는다.
3. '데이터 압축': 불필요한 서술은 제외하고 에이전트가 읽기 좋은 순수 JSON 데이터로 정제한다.
   - PENDING_CRAWL 상태의 스택은 tech_stacks에 포함하되, status를 'PENDING_CRAWL'로 유지한다.
4. coverage_rate는 전체 기능 중 APPROVED 스택이 매핑된 기능의 비율(0.0~1.0)로 계산한다.
"""


def _build_user_message(features: List[Dict], stack_mapping: List[Dict]) -> str:
    """LLM에게 전달할 입력 메시지 구성"""
    rtm_summary = json.dumps(
        [{"feature_id": f.get("id"), "category": f.get("category"),
          "description": f.get("description"), "priority": f.get("priority"),
          "dependencies": f.get("dependencies", []),
          "test_criteria": f.get("test_criteria", "")}
         for f in features],
        ensure_ascii=False, indent=2
    )
    stack_summary = json.dumps(
        [{"feature_id": m.get("feature_id"), "domain": m.get("domain"),
          "package": m.get("package"), "status": m.get("status")}
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
    approved_ids = {m.get("feature_id") for m in stack_mapping if m.get("status") == "APPROVED"}
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
    stack_mapping: List[Dict] = planner_out.get("stack_mapping", [])

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
        out, usage = call_structured_with_usage(
            api_key=api_key,
            model=model,
            schema=PMAnalysisOutput,
            system_prompt=PM_ANALYSIS_SYSTEM_PROMPT,
            user_msg=user_msg,
            temperature=0.05,  # 결정론적 검증이 중요하므로 최저 온도
        )

        # LLM이 계산한 coverage_rate가 있으면 사용, 없으면 사전 계산값 사용
        final_coverage = out.coverage_rate if out.coverage_rate > 0 else coverage_rate

        # PM_BUNDLE을 dict로 직렬화
        bundle_dict = out.bundle.model_dump()

        # metadata 보완 (run_id, created_at 등)
        bundle_dict["metadata"]["session_id"] = run_id
        bundle_dict["metadata"]["bundle_id"] = f"{run_id}_PM_BNDL"
        bundle_dict["metadata"]["created_at"] = datetime.now(timezone.utc).isoformat()

        thinking_msg = (
            f"[QA-PM] Coverage: {final_coverage:.1%} | "
            f"Warnings: {len(out.warnings)} | "
            f"RTM: {len(bundle_dict['data']['rtm'])} items | "
            f"Stacks: {len(bundle_dict['data']['tech_stacks'])} items"
        )
        logger.info(thinking_msg)

        # [Knowledge Persistence] 최종 번들 지식화 저장
        try:
            metadata = sget("metadata", {})
            project_name = metadata.get("project_name", "unnamed")
            upsert_bundle_knowledge(run_id, bundle_dict, project_name=project_name)
        except Exception as db_err:
            logger.warning(f"Failed to persist knowledge to stack_db: {db_err}")

        return {
            "pm_bundle": bundle_dict,
            "pm_coverage_rate": final_coverage,
            "pm_warnings": out.warnings,
            "thinking_log": (sget("thinking_log", []) or []) + [
                {"node": "pm_analysis", "thinking": out.thinking or thinking_msg}
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
