from __future__ import annotations

import json
import os
import sys
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from pipeline.core.utils import call_structured, get_effective_key
from pipeline.domain.dev_tracking.test.system.rubrics import JUDGE_SYSTEM_PROMPT


load_dotenv()


class DevTrackingJudgeOutput(BaseModel):
    scores: dict[str, int] = Field(..., description="각 평가 항목별 1-5점 점수")
    rationale: dict[str, str] = Field(..., description="각 점수의 근거")
    failure_modes: list[str] = Field(default_factory=list, description="발견된 실패 모드")
    required_fixes: list[str] = Field(default_factory=list, description="반드시 수정해야 하는 항목")
    overall_feedback: str = Field(..., description="전체 평가 요약")
    passed: bool = Field(..., description="운영 적용 가능한 품질인지 여부")


def _compact_dev_tracking_result(result: dict[str, Any]) -> dict[str, Any]:
    # author: xxrin
    # Judge 입력이 과도하게 커지지 않도록 품질 판단에 필요한 Dev Tracking 결과만 압축한다.
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    return {
        "status": result.get("status"),
        "approval_status": data.get("approval_status"),
        "current_step": data.get("current_step"),
        "next_action": data.get("dev_tracking_next_action"),
        "pr_context": data.get("pr_context"),
        "pm_report": data.get("pm_report"),
        "gap_report": data.get("gap_report"),
        "intent_classification": data.get("intent_classification"),
        "milestone_status": data.get("milestone_status"),
        "approval_task": data.get("approval_task"),
        "embedding_result": data.get("embedding_result"),
        "analysis_persistence": data.get("analysis_persistence"),
        "llm_warnings": data.get("llm_warnings"),
        "timeline": result.get("timeline") or data.get("timeline") or [],
    }


def judge_dev_tracking_result(
    *,
    scenario: dict[str, Any],
    result: dict[str, Any],
    judge_model: str = "",
    api_key: str = "",
) -> DevTrackingJudgeOutput | None:
    # author: xxrin
    # Dev Tracking 결과 품질 평가는 일반 pytest와 분리된 수동/벤치마크 실행 경로에서만 LLM judge로 수행한다.
    effective_key = get_effective_key(api_key or os.getenv("GEMINI_API_KEY", ""))
    model = judge_model or os.getenv("DEV_TRACKING_JUDGE_MODEL", "gemini-2.5-flash")
    user_msg = "\n\n".join(
        [
            "### [Scenario]",
            json.dumps(scenario, ensure_ascii=False, indent=2, default=str),
            "### [Dev Tracking Output]",
            json.dumps(_compact_dev_tracking_result(result), ensure_ascii=False, indent=2, default=str),
        ]
    )

    try:
        judge_res = call_structured(
            api_key=effective_key,
            model=model,
            schema=DevTrackingJudgeOutput,
            system_prompt=JUDGE_SYSTEM_PROMPT,
            user_msg=user_msg,
            temperature=0.0,
        )
        return judge_res.parsed
    except Exception as exc:
        print(f"[DevTrackingJudge] judge failed: {exc}")
        return None
