import chromadb
import os

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BACKEND_ROOT, "storage", "pm_sa_vector_db")

def list_session_artifacts(session_id):
    client = chromadb.PersistentClient(path=DB_PATH)
    coll = client.get_collection("pm_artifact_knowledge")
    
    res = coll.get(where={"session_id": session_id})
    print(f"Artifacts for {session_id}:")
    for i in range(len(res['ids'])):
        meta = res['metadatas'][i]
        print(f"- Type: {meta.get('artifact_type')}, ID: {res['ids'][i]}, Length: {len(res['documents'][i])}")

if __name__ == "__main__":
    list_session_artifacts("20260422_102148")
    print("-" * 30)
    list_session_artifacts("20260422_164605")
