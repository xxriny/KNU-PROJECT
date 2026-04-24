import sys
import os

# Add backend to path
sys.path.append(r"c:\Users\Samsung\Desktop\LLM\NAVIGATOR\backend")

try:
    from pipeline.domain.pm.nodes.pm_db import query_pm_artifacts
    from pipeline.domain.pm.nodes.stack_db import search_tech_stacks
    from pipeline.domain.pm.nodes.memo_db import query_memos
    
    print("Imports successful.")
    
    # Try a dummy query
    pm_sa = query_pm_artifacts("test", n_results=1)
    print("PM/SA query successful.")
    
    stack = search_tech_stacks("test", top_k=1)
    print("Stack query successful.")
    
    memo = query_memos("test", n_results=1)
    print("Memo query successful.")
    
except Exception as e:
    print(f"Error: {e}")
