"""
PM Benchmark Runner
주요 시나리오별로 파이프라인을 실행하고, Gemini 3.0 Pro를 통해 
품질 정밀 평가(G-Eval)를 수행하여 리포트를 생성합니다.
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# 경로 설정 (backend 위단계가 아닌 backend 자체가 pythonpath에 포함되도록 조정)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../"))

from pipeline.orchestration.graph import get_pm_pipeline
from pipeline.core.utils import call_structured
from pipeline.domain.pm.benchmark.rubrics import JUDGE_SYSTEM_PROMPT
from pipeline.core.cost_manager import calculate_cost

load_dotenv()

# Judge LLM 출력 스키마
class JudgeOutput(BaseModel):
    scores: Dict[str, int]
    rationale: Dict[str, str]
    overall_feedback: str

def run_benchmark(target_model: str = "gemini-2.5-flash"):
    print(f"\n" + "="*60)
    print(f" [PM-BENCH: {target_model}] STARTING ".center(60, "="))
    print("="*60)

    # 1. 시나리오 로드
    scenario_path = os.path.join(os.path.dirname(__file__), "scenarios.json")
    with open(scenario_path, "r", encoding="utf-8") as f:
        scenarios = json.load(f)

    app = get_pm_pipeline()
    api_key = os.getenv("GEMINI_API_KEY")
    judge_model = "gemini-3.1-pro-preview"  # 실제 지원 모델명으로 수정 (3.1 Pro)

    results = []

    for sc in scenarios:
        # 새로운 시나리오(결제 시스템)로 최종 검증 수행
        if sc['id'] != "SCEN_001":
            continue
            
        print(f"\n[Scenario] {sc['name']} ({sc['id']}) Running...")
        
        start_time = time.time()
        initial_state = {
            "api_key": api_key,
            "input_idea": sc["prompt"],
            "action_type": "CREATE",
            "model": target_model,
            "run_id": f"bench_{sc['id']}_{int(time.time())}",
            "loop_count": 0,
            "thinking_log": []
        }

        # 파이프라인 실행
        try:
            final_state = app.invoke(initial_state)
            latency = time.time() - start_time
            
            # 실제 total_retries 추출 (PipelineState에서 누적된 값)
            retry_count = final_state.get("total_retries", 0)
            
            # 결과물 수집
            pm_bundle = final_state.get("pm_bundle", {})
            bundle_json = json.dumps(pm_bundle, ensure_ascii=False, indent=2)

            # 2. 채점 (Judge LLM 호출)
            print(f"  -> Judging with {judge_model}...")
            judge_res = call_structured(
                api_key=api_key,
                model=judge_model,
                schema=JudgeOutput,
                system_prompt=JUDGE_SYSTEM_PROMPT,
                user_msg=f"### [Scenario Configuration]\n{json.dumps(sc, ensure_ascii=False)}\n\n### [Pipeline Output]\n{bundle_json}"
            )
            
            eval_data = judge_res.parsed
            
            # --- 비용 및 토큰 집계 (Phase 0) ---
            # 1. 파이프라인 소모량 (Flash)
            pipeline_usage = final_state.get("accumulated_usage", [])
            pipeline_cost = final_state.get("accumulated_cost", 0.0)
            
            # 2. 채점자 소모량 (Pro)
            judge_usage = judge_res.usage
            judge_cost = calculate_cost(judge_model, judge_usage["input_tokens"], judge_usage["output_tokens"])
            
            results.append({
                "scenario": sc,
                "latency": latency,
                "scores": eval_data.scores,
                "rationale": eval_data.rationale,
                "feedback": eval_data.overall_feedback,
                "retry_count": retry_count,
                "pipeline_usage": pipeline_usage,
                "pipeline_cost": pipeline_cost,
                "judge_usage": judge_usage,
                "judge_cost": judge_cost,
                "total_run_cost": pipeline_cost + judge_cost
            })
            print(f"  [V] Scored: Avg {sum(eval_data.scores.values())/len(eval_data.scores):.1f}")

        except Exception as e:
            print(f"  [X] Failed: {e}")

    # 3. 리포트 생성
    generate_markdown_report(target_model, results)

def generate_markdown_report(model_name: str, results: List[Dict]):
    report_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(report_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"report_{model_name}_{timestamp}.md"
    filepath = os.path.join(report_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# PM Domain Benchmark Report: {model_name}\n\n")
        f.write(f"- **Execution Time**: {datetime.now().isoformat()}\n")
        f.write(f"- **Judge Model**: gemini-3.0-pro\n\n")
        
        f.write("## 1. Executive Summary\n\n")
        avg_scores = {}
        for r in results:
            for k, v in r["scores"].items():
                avg_scores[k] = avg_scores.get(k, 0) + v
        
        f.write("| Metric | Average Score |\n")
        f.write("| :--- | :--- |\n")
        for k, v in avg_scores.items():
            f.write(f"| {k} | {v/len(results):.2f} / 5.0 |\n")
        
        f.write("\n## 2. Detailed Scenario Results\n\n")
        for r in results:
            sc = r["scenario"]
            f.write(f"### {sc['name']} ({sc['id']})\n")
            f.write(f"- **Latency**: {r['latency']:.1f}s\n")
            f.write(f"- **Scores**:\n")
            for m, s in r["scores"].items():
                f.write(f"  - {m}: **{s} / 5**\n")
            
            f.write("\n#### [Rationale]\n")
            for m, rat in r["rationale"].items():
                f.write(f"- **{m}**: {rat}\n")
            
            f.write(f"\n#### Overall Feedback\n> {r['feedback']}\n\n")
            
            f.write(f"#### [Token & Cost Analysis]\n")
            f.write(f"| Part | Input | Output | cost ($) |\n")
            f.write(f"| :--- | :--- | :--- | :--- |\n")
            
            # 파이프라인 합계 계산
            p_in = sum(u["input"] for u in r["pipeline_usage"])
            p_out = sum(u["output"] for u in r["pipeline_usage"])
            f.write(f"| **Pipeline (Flash)** | {p_in:,} | {p_out:,} | ${r['pipeline_cost']:.6f} |\n")
            f.write(f"| **Judge (Pro)** | {r['judge_usage']['input_tokens']:,} | {r['judge_usage']['output_tokens']:,} | ${r['judge_cost']:.6f} |\n")
            f.write(f"| **TOTAL** | - | - | **${r['total_run_cost']:.6f}** |\n\n")
            
            f.write("---\n")

    print(f"\n[REPORT CREATED] {filepath}")

if __name__ == "__main__":
    # 기본 모델 평가 실행
    run_benchmark(os.getenv("DEFAULT_MODEL", "gemini-2.5-flash"))
