"""
PM Logical Gate Integration Test
Analyzer의 기능 개수와 Planner의 매핑 개수가 불일치할 때
PM Analysis가 이를 차단(Gate)하고 RAG 적재를 막는지 검증합니다.
"""

import os
import sys
import json
from unittest.mock import MagicMock, patch
from dotenv import load_dotenv

# 경로 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../../"))

from pipeline.orchestration.graph import get_pm_pipeline
from pipeline.domain.pm.schemas import PMAnalysisOutput, PMBundle

load_dotenv()

def test_pm_logical_gate():
    print("\n" + "="*60)
    print(" [PM LOGICAL GATE TEST] STARTING ".center(60, "="))
    print("="*60)

    # 1. 의도적인 불일치 데이터 구성
    # Features는 3개인데 Stack Mapping은 1개만 있음 (Hallucination 상황 시뮬레이션)
    mock_features = [
        {"id": "FEAT_001", "category": "A", "description": "F1"},
        {"id": "FEAT_002", "category": "B", "description": "F2"},
        {"id": "FEAT_003", "category": "C", "description": "F3"},
    ]
    
    mock_stack_mapping = [
        {"feature_id": "FEAT_001", "domain": "Web", "package": "react", "status": "APPROVED"}
        # FEAT_002, FEAT_003 누락!
    ]

    # 2. PM Analysis 노드의 LLM 호출 모킹
    # 로직 검증이 목적이므로 LLM도 누락된 결과(1개만 포함된 번들)를 반환한다고 가정
    with patch("pipeline.domain.pm.nodes.pm_analysis.call_structured_with_usage") as mock_call:
        mock_analysis_out = MagicMock()
        mock_analysis_out.thinking = "Inconsistent data detected."
        mock_analysis_out.warnings = ["Missing mappings for FEAT_002, FEAT_003"]
        mock_analysis_out.coverage_rate = 0.33
        
        # 번들 데이터도 불완전하게 생성됨
        mock_bundle = MagicMock()
        mock_bundle.model_dump.return_value = {
            "metadata": {"version": "1.0", "phase": "PM", "artifact_type": "PM_BUNDLE"},
            "data": {
                "rtm": mock_features,
                "tech_stacks": mock_stack_mapping
            }
        }
        mock_analysis_out.bundle = mock_bundle
        
        mock_call.return_value = (mock_analysis_out, {"total_tokens": 100})

        # 3. 파이프라인 그래프 실행
        # 선행 노드들이 실제 API를 호출하지 않도록 모킹 (그래프가 임포트한 네임스페이스를 직접 패치)
        from pipeline.orchestration.graph import _PipelineRegistry
        _PipelineRegistry._cache.clear()
        
        with patch("pipeline.orchestration.graph.requirement_analyzer_node") as mock_req, \
             patch("pipeline.orchestration.graph.stack_planner_node") as mock_planner, \
             patch("pipeline.orchestration.graph.pm_embedding_node") as mock_embedding:
            
            # 모킹된 노드들이 입력된 sget 데이터를 그대로 통과시키거나 필요한 것만 추가하도록 설정
            mock_req.side_effect = lambda state: {"features": mock_features}
            mock_planner.side_effect = lambda state: {"stack_planner_output": {"stack_mapping": mock_stack_mapping}}

            initial_state = {
                "api_key": "test_key",
                "run_id": "test_gate_fail",
                "input_idea": "test",
                "action_type": "CREATE",
                "thinking_log": [],
                "loop_count": 0
            }

            print("\n[Executing Pipeline with Mocked Preceding Nodes]")
            app = get_pm_pipeline()
            final_state = app.invoke(initial_state)

            # 4. 검증
            print("\n[Verification]")
            is_fail = final_state.get("is_integration_fail", False)
            error_msg = final_state.get("error", "")
            
            print(f"  - Integration Fail Flag: {is_fail}")
            print(f"  - Error Message: {error_msg}")
            
            # pm_embedding 노드가 실행되었는지 확인 (Gating 검증)
            embedding_called = mock_embedding.called
            print(f"  - pm_embedding_node called: {embedding_called}")

            if is_fail and not embedding_called:
                print("\n[V] PASS: 논리적 불일치가 감지되어 RAG 적재가 차단되었습니다.")
            else:
                if not is_fail:
                    print("\n[X] FAIL: 불일치를 감지하지 못했습니다.")
                if embedding_called:
                    print("\n[X] FAIL: 불완전한 데이터가 RAG 적재 노드로 전달되었습니다. (Gate 작동 실패)")

    print("\n" + "="*60)
    print(" [PM LOGICAL GATE TEST] COMPLETED ".center(60, "="))
    print("="*60 + "\n")

if __name__ == "__main__":
    test_pm_logical_gate()
