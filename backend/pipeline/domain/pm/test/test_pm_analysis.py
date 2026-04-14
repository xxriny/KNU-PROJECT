import os
import sys
import json
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))
from pipeline.domain.pm.nodes.pm_analysis import pm_analysis_node

load_dotenv()

def test_pm_analysis():
    print("\n[PM Analysis Node Test]")

    # 1. 테스트용 features (requirement_analyzer 출력 모사)
    features = [
        {"id": "FEAT_001", "category": "Backend", "priority": "Must-have",
         "description": "사용자 이메일 및 비밀번호 기반 로그인 API 제공",
         "dependencies": [], "test_criteria": "이메일 형식 오류 시 400 에러 반환"},
        {"id": "FEAT_002", "category": "Frontend", "priority": "Must-have",
         "description": "실시간 주식 차트 시각화",
         "dependencies": ["FEAT_001"], "test_criteria": "차트 데이터 200ms 내 렌더링"},
        {"id": "FEAT_003", "category": "Database", "priority": "Should-have",
         "description": "사용자 데이터 영구 저장",
         "dependencies": [], "test_criteria": "데이터 유실 없이 저장 확인"},
    ]

    # 2. 테스트용 stack_planner_output (stack_planner 출력 모사)
    stack_mapping = [
        {"feature_id": "FEAT_001", "domain": "Backend",
         "package": "fastapi", "status": "APPROVED", "reason": "RAG 승인"},
        {"feature_id": "FEAT_002", "domain": "Frontend",
         "package": "recharts", "status": "APPROVED", "reason": "RAG 승인"},
        {"feature_id": "FEAT_002", "domain": "Frontend",
         "package": "React 18", "status": "APPROVED", "reason": "RAG 승인"},
        {"feature_id": "FEAT_003", "domain": "Database",
         "package": "postgresql", "status": "APPROVED", "reason": "RAG 승인"},
        # FEAT_002가 의존하는 FEAT_001과 동일 도메인 체크용
    ]

    state = {
        "api_key": os.getenv("GEMINI_API_KEY"),
        "features": features,
        "stack_planner_output": {"thinking": "test", "stack_mapping": stack_mapping},
        "thinking_log": []
    }

    print("Running pm_analysis_node...")
    result = pm_analysis_node(state)

    # 출력
    print("\n" + "="*50)
    pm_bundle = result.get("pm_bundle", {})
    coverage = result.get("pm_coverage_rate", 0)
    warnings = result.get("pm_warnings", [])

    print(f"  Coverage Rate: {coverage:.1%}")
    print(f"  Warnings ({len(warnings)}):")
    for w in warnings:
        print(f"    - {w}")

    meta = pm_bundle.get("metadata", {})
    data = pm_bundle.get("data", {})
    print(f"\n  Bundle ID: {meta.get('bundle_id')}")
    print(f"  RTM Items: {len(data.get('rtm', []))}")
    print(f"  TechStack Items: {len(data.get('tech_stacks', []))}")

    print("\n  PM_BUNDLE (JSON):")
    print(json.dumps(pm_bundle, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    test_pm_analysis()
