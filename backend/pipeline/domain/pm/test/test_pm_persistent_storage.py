import os
import sys
import json
import shutil
from datetime import datetime, timezone
from dotenv import load_dotenv

# 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, "../../../../"))
sys.path.insert(0, backend_dir)

from pipeline.domain.pm.nodes.pm_analysis import pm_analysis_node
from connectors.result_logger import DATA_DIR

load_dotenv()

def test_persistence():
    print("\n[PM Persistent Storage & Knowledge Test]")
    
    # 1. 이전 유산 흔적 확인 및 제거 (테스트 클린업)
    legacy_data_dir = os.path.join(backend_dir, "Data")
    if os.path.exists(legacy_data_dir) and os.listdir(legacy_data_dir):
        print(f"  Cleaning legacy Data folder: {legacy_data_dir}")
        # Note: 실제 운영 환경은 비워두어야 하지만 테스트를 위해 확인만 함
    
    # 2. 테스트 데이터 준비
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    state = {
        "api_key": os.getenv("GEMINI_API_KEY"),
        "run_id": run_id,
        "features": [
            {"id": "FEAT_TEST_001", "description": "Persistence Test Feature", "category": "Test", "priority": "Must-have"}
        ],
        "stack_planner_output": {
            "stack_mapping": [
                {"feature_id": "FEAT_TEST_001", "domain": "Test", "package": "pytest", "status": "APPROVED"}
            ]
        },
        "metadata": {"project_name": "Storage_Test_Project"},
        "thinking_log": []
    }

    # 3. pm_analysis_node 실행 (이 내부에서 stack_db 저장이 일어남)
    print(f"  Running pm_analysis_node (ID: {run_id})...")
    result = pm_analysis_node(state)
    pm_bundle = result.get("pm_bundle")

    # 4. 결과 저장 모사 (pipeline_runner가 하는 일)
    from connectors.result_logger import save_result
    saved_path = save_result(pm_bundle)
    print(f"  JSON Result saved to: {saved_path}")

    # 5. 검증 (Assertion)
    print("\n[Validation Results]")
    
    # 가. 신규 세션 저장소 확인
    if "storage" in saved_path and "sessions" in saved_path:
        print("  [V] PASS: Result saved in 'backend/storage/sessions'")
    else:
        print(f"  [X] FAIL: Unexpected save path: {saved_path}")

    # 나. ChromaDB 신규 경로 확인
    db_path = os.path.join(backend_dir, "storage", "vector_db")
    if os.path.exists(db_path):
        print("  [V] PASS: ChromaDB (vector_db) exists in 'backend/storage/'")
    else:
        print("  [X] FAIL: ChromaDB path not found in storage")

    # 다. MD 파일 생성 여부 확인
    md_file = os.path.join(os.path.dirname(saved_path), saved_path.replace(".json", "_PROJECT_STATE.md"))
    if not os.path.exists(md_file):
        print("  [V] PASS: PROJECT_STATE.md was NOT created (Legacy removed)")
    else:
        print("  [X] FAIL: Legacy PROJECT_STATE.md still being created")

if __name__ == "__main__":
    test_persistence()
