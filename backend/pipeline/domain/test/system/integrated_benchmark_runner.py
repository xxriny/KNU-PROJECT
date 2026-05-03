import os
import sys
import json
import time
from datetime import datetime
from typing import List, Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv

# 프로젝트 루트(backend) 경로 추가
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
sys.path.insert(0, ROOT_DIR)

from pipeline.orchestration.graph import get_pm_pipeline
from pipeline.domain.sa.nodes.component_scheduler import component_scheduler_node
from pipeline.domain.sa.nodes.sa_unified_modeler import sa_unified_modeler_node
from pipeline.domain.sa.nodes.sa_advisor import sa_advisor_node
from pipeline.domain.sa.nodes.sa_embedding import sa_embedding_node
from pipeline.domain.sa.test.sa_test_utils import UsageTracker
from version import DEFAULT_MODEL
from observability.logger import get_logger

load_dotenv()
logger = get_logger()

@dataclass
class IntegratedScenario:
    name: str
    input_idea: str
    description: str

# --------------------------------------------------------------------------------
# 통합 테스트 시나리오 (아이디어 기반)
# --------------------------------------------------------------------------------

SCENARIOS = [
    IntegratedScenario(
        name="INT-01: Intergalactic Logistics System",
        input_idea="우주 간 물류 배송 시스템을 만들어줘. 행성별 세금 계산, 상대성 이론을 적용한 유효기간 관리, 순환 참조 없는 공급망, 반물질 에스크로 결제, 영지식 증명 익명 인증이 필요해.",
        description="PM의 기획력과 SA의 설계 정밀도를 동시에 테스트하는 고난도 시나리오"
    )
]

def run_integrated_pipeline(scenario: IntegratedScenario, tracker: UsageTracker) -> Dict[str, Any]:
    """PM + SA 통합 파이프라인 실행"""
    api_key = os.getenv("GEMINI_API_KEY")
    
    # 1. PM Pipeline Execution (pm_analysis 제거됨: pm_embedding이 pm_bundle 자동 조립)
    print(f"\n[Step 1] Running PM Pipeline for idea: '{scenario.input_idea[:30]}...'")
    pm_app = get_pm_pipeline()
    pm_initial_state = {
        "api_key": api_key,
        "input_idea": scenario.input_idea,
        "action_type": "CREATE",
        "thinking_log": [],
        "run_id": f"INT_{datetime.now().strftime('%m%d_%H%M')}"
    }
    
    pm_final_state = pm_app.invoke(pm_initial_state)
    pm_bundle = pm_final_state.get("pm_bundle", {})
    rtm = pm_bundle.get("data", {}).get("rtm", [])
    
    print(f"   [PM DONE] Generated {len(rtm)} Requirements (RTM)")

    # 2. SA Pipeline Execution (sa_analysis 제거됨: sa_advisor가 QA + 조언 통합)
    print(f"\n[Step 2] Running SA Pipeline with PM Outputs...")
    
    sa_state = {
        **pm_final_state,
        "merged_project": {
            "mode": "CREATE",
            "plan": {"requirements_rtm": rtm}
        },
    }

    # SA Step 1: Scheduling
    sa_state.update(component_scheduler_node(sa_state))
    print(f"   [SA-1] Component Scheduler: {len(sa_state.get('component_scheduler_output', {}).get('components', []))} comps")

    # SA Step 2: Unified Modeling
    sa_state.update(sa_unified_modeler_node(sa_state))
    unified_out = sa_state.get("sa_unified_modeler_output", {})
    print(f"   [SA-2] Unified Modeler: {len(unified_out.get('apis', []))} APIs, {len(unified_out.get('tables', []))} Tables")

    # SA Step 3: SA Advisor (통합 QA + 수정 조언 + sa_arch_bundle 조립)
    print(f"   [SA-3] Running SA Advisor (QA + Recommendations)...")
    advisor_res = sa_advisor_node(sa_state)
    sa_state.update(advisor_res)
    
    # SA Step 4: Persistence (Embedding to RAG)
    print(f"   [SA-4] Persisting SA Design to RAG...")
    sa_state.update(sa_embedding_node(sa_state))
    
    advisor_out = advisor_res.get("sa_advisor_output", {})
    sa_output = advisor_res.get("sa_output", {})
    
    status = advisor_out.get("status", "UNKNOWN")
    gaps = advisor_out.get("gaps", [])
    recommendations = advisor_out.get("recommendations", [])
    
    print(f"   [SA-3 DONE] Status: {status} | Gaps: {len(gaps)} | Recommendations: {len(recommendations)}")
    if recommendations:
        for rec in recommendations[:3]:
            print(f"     → [{rec.get('priority')}] {rec.get('target')}: {rec.get('action')}")

    return {
        "pm_output": pm_bundle,
        "sa_output": sa_output,
        "advisor_output": advisor_out,
        "status": status,
        "gaps": gaps,
        "recommendations": recommendations,
    }

def run_benchmark():
    print("\n" + "="*80)
    print(" [INTEGRATED PM-SA DOMAIN BENCHMARK v2.0 (Advisor)] ".center(80, "="))
    print("="*80)

    results = []
    total_tracker = UsageTracker()

    for scenario in SCENARIOS:
        print(f"\n>>> Scenario: {scenario.name}")
        scenario_tracker = UsageTracker()
        
        try:
            with scenario_tracker.track():
                final_res = run_integrated_pipeline(scenario, scenario_tracker)
            
            summary = scenario_tracker.get_summary()
            results.append({
                "name": scenario.name,
                "status": final_res["status"],
                "input_idea": scenario.input_idea,
                "requirements_count": len(final_res["pm_output"].get("data", {}).get("rtm", [])),
                "api_count": len(final_res["sa_output"].get("data", {}).get("apis", [])),
                "table_count": len(final_res["sa_output"].get("data", {}).get("tables", [])),
                "component_count": len(final_res["sa_output"].get("data", {}).get("components", [])),
                "recommendation_count": len(final_res.get("recommendations", [])),
                "cost": summary["cost_usd"],
                "tokens": summary["total_tokens"],
                "duration": summary["duration_sec"],
                "gaps": final_res["gaps"],
                "recommendations": final_res["recommendations"],
            })
            
        except Exception as e:
            print(f"   [X] Failed: {e}")
            import traceback
            traceback.print_exc()

    # 결과 리포트 출력
    print("\n\n" + "="*80)
    print(" INTEGRATED BENCHMARK SUMMARY ".center(80, "-"))
    for r in results:
        print(f" - {r['name']}: Status={r['status']}, Cost=${r['cost']:.4f}, Recs={r['recommendation_count']}")
    print("="*80 + "\n")

    # 파일 저장
    report_path = os.path.join(os.path.dirname(__file__), "integrated_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Report saved to: {report_path}")

if __name__ == "__main__":
    run_benchmark()
