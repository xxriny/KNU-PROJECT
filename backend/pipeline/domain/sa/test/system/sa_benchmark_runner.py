import os
import sys
import json
import time
from datetime import datetime
from tabulate import tabulate  # 설치되어 있지 않으면 리스트로 출력
from dotenv import load_dotenv

# 경로 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../../"))

from pipeline.domain.sa.test.sa_test_utils import UsageTracker
# 기존 테스트 함수들을 import 하기 위해 경로 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../integration/"))

import test_sa_new_project
import test_sa_project_extension
import test_sa_integrity_loop
import test_sa_hybrid_rag

load_dotenv()

def run_sa_benchmark():
    print("\n" + "="*80)
    print(" [SA ARCHITECTURE PIPELINE BENCHMARK] ".center(80, "="))
    print("="*80)

    scenarios = [
        ("IT-01: New Project", test_sa_new_project.test_new_project_design),
        ("IT-02: Project Extension", test_sa_project_extension.test_project_extension),
        ("IT-03: Integrity Loop", test_sa_integrity_loop.test_integrity_loop),
        ("ST-01: Hybrid RAG", test_sa_hybrid_rag.test_hybrid_rag_integration)
    ]

    results = []
    total_cost = 0.0
    total_tokens = 0

    for name, test_fn in scenarios:
        print(f"\n>>> Running Scenario: {name}...")
        tracker = UsageTracker()
        
        try:
            with tracker.track():
                test_fn()
            
            summary = tracker.get_summary()
            results.append([
                name, 
                "PASS", # 기본적으로 예외 없으면 PASS (Score는 개별 출력됨)
                f"{summary['total_tokens']:,}",
                f"${summary['cost_usd']:.5f}",
                f"{summary['duration_sec']:.1f}s"
            ])
            total_cost += summary['cost_usd']
            total_tokens += summary['total_tokens']
            
        except Exception as e:
            print(f" [X] Scenario {name} failed: {e}")
            results.append([name, "FAIL", "-", "-", "-"])

    # 결과 테이블 출력
    headers = ["Scenario", "Status", "Tokens", "Cost (USD)", "Duration"]
    print("\n\n" + "="*80)
    print(" BENCHMARK RESULTS SUMMARY ".center(80, "="))
    print("="*80)
    
    try:
        from tabulate import tabulate
        print(tabulate(results, headers=headers, tablefmt="grid"))
    except ImportError:
        # tabulate가 없는 경우 간단히 출력
        print(f"{'Scenario':<25} | {'Status':<10} | {'Tokens':<10} | {'Cost':<10} | {'Duration':<10}")
        print("-" * 80)
        for row in results:
            print(f"{row[0]:<25} | {row[1]:<10} | {row[2]:<10} | {row[3]:<10} | {row[4]:<10}")

    print("="*80)
    print(f" TOTAL TOKENS: {total_tokens:,}")
    print(f" TOTAL COST:   ${total_cost:.5f}")
    print("="*80 + "\n")

if __name__ == "__main__":
    run_sa_benchmark()
