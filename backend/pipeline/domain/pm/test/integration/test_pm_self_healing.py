"""
PM Self-Healing Integration Test (Final Corrected)
재시도 루프(_retry_loop)가 예외 상황을 감지하고 다시 시도하는 과정을
실제 예외 발생(raise ValidationError)을 통해 시뮬레이션합니다.
"""

import os
import sys
import json
from unittest.mock import MagicMock, patch
from dotenv import load_dotenv
from pydantic import ValidationError

# 경로 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../../"))

from pipeline.orchestration.graph import get_pm_pipeline
from pipeline.domain.pm.schemas import RequirementAnalyzerOutput, RequirementFeature, StackPlannerOutput, PMBundle

load_dotenv()

def test_pm_self_healing():
    print("\n" + "="*60)
    print(" [PM SELF-HEALING TEST] STARTING ".center(60, "="))
    print("="*60)

    # 1. 시퀀스 기반 Mock 응답 구성
    
    # [A] Req Analyzer 결과
    req_out = {
        "parsed": RequirementAnalyzerOutput(
            thinking="Req OK",
            features=[RequirementFeature(id="FEAT_001", category="Frontend", description="Test", priority="Must-have", dependencies=[], test_criteria="Criteria")]
        ),
        "raw": MagicMock(usage_metadata={"total_tokens": 10}),
        "parsing_error": None
    }
    
    # [B] Stack Planner 결과들 (실패 시 예외를 던지도록 side_effect에서 처리 예정)
    planner_fail_1 = {"error": "JSON 문법 상 괄호 누락"}
    planner_fail_2 = {"error": "필수 필드 'stack_mapping' 누락"}
    planner_success = {
        "parsed": StackPlannerOutput(
            thinking="Planner Fixed!",
            stack_mapping=[{"feature_id": "FEAT_001", "domain": "Frontend", "package": "react", "status": "APPROVED"}]
        ),
        "raw": MagicMock(usage_metadata={"total_tokens": 20}),
        "parsing_error": None
    }
    
    # [C] PM Analysis 결과
    mock_bundle = PMBundle(
        metadata={"session_id": "sh_test", "bundle_id": "sh_bndl", "version": "1.0", "phase": "PM", "artifact_type": "PM_BUNDLE", "created_at": "2026-04-15"},
        data={
            "rtm": [{"feature_id": "FEAT_001", "category": "Frontend", "description": "Test", "priority": "Must-have", "dependencies":[], "test_criteria": "OK"}],
            "tech_stacks": [{"feature_id": "FEAT_001", "domain": "Frontend", "package": "react", "status": "APPROVED"}]
        }
    )
    mock_bundle_parsed = MagicMock()
    mock_bundle_parsed.thinking = "Analysis OK"
    mock_bundle_parsed.bundle = mock_bundle
    mock_bundle_parsed.coverage_rate = 1.0  # float 타입 명시
    mock_bundle_parsed.warnings = []
    
    analysis_out = {
        "parsed": mock_bundle_parsed, 
        "raw": MagicMock(usage_metadata={"total_tokens": 30}),
        "parsing_error": None
    }

    mock_responses = [req_out, planner_fail_1, planner_fail_2, planner_success, analysis_out]
    call_count = 0

    def mock_invoke_side_effect(messages, **kwargs):
        nonlocal call_count
        if call_count >= len(mock_responses):
            return {"parsed": MagicMock(), "raw": MagicMock(), "parsing_error": None}
            
        res = mock_responses[call_count]
        call_count += 1
        
        # 에러 시뮬레이션: 예외를 던져야 _retry_loop가 재시도함
        if "error" in res:
            print(f"  [Mock LLM] Call {call_count}: Raising intentional error - {res['error']}")
            # ValidationError.from_exception_data는 Pydantic 2에서 예외를 강제로 만드는 가장 깔끔한 방법 중 하나입니다.
            raise ValueError(f"Intended LLM Error: {res['error']}")
        
        print(f"  [Mock LLM] Call {call_count}: Success (parsed returned)")
        return res

    # 2. Patch 적용
    with patch("pipeline.core.utils.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_structured_llm = MagicMock()
        
        mock_get_llm.return_value = mock_llm
        mock_llm.with_structured_output.return_value = mock_structured_llm
        mock_structured_llm.invoke.side_effect = mock_invoke_side_effect

        # 3. 파이프라인 실행
        initial_state = {
            "api_key": "test_key",
            "input_idea": "자가 복구 시나리오",
            "action_type": "CREATE",
            "run_id": "test_self_healing",
            "loop_count": 0,
            "thinking_log": []
        }

        print("\n[Node Execution with Multi-Level Failures Mocking]")
        app = get_pm_pipeline()
        
        try:
            final_state = app.invoke(initial_state)
            print("\n[V] PASS: 파이프라인 자가 복구 완주 성공")
        except Exception as e:
            print(f"\n[X] FAIL: 파이프라인 크래시: {e}")
            return

        # 4. 검증 결과 출력
        print("\n[Self-Healing Verification Metrics]")
        print(f"  - 총 LLM 호출 수: {call_count} (기대치: 5)")
        
        if call_count >= 5:
            print("  [V] PASS: 자가 복구 재시도 로직이 정상 작동함.")
        else:
            print(f"  [!] ERROR: 호출 수가 기대보다 적음 ({call_count}/5).")

        # 5. 최종 결과 출력
        pm_bundle = final_state.get("pm_bundle")
        if pm_bundle:
            print("\n[Final Output: PM_BUNDLE JSON]")
            print("-" * 40)
            print(json.dumps(pm_bundle, ensure_ascii=False, indent=2))
            print("-" * 40)

    print("\n" + "="*60)
    print(" [PM SELF-HEALING TEST] COMPLETED ".center(60, "="))
    print("="*60 + "\n")

if __name__ == "__main__":
    test_pm_self_healing()
