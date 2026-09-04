import os
import sys
import json
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔 코드페이지(cp949)에서 이모지/한글 출력 시 크래시 방지

# 프로젝트 루트(backend)를 검색 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../.."))

from pipeline.orchestration.graph import get_pm_pipeline

load_dotenv()

def test_pm_self_correction_loop():
    print("\n[PM FULL LOOP TEST] Starting...")

    # 1. 초기 상태 설정 (RAG에 Chart Library가 없는 상황 연출)
    initial_state = {
        "api_key": os.getenv("GEMINI_API_KEY"),
        "input_idea": "실시간 주식 차트 대시보드 기능을 만들어줘.",
        "action_type": "CREATE",
        "stack_rag_context": "Approved Stacks: React 18, Zustand, Tailwind CSS, FastAPI. (No charting libraries found)",
        "loop_count": 0,
        "thinking_log": []
    }

    # 2. 파이프라인 실행
    app = get_pm_pipeline()
    print("\n[Running] Pipeline started (Knowledge-gap detection -> Crawling -> Re-planning is automatic)")
    final_state = app.invoke(initial_state)

    # 3. 결과 출력
    print("\n" + "="*50)
    print("[RESULT ANALYSIS]")
    print("="*50)

    loop_count = final_state.get("loop_count", 0)
    print(f"  Total loop count: {loop_count}")
    print(f"  State keys: {list(final_state.keys())}")

    # StackPlannerOutput 스키마: th(thinking) / m(stack_mapping) / gs(global_stacks)
    planner_out = final_state.get("stack_planner_output", {})
    mapping = planner_out.get("m", [])

    print(f"\n  TechStack Mappings ({len(mapping)} items):")
    for item in mapping:
        status_icon = "[APPROVED]" if item["status"] == "APPROVED" else "[PENDING]"
        print(f"    {status_icon} [{item['f_id']}] {item['dom']} : {item['pkg']}")
        if item["status"] == "PENDING_CRAWL" and item.get("query"):
            print(f"      -> Crawl query: {item['query']}")

    print("\n  Planner thinking:")
    print(f"    {planner_out.get('th', 'N/A')[:200]}")

    # 검증
    if loop_count > 1:
        print("\n[SUCCESS] Self-correction loop triggered!")
    else:
        print(f"\n[INFO] Loop count={loop_count}. No additional loop triggered.")
        pending = [item for item in mapping if item["status"] == "PENDING_CRAWL"]
        if pending:
            print(f"  PENDING items: {[item['pkg'] for item in pending]}")
            print("  -> Loop was expected but did not trigger. Check router logic.")

if __name__ == "__main__":
    test_pm_self_correction_loop()
