import sys
import os

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pipeline.domain.rag.nodes.project_db import _get_collection, query_project_code

def run_diagnostics():
    try:
        col = _get_collection()
        count = col.count()
        print(f"Total chunks in DB: {count}")
        
        # Get a few samples
        res = col.get(limit=5, include=["metadatas"])
        if not res["ids"]:
            print("DB is empty.")
            return
            
        print("\nSample metadata:")
        for m in res["metadatas"]:
            print(f"- session_id: {m.get('session_id')}, file_path: {m.get('file_path')}")
            
        session_id = res["metadatas"][0].get('session_id')
        print(f"\nTesting query with session_id={session_id}")
        
        # Test query
        results = query_project_code("FastAPI APIRouter", session_id=session_id, n_results=3)
        print(f"\nQuery results count: {len(results)}")
        for r in results:
            print(f"Match: {r['file_path']} (score: {r['similarity']})")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_diagnostics()
