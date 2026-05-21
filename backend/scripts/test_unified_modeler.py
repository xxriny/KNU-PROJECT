
import os
import sys
import json

# Add backend to path
sys.path.append(os.path.join(os.getcwd()))

from pipeline.domain.sa.nodes.sa_unified_modeler import sa_unified_modeler_node
from pipeline.core.node_base import NodeContext
from pipeline.core.state import PipelineState
from pipeline.domain.rag.nodes.project_db import get_session_inventory
from version import DEFAULT_MODEL

def test_recovery():
    # 1. Setup Session ID (from previous discovery)
    session_id = "77fe9dc2c7816fa6" 
    api_key = os.environ.get("GOOGLE_API_KEY") # Ensure this is set in the environment
    
    if not api_key:
        print("Error: GOOGLE_API_KEY not found in environment.")
        return

    print(f"--- Testing SA Unified Modeler Recovery (Session: {session_id}) ---")

    # 2. Mock Pipeline State
    state = PipelineState({
        "session_id": session_id,
        "run_id": session_id,
        "action_type": "REVERSE_ENGINEER",
        "api_key": api_key,
        "model": "gemini-1.5-pro", # Use Pro for high accuracy
        "component_scheduler_output": {"components": []}, # Not strictly needed for DB extraction
        "features": [] 
    })

    # 4. Run Node
    print("Running sa_unified_modeler_node...")
    try:
        # 노드가 @pipeline_node 데코레이터로 감싸져 있으므로 state를 직접 전달해야 합니다.
        result = sa_unified_modeler_node(state)
        
        # 5. Verify Results
        output = result.get("sa_unified_modeler_output", {})
        tables = output.get("tb", [])
        
        print("\n[RESULT] Found Tables:")
        found_names = []
        for t in tables:
            name = t.get("nm")
            found_names.append(name)
            print(f"  - {name}: {t.get('cl')[:50]}...")
            
        target_dbs = ["user_memos", "tech_stack_knowledge"]
        all_found = True
        for target in target_dbs:
            if any(target in name for name in found_names):
                print(f"  [SUCCESS] {target} detected!")
            else:
                print(f"  [FAILURE] {target} MISSING!")
                all_found = False
        
        if all_found:
            print("\n=== FINAL TEST RESULT: PASSED ===")
        else:
            print("\n=== FINAL TEST RESULT: FAILED ===")

    except Exception as e:
        print(f"Error during node execution: {e}")

if __name__ == "__main__":
    test_recovery()
