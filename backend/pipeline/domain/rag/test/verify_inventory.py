import os
import sys

# Path setup
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_root = os.path.abspath(os.path.join(current_dir, "..", "..", "..", ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from pipeline.domain.rag.nodes.project_db import get_session_inventory

def verify_inventory():
    session_id = "77fe9dc2c7816fa6" # NAVIGATOR stable session id
    inventory = get_session_inventory(session_id)
    
    target = "backend/pipeline/domain/pm/nodes/requirement_analyzer.py"
    if target in inventory:
        print(f"\n[Focus Check] {target}:")
        print(f"  Functions found: {inventory[target]}")
    else:
        print(f"\n[Focus Check] {target} NOT FOUND in inventory!")

if __name__ == "__main__":
    verify_inventory()
