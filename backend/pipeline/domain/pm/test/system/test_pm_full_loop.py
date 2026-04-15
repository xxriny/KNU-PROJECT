import os
import sys
import json
from dotenv import load_dotenv

# ?„ë¡œ?íŠ¸ ë£¨íŠ¸(backend)ë¥?ê²€??ê²½ë¡œ??ì¶”ê?
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../.."))

from pipeline.orchestration.graph import get_pm_pipeline

load_dotenv()

def test_pm_self_correction_loop():
    print("\n[PM FULL LOOP TEST] Starting...")
    
    # 1. ì´ˆê¸° ?íƒœ ?¤ì • (RAG??Chart Libraryê°€ ?†ëŠ” ?í™© ?°ì¶œ)
    initial_state = {
        "api_key": os.getenv("GEMINI_API_KEY"),
        "input_idea": "?¤ì‹œê°?ì£¼ì‹ ì°¨íŠ¸ ?€?œë³´??ê¸°ëŠ¥??ë§Œë“¤?´ì¤˜.",
        "action_type": "CREATE",
        "stack_rag_context": "Approved Stacks: React 18, Zustand, Tailwind CSS, FastAPI. (No charting libraries found)",
        "loop_count": 0,
        "thinking_log": []
    }

    # 2. ?Œì´?„ë¼???¤í–‰
    app = get_pm_pipeline()
    print("\n[Running] Pipeline started (Knowledge-gap detection -> Crawling -> Re-planning is automatic)")
    final_state = app.invoke(initial_state)

    # 3. ê²°ê³¼ ì¶œë ¥
    print("\n" + "="*50)
    print("[RESULT ANALYSIS]")
    print("="*50)
    
    loop_count = final_state.get("loop_count", 0)
    print(f"  Total loop count: {loop_count}")
    print(f"  State keys: {list(final_state.keys())}")

    planner_out = final_state.get("stack_planner_output", {})
    mapping = planner_out.get("stack_mapping", [])
    
    print(f"\n  TechStack Mappings ({len(mapping)} items):")
    for m in mapping:
        status_icon = "[APPROVED]" if m["status"] == "APPROVED" else "[PENDING]"
        print(f"    {status_icon} [{m['feature_id']}] {m['domain']} : {m['package']}")
        if m["status"] == "PENDING_CRAWL" and m.get("suggested_query"):
            print(f"      -> Crawl query: {m['suggested_query']}")

    print("\n  Planner thinking:")
    print(f"    {planner_out.get('thinking', 'N/A')[:200]}")
    
    # ê²€ì¦?    if loop_count > 1:
        print("\n[SUCCESS] Self-correction loop triggered!")
    else:
        print(f"\n[INFO] Loop count={loop_count}. No additional loop triggered.")
        pending = [m for m in mapping if m["status"] == "PENDING_CRAWL"]
        if pending:
            print(f"  PENDING items: {[m['package'] for m in pending]}")
            print("  -> Loop was expected but did not trigger. Check router logic.")

if __name__ == "__main__":
    test_pm_self_correction_loop()
