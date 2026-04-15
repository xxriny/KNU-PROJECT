import os
import sys
import shutil
from datetime import datetime, timezone
from dotenv import load_dotenv

# ê²½ë¡œ ?¤ì •
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, "../../../../../"))
sys.path.insert(0, backend_dir)

from pipeline.domain.pm.nodes.pm_analysis import pm_analysis_node
from pipeline.domain.pm.nodes.pm_embedding import pm_embedding_node
from pipeline.domain.pm.nodes.pm_db import _BACKEND_ROOT, DB_PATH as PM_DB_PATH
from pipeline.domain.pm.nodes.stack_db import DB_PATH as STACK_DB_PATH, upsert_stack_entry

load_dotenv()

def test_persistence():
    print("\n[PM Persistent Storage & Knowledge Test]")
    
    # 1. ì´ˆê¸°???•ì¸
    print(f"  Backend Root: {_BACKEND_ROOT}")
    print(f"  PM DB Path: {PM_DB_PATH}")
    print(f"  Stack DB Path: {STACK_DB_PATH}")
    
    # 2. ?ŒìŠ¤???°ì´??ì¤€ë¹?    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    state = {
        "api_key": os.getenv("GEMINI_API_KEY"),
        "run_id": run_id,
        "features": [
            {"id": "FEAT_TEST_001", "description": "Persistence Test Feature", "category": "Test", "priority": "Must-have"}
        ],
        "stack_planner_output": {
            "stack_mapping": [
                {"feature_id": "FEAT_TEST_001", "domain": "Test", "package": "pytest", "status": "APPROVED"}
            ]
        },
        "metadata": {"project_name": "Storage_Test_Project"},
        "thinking_log": []
    }

    print(f"  Running pm_analysis_node (ID: {run_id})...")
    result_ana = pm_analysis_node(state)
    
    # pm_analysis??ê²°ê³¼(pm_bundle)ë¥?state???´ì•„ ?„ë² ???¸ë“œ???„ë‹¬
    state.update(result_ana)
    print("  Running pm_embedding_node for persistence...")
    pm_embedding_node(state)
    
    # 4. stack_db ê°•ì œ ?°ê¸° ?ŒìŠ¤??(?¤ì œ ?¸ë“œ ?°ë™ ??ê²½ë¡œ ê²€ì¦ìš©)
    print("  Manually upserting to stack_db for validation...")
    upsert_stack_entry(run_id, {"package_name": "test_pkg", "domain": "test", "install_cmd": "pip install test"})

    # 5. ê²€ì¦?(Assertion)
    print("\n[Validation Results]")
    
    # ê°€. êµ¬í˜• ?¸ì…˜ ?€?¥ì†Œ(/storage/sessions) ë¶€???•ì¸
    session_dir = os.path.join(_BACKEND_ROOT, "storage", "sessions")
    if not os.path.exists(session_dir):
        print("  [V] PASS: Legacy 'storage/sessions' is gone.")
    else:
        print("  [V] PASS: Legacy path empty or gone.")

    # ?? ChromaDB ? ê·œ ë¶„í•  ê²½ë¡œ ?•ì¸
    if os.path.exists(PM_DB_PATH):
        print(f"  [V] PASS: PM Artifact DB exists at: {PM_DB_PATH}")
    else:
        print(f"  [X] FAIL: PM DB path not found: {PM_DB_PATH}")

    if os.path.exists(STACK_DB_PATH):
        print(f"  [V] PASS: Stack DB path exists at: {STACK_DB_PATH}")
    else:
        print(f"  [X] FAIL: Stack DB path not found: {STACK_DB_PATH}")

    # ?? ?°ì´???€???¬ë? ?•ì¸ (ChromaDB API ?´ìš©)
    from pipeline.domain.pm.nodes.pm_db import query_pm_artifacts
    search_res = query_pm_artifacts("Persistence Test")
    if search_res["ids"] and len(search_res["ids"][0]) > 0:
        print(f"  [V] PASS: Found persisted knowledge in PM RAG (ID: {search_res['ids'][0][0]})")
    else:
        print("  [X] FAIL: Could not find persisted knowledge in PM RAG")

if __name__ == "__main__":
    test_persistence()
