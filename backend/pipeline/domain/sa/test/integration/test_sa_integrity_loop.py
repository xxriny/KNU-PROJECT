import json
import os
import sys
from dotenv import load_dotenv

# 프로젝트 루트 및 backend 경로 자동 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.abspath(os.path.join(current_dir, "../../../../../"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from pipeline.domain.sa.nodes.sa_analysis import sa_analysis_node
from sa_integration_judge import judge_integration

load_dotenv()

def test_integrity_loop():
    """통합 테스트 3: 설계 무결성 및 피드백 루프 (Image 29)"""
    scenario_name = "IT-03: Integrity Loop (Missing Table Detection)"
    
    requirements = [{"id": "REQ-301", "desc": "상품 목록 조회"}]
    
    # 의도적인 결함 주입: API는 설계되었으나 Table이 누락됨
    state = {
        "merged_project": {"plan": {"requirements_rtm": requirements}},
        "component_scheduler_output": {"components": [{"component_name": "ProductController", "role": "상품 처리"}]},
        "api_data_modeler_output": {
            "apis": [{"endpoint": "GET /api/v1/products", "description": "상품 목록 조회"}],
            "tables": [] # 결함: products 테이블 누락
        },
        "api_key": "[.env]",
        "model": "gemini-2.5-flash",
        "run_id": "it_03_loop"
    }

    print(f"\n>>> Running Integrity Check (Expecting FAIL)")
    
    # SA Analysis 실행 (결함을 찾아야 함)
    res_a = sa_analysis_node(state)
    
    final_bundle = res_a["sa_analysis_output"]
    
    # 결과 출력
    print(f"▶ Analysis Status: {final_bundle.get('status')}")
    print(f"▶ Analysis Gaps: {final_bundle.get('gaps')}")

    judge_integration(scenario_name, requirements, final_bundle)

if __name__ == "__main__":
    test_integrity_loop()
