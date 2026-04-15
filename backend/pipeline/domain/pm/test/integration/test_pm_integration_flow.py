"""
PM Integration Flow Test
사용자 요구사항부터 최종 RAG 적재까지의 전 과정을 검증하며,
출력 규격(JSON)의 정합성과 ID 보존 여부를 직접 확인합니다.
"""

import os
import sys
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from pydantic import ValidationError

# 경로 설정 (test/integration -> pm -> domain -> pipeline -> backend)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../.."))

from pipeline.orchestration.graph import get_pm_pipeline
from pipeline.domain.pm.schemas import PMBundle
from pipeline.domain.pm.nodes.pm_db import query_pm_artifacts
from pipeline.domain.pm.nodes.stack_db import search_tech_stacks

load_dotenv()

def run_integration_test():
    print("\n" + "="*60)
    print(" [PM INTEGRATION FLOW TEST] STARTING ".center(60, "="))
    print("="*60)

    # 1. 입력 데이터 설정
    user_input = "React와 Zustand를 써서 장바구니 기능이랑 결제 기능을 만들어줘."
    run_id = f"test_intg_{datetime.now(timezone.utc).strftime('%H%M%S')}"
    
    initial_state = {
        "api_key": os.getenv("GEMINI_API_KEY"),
        "input_idea": user_input,
        "action_type": "CREATE",
        "run_id": run_id,
        "loop_count": 0,
        "thinking_log": []
    }

    print(f"\n[1/4] 파이프라인 실행 시작 (Run ID: {run_id})")
    print(f"  Input: \"{user_input}\"")
    
    app = get_pm_pipeline()
    try:
        final_state = app.invoke(initial_state)
        print("  파이프라인 실행 완료.")
    except Exception as e:
        print(f"  [FAIL] 파이프라인 실행 중 오류 발생: {e}")
        return

    # 2. 결과 추출 및 JSON 출력
    pm_bundle_raw = final_state.get("pm_bundle")
    print("\n[2/4] 최종 산출물(PM_BUNDLE) JSON 출력:")
    print("-" * 40)
    if pm_bundle_raw:
        print(json.dumps(pm_bundle_raw, ensure_ascii=False, indent=2))
    else:
        print("  [ERROR] pm_bundle 데이터가 결과에 없습니다.")
        return
    print("-" * 40)

    # 3. 규격 및 무결성 검증
    print("\n[3/4] 데이터 정합성 검증 시작...")
    
    # 가. Pydantic 스키마 검증
    try:
        pm_bundle = PMBundle.model_validate(pm_bundle_raw)
        print("  [V] PASS: PMBundle Pydantic 스키마 규격 일치.")
    except ValidationError as ve:
        print(f"  [X] FAIL: 스키마 규격 불일치!\n{ve}")
        return

    # 나. ID 보존 및 외래키(Foreign Key) 검증
    rtm_ids = [item.feature_id for item in pm_bundle.data.rtm]
    stack_refs = [item.feature_id for item in pm_bundle.data.tech_stacks]
    
    print(f"  - 생성된 기능 IDs: {rtm_ids}")
    print(f"  - 스택 매핑 IDs: {stack_refs}")
    
    missing_refs = [sid for sid in stack_refs if sid not in rtm_ids]
    if not missing_refs:
        print("  [V] PASS: 모든 기술 스택이 존재하는 기능 ID를 참조하고 있음.")
    else:
        print(f"  [X] FAIL: 존재하지 않는 기능 ID가 참조됨: {missing_refs}")

    # 4. RAG 적재 여부 최종 확인
    print("\n[4/4] RAG 저장소 반영 확인...")
    
    # PM/SA RAG 확인
    pm_rag_res = query_pm_artifacts(user_input, n_results=1)
    if pm_rag_res["ids"] and len(pm_rag_res["ids"][0]) > 0:
        print(f"  [V] PASS: PM RAG에 지식이 정상 적재됨. (최근 ID: {pm_rag_res['ids'][0][0]})")
    else:
        print("  [X] FAIL: PM RAG에서 저장된 지식을 찾을 수 없음.")

    print("\n" + "="*60)
    print(" [PM INTEGRATION FLOW TEST] COMPLETED ".center(60, "="))
    print("="*60 + "\n")

if __name__ == "__main__":
    run_integration_test()
