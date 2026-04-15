"""
PM System Reliability Test (Internal Integrity Focus)
복합 요구사항(RBAC)을 입력하여 엔드투엔드 파이프라인의 
원자화, 논리적 정합성, 그리고 RAG 적재 무결성을 검증합니다.
"""

import os
import sys
import json
import time
from datetime import datetime
from dotenv import load_dotenv

# 경로 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../../"))

from pipeline.orchestration.graph import get_pm_pipeline
from pipeline.domain.pm.test.db.inspect_rag import inspect_pm_sa_rag

load_dotenv()

def test_pm_system_reliability():
    print("\n" + "="*60)
    print(" [PM SYSTEM RELIABILITY TEST] STARTING ".center(60, "="))
    print("="*60)

    # 1. 입력 시나리오: 복합 엔터프라이즈 요구사항
    # (인터넷 크롤링 루프를 최소화하기 위해 이미 RAG에 있을 법하거나 명확한 스택 사용)
    user_prompt = (
        "Node.js와 PostgreSQL을 기반으로 한 유저 관리 및 역할 기반 권한 제어(RBAC) 시스템을 설계해줘. "
        "보안을 위해 JWT 인증이 포함되어야 하며, 모든 API는 RESTful하게 설계되어야 함."
    )
    
    run_id = f"sys_rel_{datetime.now().strftime('%m%d_%H%M%S')}"
    
    initial_state = {
        "api_key": os.getenv("GEMINI_API_KEY"),
        "input_idea": user_prompt,
        "action_type": "CREATE",
        "run_id": run_id,
        "loop_count": 0,
        "thinking_log": []
    }

    # 2. 파이프라인 실행
    print(f"\n[1/3] Pipeline Execution (RunID: {run_id})")
    print(f"  Input: {user_prompt[:50]}...")
    
    app = get_pm_pipeline()
    start_time = time.time()
    
    try:
        final_state = app.invoke(initial_state)
        elapsed = time.time() - start_time
        print(f"  [V] Pipeline completed in {elapsed:.1f}s")
    except Exception as e:
        print(f"  [X] Pipeline crashed: {e}")
        return

    # 3. 내부 정합성 검증 (Internal Precision)
    print("\n[2/3] Internal Precision Verification")
    
    features = final_state.get("features", [])
    pm_bundle = final_state.get("pm_bundle", {})
    rtm = pm_bundle.get("data", {}).get("rtm", [])
    tech_stacks = pm_bundle.get("data", {}).get("tech_stacks", [])
    
    print(f"  - 원자화된 기능 수: {len(features)}")
    print(f"  - 번들 RTM 항목 수: {len(rtm)}")
    print(f"  - 매핑된 기술 스택 수: {len(tech_stacks)}")

    # 검증 기준 1: 기능 분해 (최소 3개 이상 예상: 인증, 유저, 권한 등)
    if len(features) >= 3:
        print(f"  [V] Atomicity Detail: {len(features)} features generated.")
    else:
        print(f"  [!] Warning: 기능 분해가 충분히 이루어지지 않음 ({len(features)}).")

    # 검증 기준 2: 메타데이터 보존성
    bundle_metadata = pm_bundle.get("metadata", {})
    if bundle_metadata.get("session_id") == run_id:
        print("  [V] Metadata Check: RunID preserved in PM_BUNDLE.")
    else:
        print(f"  [X] Metadata Mismatch: Expected {run_id}, got {bundle_metadata.get('session_id')}")

    # 검증 기준 3: 일관성 (Node.js/PostgreSQL 전파 여부)
    all_node_js = all("node" in str(s.get("package")).lower() for s in tech_stacks if s.get("domain") == "Backend")
    if all_node_js:
        print("  [V] Logic Consistency: Node.js correctly propagated to backend stacks.")

    # 4. RAG 적재 무결성 확인
    print("\n[3/3] RAG Persistence Verification")
    # 약간의 적재 지연 고려
    time.sleep(2) 
    
    print(f"\n  Checking PM_SA_VECTOR_DB for RunID: {run_id}...")
    # inspect_rag.py의 로직을 활용하여 해당 RunID로 적재된 문서 확인
    db_results = inspect_pm_sa_rag(filter_metadata={"session_id": run_id})
    
    doc_count = len(db_results.get("ids", []))
    print(f"  - DB에서 검색된 문서 수: {doc_count}")
    
    if doc_count > 0:
        print(f"  [V] Persistence Success: {doc_count} documents indexed in ChromaDB.")
        # 첫 번째 문서 샘플 확인
        sample_meta = db_results.get("metadatas", [{}])[0]
        print(f"  - Sample Metadata: {json.dumps(sample_meta, ensure_ascii=False)}")
    else:
        print("  [X] Persistence Failure: No documents found in RAG for this session.")

    print("\n" + "="*60)
    print(" [PM SYSTEM RELIABILITY TEST] COMPLETED ".center(60, "="))
    print("="*60 + "\n")

if __name__ == "__main__":
    test_pm_system_reliability()
