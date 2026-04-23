import json
import os
import sys
from dotenv import load_dotenv

# 프로젝트 루트 및 backend 경로 자동 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.abspath(os.path.join(current_dir, "../../../../../"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from pipeline.domain.sa.nodes.component_scheduler import component_scheduler_node
from pipeline.domain.sa.nodes.api_modeler import api_modeler_node
from pipeline.domain.sa.nodes.db_schema_architect import db_schema_architect_node
from pipeline.domain.sa.nodes.sa_analysis import sa_analysis_node
from pipeline.core.node_base import NodeContext
from sa_integration_judge import judge_integration

load_dotenv()

def test_integrity_loop():
    """통합 테스트 3: 고난도 설계 무결성 및 피드백 루프 (Nightmare Scenario 2.0)"""
    scenario_name = "IT-03: Stress-Test (Intergalactic Logistics & Sovereign Fund)"
    
    requirements = [
        {"id": "REQ-001", "desc": "다중 주권 과세 엔진: 각 행성(Tenant)은 고유한 세율을 가지며, 행성 간 관세 협정 테이블을 참조하여 세금이 계산되어야 함."},
        {"id": "REQ-002", "desc": "상대성 재고 관리: 시간 지연(Time Dilation) 효과로 인해, 각 행성에서의 재고 유효 기간이 다르게 계산됨."},
        {"id": "REQ-003", "desc": "무한 순환 공급망: 품목(Item)은 하위 품목을 가질 수 있으며, 순환 의존성(Circular Dependency) 감지 로직 필요."},
        {"id": "REQ-004", "desc": "반물질 에스크로 결제: 모든 결제는 '에스크로' 상태를 거치며, 에너지 균형이 맞지 않으면 예외를 발생시켜야 함."},
        {"id": "REQ-005", "desc": "영지식 증명 기반 익명 인증: 사용자 테이블에는 개인정보 대신 공개키와 약속 해시만 저장함."}
    ]
    
    api_key = os.getenv("GEMINI_API_KEY")
    state = {
        "run_id": "it_stress_2026",
        "action_type": "CREATE",
        "merged_project": {"mode": "CREATE", "plan": {"requirements_rtm": requirements}},
        "thinking_log": []
    }

    def get_ctx(curr_state):
        return NodeContext(
            state=curr_state,
            api_key=api_key,
            model="gemini-2.0-flash-exp",
            sget=lambda k, default=None: curr_state.get(k, default)
        )

    print(f"\n>>> Running Full SA Pipeline with Nightmare Scenario...")
    
    # 1. Component Scheduler
    print(" - [1/3] Scheduling Components...")
    state.update(component_scheduler_node(get_ctx(state)))
    
    # 2. API & Data Modeler
    print(" - [2/4] Modeling API Interfaces...")
    state.update(api_modeler_node(get_ctx(state)))
    
    print(" - [3/4] Architecting DB Schemas...")
    state.update(db_schema_architect_node(get_ctx(state)))
    
    # 3. SA Analysis (Judge)
    print(" - [4/4] Analyzing Architecture Quality (Pinpoint Feedback)...")
    state.update(sa_analysis_node(get_ctx(state)))
    
    final_bundle = state["sa_analysis_output"]
    
    print(f"▶ Final Status: {final_bundle.get('status')}")
    print(f"▶ Gaps Found: {len(final_bundle.get('gaps', []))}")

    return judge_integration(scenario_name, requirements, final_bundle)

if __name__ == "__main__":
    test_integrity_loop()
