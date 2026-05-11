
import os
import sys
import json

# Add backend to path
sys.path.append(os.path.join(os.getcwd()))

from pipeline.domain.sa.nodes.sa_unified_modeler import _build_user_message, SAUnifiedModelerOutput, RECOVERY_PROMPT, OUTPUT_GUIDE
from pipeline.core.utils import call_structured
from pipeline.domain.rag.nodes.project_db import get_session_inventory, get_file_chunks
from pipeline.core.state import PipelineState
from version import DEFAULT_MODEL

def test_fast_recovery():
    session_id = "77fe9dc2c7816fa6" 
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    
    if not api_key:
        print("Error: API_KEY not found.")
        return

    print(f"--- Fast Integration Test (Direct File Target) ---")

    # 1. Get Inventory
    inventory = get_session_inventory(session_id)
    
    # 2. Directly Fetch Target DB Snippets (Bypassing Semantic Search/Embeddings)
    target_files = [
        "backend/pipeline/domain/pm/nodes/memo_db.py",
        "backend/pipeline/domain/pm/nodes/stack_db.py",
        "backend/pipeline/domain/pm/nodes/pm_db.py",
        "backend/pipeline/domain/rag/nodes/project_db.py"
    ]
    
    all_chunks = []
    for f in target_files:
        chunks = get_file_chunks(f, session_id)
        all_chunks.extend(chunks)
        print(f"  - Loaded {len(chunks)} chunks from {f}")

    # 3. Build Evidence
    lines = ["<existing_code_forensic_evidence>"]
    for c in all_chunks[:100]:
        lines.append(f"File: {c.get('file_path')}\nContent: {c.get('content_text', '')[:1200]}")
    lines.append("</existing_code_forensic_evidence>")
    snippets_text = "\n".join(lines)

    # 4. Mock Inputs
    components = [] # Simplified
    rtm = [] # Simplified
    action_type = "REVERSE_ENGINEER"

    user_content = _build_user_message(components, rtm, inventory, action_type, snippets_text)
    system_prompt = RECOVERY_PROMPT + OUTPUT_GUIDE

    # 5. Call LLM (Only one call, should be fast)
    print("Calling LLM for final verification...")
    res = call_structured(
        api_key=api_key, 
        model=DEFAULT_MODEL,
        schema=SAUnifiedModelerOutput, 
        system_prompt=system_prompt,
        user_msg=user_content,
        temperature=0.0
    )

    output = res.parsed
    tables = output.tables
    print("\n[VERIFICATION RESULT] Found Tables:")
    found_names = [t.table_name for t in tables]
    for name in found_names:
        print(f"  - {name}")

    target_dbs = ["user_memos", "tech_stack_knowledge"]
    success = True
    for target in target_dbs:
        if any(target in name for name in found_names):
            print(f"  [OK] {target} detected!")
        else:
            print(f"  [FAIL] {target} MISSING!")
            success = False

    if success:
        print("\n=== FINAL VERIFICATION: SUCCESS ===")
    else:
        print("\n=== FINAL VERIFICATION: FAILED ===")

if __name__ == "__main__":
    test_fast_recovery()
