import json
import os
import sys
from typing import Dict, Any

# 프로젝트 루트 및 backend 경로 자동 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.abspath(os.path.join(current_dir, "../../../../../"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from pipeline.domain.sa.nodes.api_modeler import api_modeler_node
from pipeline.domain.sa.nodes.db_schema_architect import db_schema_architect_node
from sa_unit_judge import judge_node
from dotenv import load_dotenv

load_dotenv()

def run_test_scenario(scenario_name: str, state: Dict[str, Any], use_judge: bool = True):
    """
    특정 시나리오에 대해 api_modeler_node와 db_schema_architect_node를 차례대로 실행하고 결과를 채점합니다.
    """
    print(f"\n" + "*" * 80)
    print(f" [SCENARIO] {scenario_name} ".center(80, " "))
    print("*" * 80 + "\n")

    # 1. API Modeler 실행
    api_result = api_modeler_node(state)
    if "error" in api_result:
        print(f"[ERROR] API Modeler Failed: {api_result['error']}")
        return None
    state.update(api_result)

    api_output = api_result.get("api_modeler_output")
    if not api_output:
        print(f"[ERROR] 'api_modeler_output' not found.")
        return None

    # 2. DB Schema Architect 실행
    db_result = db_schema_architect_node(state)
    if "error" in db_result:
        print(f"[ERROR] DB Schema Architect Failed: {db_result['error']}")
        return None
    state.update(db_result)

    db_output = db_result.get("db_schema_architect_output")
    if not db_output:
        print(f"[ERROR] 'db_schema_architect_output' not found.")
        return None
        
    # 3. 결과 요약 출력
    print(f"[SUCCESS] Modeling Result Summary:")
    print(f"   - API Thinking: {api_output.get('thinking', 'N/A')[:50]}...")
    print(f"   - DB Thinking: {db_output.get('thinking', 'N/A')[:50]}...")
    print(f"   - APIs: {len(api_output.get('apis', []))} defined")
    print(f"   - Tables: {len(db_output.get('tables', []))} defined")
    
    # 4. Judge 평가
    if use_judge:
        # 통합된 출력을 만들어서 judge에 전달
        combined_output = {
            "apis": api_output.get("apis", []),
            "tables": db_output.get("tables", [])
        }
        judge_res = judge_node("api_and_data_modeler", state, combined_output)
        return judge_res
    return None

def main():
    # --- 시나리오: 표준적인 게시판 확장 ---
    scenario_1 = {
        "scenario_name": "Standard Board Extension",
        "state": {
            "component_scheduler_output": {
                "components": [
                    {"domain": "Backend", "component_name": "PostService", "role": "게시글 CRUD 처리", "dependencies": []},
                    {"domain": "Backend", "component_name": "S3Service", "role": "이미지 업로드", "dependencies": []}
                ]
            },
            "merged_project": {
                "plan": {"requirements_rtm": [{"id": "REQ-1", "desc": "게시글 작성 시 여러 장의 이미지 업로드 및 S3 저장"}]}
            },
            "api_key": "[.env]",
            "model": "gemini-2.5-flash"
        }
    }

    scenarios = [scenario_1]
    
    total_scenarios = len(scenarios)
    passed_count = 0

    for idx, sc in enumerate(scenarios):
        print(f"\n[Running Test {idx+1}/{total_scenarios}]")
        judge_res = run_test_scenario(sc["scenario_name"], sc["state"])
        if judge_res and judge_res.passed:
            passed_count += 1

    print("\n" + "="*80)
    print(f" [FINAL TEST REPORT] ".center(80, "="))
    print(f" Total Scenarios: {total_scenarios}")
    print(f" Passed: {passed_count}")
    print(f" Failed: {total_scenarios - passed_count}")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
