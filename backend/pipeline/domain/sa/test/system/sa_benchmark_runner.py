import os
import sys
import json
import time
from datetime import datetime
from typing import List, Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv

# 경로 설정
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../"))
sys.path.insert(0, ROOT_DIR)

from pipeline.domain.sa.test.sa_test_utils import UsageTracker
from pipeline.domain.sa.nodes.component_scheduler import component_scheduler_node
from pipeline.domain.sa.nodes.api_data_modeler import api_data_modeler_node
from pipeline.domain.sa.nodes.sa_analysis import sa_analysis_node
from pipeline.core.state import PipelineState, make_sget
from pipeline.core.node_base import NodeContext
from version import DEFAULT_MODEL
from observability.logger import get_logger

load_dotenv()
logger = get_logger()

@dataclass
class SAScenario:
    name: str
    rtm: List[Dict[str, str]]
    description: str

# --------------------------------------------------------------------------------
# [TEST CASE] 
# --------------------------------------------------------------------------------
SCENARIOS = [
    SAScenario(
        name="ST-01: Nightmare Intergalactic Logistics",
        description="복합적 계층 구조 및 참조 무결성 검증을 위한 고난도 시나리오",
        rtm=[
            {"id": "REQ-001", "desc": "다중 주권 과세 엔진: 행성 간 상이한 세율 및 관세 협정 참조 설계."},
            {"id": "REQ-002", "desc": "상대성 재고 관리: 시간 왜곡(Time Dilation) 계수를 적용한 유효기간 계산."},
            {"id": "REQ-003", "desc": "무한 순환 공급망: 품목 간 재귀적 구조에서 순환 참조 감지 및 차단."},
            {"id": "REQ-004", "desc": "반물질 에스크로: 에너지 균형 검증 로직이 포함된 결제 트랜잭션."},
            {"id": "REQ-005", "desc": "영지식 증명 익명 인증: 공개키와 해시 기반의 보안 스키마 설계."}
        ]
    )
]

# --------------------------------------------------------------------------------
# [BENCHMARK RUNNER] 
# --------------------------------------------------------------------------------

def run_sa_pipeline(scenario: SAScenario) -> Dict[str, Any]:
    """단일 파이프라인 실행을 수행합니다."""
    api_key = os.getenv("GEMINI_API_KEY")
    model = DEFAULT_MODEL # 프로젝트 표준 모델 사용
    
    # 1. 초기 상태 설정
    state = {
        "run_id": f"BENCH_{datetime.now().strftime('%m%d_%H%M')}",
        "action_type": "CREATE",
        "merged_project": {
            "mode": "CREATE", 
            "plan": {"requirements_rtm": scenario.rtm}
        },
        "pm_bundle": {"data": {"rtm": scenario.rtm}}, # 폴백용 추가
        "thinking_log": [],
        "skip_rag_persistence": False # 즉시 저장 활성화
    }

    # 에러 세부 사항 저장용
    error_details = []

    def log_output(node_name, result):
        if "error" in result:
            error_msg = result["error"]
            error_details.append({
                "node": node_name,
                "error": error_msg,
                "timestamp": datetime.now().isoformat()
            })
            print(f"   ❌ [ERROR from {node_name}] Details saved to error_details.json")
            return

        keys = list(result.keys())
        summary = ""
        if "component_scheduler_output" in result:
            summary = f"Components: {len(result['component_scheduler_output'].get('components', []))}"
        elif "api_data_modeler_output" in result:
            out = result["api_data_modeler_output"]
            summary = f"APIs: {len(out.get('apis', []))}, Tables: {len(out.get('tables', []))}"
        elif "sa_analysis_output" in result:
            out = result["sa_analysis_output"]
            summary = f"Status: {out.get('status')}, Gaps: {len(out.get('gaps', []))}"
        print(f"   📤 [OUTPUT from {node_name}] Keys: {keys} | {summary}")

    # 2. 파이프라인 순차 실행
    print(f"\n[Execution: Initial Design]")
    
    # Step 1: Scheduling
    comp_res = component_scheduler_node(state)
    log_output("component_scheduler", comp_res)
    state.update(comp_res)

    # Step 2: Data Modeling
    model_res = api_data_modeler_node(state)
    log_output("api_data_modeler", model_res)
    state.update(model_res)

    # Step 3: Analysis
    analysis_res = sa_analysis_node(state)
    log_output("sa_analysis", analysis_res)
    state.update(analysis_res)

    analysis_out = state.get("sa_analysis_output", {})
    status = analysis_out.get("status")
    gaps = analysis_out.get("gaps", [])

    if status == "PASS":
        print(f"   ✅ PASS achieved!")
    else:
        print(f"   ⚠️ Result: {status} with {len(gaps)} gaps.")
        
    # STEP 4: 통합 Judge
    print(f"   [Step 4] Running Integration Judge for Developer Feedback...")
    from pipeline.domain.sa.test.integration.sa_integration_judge import judge_integration
    
    judge_res = judge_integration(scenario.name, scenario.rtm, state.get("sa_analysis_output"))

    return {
        "status": status,
        "gaps_final": gaps,
        "bundle": state.get("sa_analysis_output"),
        "judge_report": judge_res 
    }
        
    # STEP 4: 통합 Judge (개발용 피드백 포함)
    print(f"   [Step 4] Running Integration Judge for Developer Feedback...")
    from pipeline.domain.sa.test.integration.sa_integration_judge import judge_integration
    
    # 현재 시나리오 데이터를 바탕으로 최종 품질 평가
    judge_res = judge_integration(scenario.name, scenario.rtm, state.get("sa_analysis_output"))

    return {
        "status": status,
        "retry_count": min(retry_count, max_retries),
        "gaps_final": gaps,
        "bundle": state.get("sa_analysis_output"),
        "judge_report": judge_res 
    }

def run_sa_benchmark():
    print("\n" + "="*80)
    print(" [SA PIPELINE ARCHITECTURE BENCHMARK v2.0] ".center(80, "="))
    print("="*80)

    results = []
    total_cost = 0.0
    total_tokens = 0

    for scenario in SCENARIOS:
        print(f"\n🚀 Running Scenario: {scenario.name}")
        print(f"   Desc: {scenario.description}")
        
        tracker = UsageTracker()
        
        try:
            with tracker.track():
                final_res = run_sa_pipeline(scenario)
            
            summary = tracker.get_summary()
            results.append({
                "name": scenario.name,
                "status": final_res["status"],
                "tokens": summary["total_tokens"],
                "cost": summary["cost_usd"],
                "duration": summary["duration_sec"],
                "judge_report": final_res.get("judge_report") # 상세 피드백 추가
            })
            total_cost += summary["cost_usd"]
            total_tokens += summary["total_tokens"]
            
        except Exception as e:
            print(f"   [X] Scenario failed with error: {e}")
            import traceback
            traceback.print_exc()

    # 결과 요약 출력
    print("\n\n" + "="*80)
    print(" BENCHMARK RESULTS SUMMARY ".center(80, "="))
    print("="*80)
    
    print(f"{'Scenario Name':<40} | {'Status':<6} | {'Tokens':<10} | {'Cost'}")
    print("-" * 80)
    for r in results:
        print(f"{r['name']:<40} | {r['status']:<6} | {r['tokens']:<10,} | ${r['cost']:.5f}")

    print("="*80)
    print(f" TOTAL TOKENS: {total_tokens:,}")
    print(f" TOTAL COST:   ${total_cost:.5f}")
    
    # 6. 리포트 저장
    report_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(report_dir, exist_ok=True)
    
    final_report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_tokens": total_tokens,
            "total_cost": total_cost
        },
        "scenarios": results
    }

    report_path = os.path.join(report_dir, "report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=2, ensure_ascii=False)

    # 에러 세부 사항 별도 저장
    if error_details:
        error_path = os.path.join(report_dir, "error_details.json")
        with open(error_path, "w", encoding="utf-8") as f:
            json.dump(error_details, f, indent=2, ensure_ascii=False)
        print(f"📂 Error details saved to: {error_path}")
    
    print(f"\n📂 Development report saved to: {report_path}")
    print("="*80 + "\n")

if __name__ == "__main__":
    run_sa_benchmark()
