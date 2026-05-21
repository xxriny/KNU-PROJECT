
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd()))

from pipeline.domain.rag.nodes.project_db import query_project_code, get_session_inventory
from pipeline.core.state import PipelineState

def debug_sa_rag(session_id: str):
    print(f"=== Debugging SA RAG for Session: {session_id} ===")
    
    # 1. Check Inventory
    try:
        inventory = get_session_inventory(session_id)
        print(f"\n[1] Inventory Files ({len(inventory)} total):")
        db_files = [f for f in inventory.keys() if "_db.py" in f]
        for f in db_files:
            print(f"  - FOUND DB FILE: {f}")
            print(f"    Functions: {[it['name'] for it in inventory[f]]}")
        if not db_files:
            print("  - NO DB FILES FOUND IN INVENTORY!")
    except Exception as e:
        print(f"  - Error getting inventory: {e}")

    # 2. Replicate sa_unified_modeler Queries
    queries = [
        "SQLAlchemy Base declarative_base Column ForeignKey",
        "ChromaDB Collection get_or_create_collection PersistentClient",
        "user_memos tech_stack_knowledge pm_artifact_knowledge",
        "memo_db.py stack_db.py pm_db.py project_db.py",
        "sqlite3.connect cursor.execute",
        "Table(Base) __tablename__ = ",
        "vector_db chat_db project_db history_db"
    ]
    
    print("\n[2] Replicating sa_unified_modeler Queries:")
    seen_files = set()
    all_chunks = []
    
    for q in queries:
        print(f"  Query: '{q}'")
        try:
            # Note: We don't have the user's API key here, but hopefully local search works or uses env
            res = query_project_code(q, session_id=session_id, n_results=20)
            print(f"    -> Found {len(res)} chunks")
            for c in res:
                path = c.get('file_path')
                seen_files.add(path)
                if "_db.py" in path:
                    print(f"       MATCH: {path} (sim: {c.get('similarity', 0):.2f})")
        except Exception as e:
            print(f"    -> Query failed: {e}")

    print(f"\n[3] All DB-related files reached by RAG:")
    for f in sorted(seen_files):
        if "_db.py" in f:
            print(f"  - {f}")
    
    # 3. Direct File Target Test
    print("\n[4] Direct Target Test (memo_db.py):")
    try:
        res = query_project_code("memo_db.py", session_id=session_id, n_results=5)
        for c in res:
            if "memo_db.py" in c.get('file_path', ''):
                print(f"  - Found memo_db.py content! Chunk length: {len(c.get('content_text',''))}")
                # print(f"  - Snippet: {c.get('content_text','')[:100]}...")
            else:
                 print(f"  - Found OTHER file: {c.get('file_path')}")
    except Exception as e:
        print(f"  - Direct target failed: {e}")

if __name__ == "__main__":
    # If no session_id provided, we might need to find the latest one from storage
    target_session = sys.argv[1] if len(sys.argv) > 1 else "default_session"
    debug_sa_rag(target_session)
