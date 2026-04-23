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
from pipeline.domain.sa.nodes.sa_unified_modeler import sa_unified_modeler_node
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
SCENARIOS = [
    SAScenario(
        name="ST-01: Nightmare Intergalactic Logistics",
        description="복합적 계층 구조 및 참조 무결성 검증을 위한 고난도 시나리오 (RTM x5)",
        rtm=[
            {"id": "REQ-001", "desc": "다중 주권 과세 엔진: 행성 간 상이한 세율 및 관세 협정 참조 설계."},
            {"id": "REQ-002", "desc": "상대성 재고 관리: 시간 왜곡(Time Dilation) 계수를 적용한 유효기간 계산."},
            {"id": "REQ-003", "desc": "무한 순환 공급망: 품목 간 재귀적 구조에서 순환 참조 감지 및 차단."},
            {"id": "REQ-004", "desc": "반물질 에스크로: 에너지 균형 검증 로직이 포함된 결제 트랜잭션."},
            {"id": "REQ-005", "desc": "영지식 증명 익명 인증: 공개키와 해시 기반의 보안 스키마 설계."}
        ]
    )
]

def run_sa_pipeline(scenario: SAScenario, error_details: list) -> Dict[str, Any]:
    """단일 파이프라인 실행을 수행합니다."""
    api_key = os.getenv("GEMINI_API_KEY")
    model = DEFAULT_MODEL
    
    state = {
        "run_id": f"BENCH_{datetime.now().strftime('%m%d_%H%M')}",
        "action_type": "CREATE",
        "merged_project": {
            "mode": "CREATE", 
            "plan": {"requirements_rtm": scenario.rtm}
        },
        "pm_bundle": {"data": {"rtm": scenario.rtm}},
        "thinking_log": [],
        "skip_rag_persistence": True
    }

    def log_output(node_name, result):
        if "error" in result:
            error_msg = result["error"]
            error_details.append({
                "node": node_name,
                "error": error_msg,
                "timestamp": datetime.now().isoformat()
            })
            print(f"   [ERROR from {node_name}] {error_msg}")
            return True
        
        summary = ""
        if "component_scheduler_output" in result:
            summary = f"Components: {len(result['component_scheduler_output'].get('components', []))}"
        elif "sa_unified_modeler_output" in result:
            out = result["sa_unified_modeler_output"]
            summary = f"APIs: {len(out.get('apis', []))}, Tables: {len(out.get('tables', []))}"
        elif "sa_analysis_output" in result:
            out = result["sa_analysis_output"]
            summary = f"Status: {out.get('status')}, Gaps: {len(out.get('gaps', [])) if isinstance(out.get('gaps'), list) else 'Block'}"
        
        print(f"   [OUTPUT from {node_name}] | {summary}")
        return False

    print(f"\n[Execution: Initial Design]")
    
    # Step 1: Scheduling
    state.update(component_scheduler_node(state))
    log_output("component_scheduler", state)

    # Step 2: Unified System Modeling (API + DB)
    state.update(sa_unified_modeler_node(state))
    log_output("sa_unified_modeler", state)

    # Step 4: Analysis (Benchmark 전용 Judge로 활용)
    print(f"   [Step 4] Running Native SA Analysis as Judge...")
    analysis_res = sa_analysis_node(state)
    log_output("sa_analysis", analysis_res)
    
    analysis_out = analysis_res.get("sa_analysis_output", {})
    status = analysis_out.get("status", "FAIL")
    gaps = analysis_out.get("gaps", [])

    judge_report = {
        "score": 5 if status == "PASS" else (3 if status == "WARNING" else 1),
        "rationale": analysis_out.get("thinking", ""),
        "interface_consistency": "Gaps 확인" if gaps else "완벽함",
        "requirement_coverage": f"{len(scenario.rtm)}개 요구사항 분석 완료"
    }

    return {
        "status": status,
        "tokens": 0,
        "cost": 0.0,
        "judge_report": judge_report,
        "gaps": gaps
    }

def run_sa_benchmark():
    print("\n" + "="*80)
    print(" [SA PIPELINE ARCHITECTURE BENCHMARK v4.0 (Unified)] ".center(80, "="))
    print("="*80)

    results = []
    error_details = []
    total_cost = 0.0
    total_tokens = 0
    total_input = 0
    total_output = 0

    for scenario in SCENARIOS:
        print(f"\n[RUN] Running Scenario: {scenario.name}")
        tracker = UsageTracker()
        
        try:
            with tracker.track():
                final_res = run_sa_pipeline(scenario, error_details)
            
            summary = tracker.get_summary()
            results.append({
                "name": scenario.name,
                "status": final_res["status"],
                "input_tokens": summary["input_tokens"],
                "output_tokens": summary["output_tokens"],
                "total_tokens": summary["total_tokens"],
                "cost": summary["cost_usd"],
                "duration": summary["duration_sec"],
                "judge_report": final_res.get("judge_report"),
                "gaps": final_res.get("gaps")
            })
            total_cost += summary["cost_usd"]
            total_tokens += summary["total_tokens"]
            total_input += summary["input_tokens"]
            total_output += summary["output_tokens"]
            
        except Exception as e:
            print(f"   [X] Scenario failed with error: {e}")
            import traceback
            traceback.print_exc()

    # 요약 출력 및 저장 로직 생략 (기존과 동일)
    print("\n\n" + "="*80)
    print(f" TOTAL INPUT:  {total_input:,}")
    print(f" TOTAL OUTPUT: {total_output:,}")
    print(f" TOTAL TOKENS: {total_tokens:,}")
    print(f" TOTAL COST:   ${total_cost:.5f}")
    print("="*80 + "\n")

    # 리포트 저장
    report_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(report_dir, exist_ok=True)
    final_report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {"total_input": total_input, "total_output": total_output, "total_cost": total_cost},
        "scenarios": results
    }
    with open(os.path.join(report_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    run_sa_benchmark()
