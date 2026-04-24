import chromadb
import os
import json

# DB 경로 설정
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BACKEND_ROOT, "storage", "pm_sa_vector_db")

def check_sa_rag():
    print(f"Checking SA data in: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("DB path does not exist.")
        return

    client = chromadb.PersistentClient(path=DB_PATH)
    
    try:
        coll = client.get_collection("pm_artifact_knowledge")
        print(f"\nScanning 'pm_artifact_knowledge' (Total: {coll.count()} items)...")
        
        # phase="SA" 인 데이터 필터링 조회
        results = coll.get(where={"phase": "SA"})
        
        if not results['ids']:
            print("\n[ALERT] No SA phase artifacts found in RAG.")
            return

        print(f"\n[FOUND] {len(results['ids'])} SA artifacts found.")
        for i in range(len(results['ids'])):
            print(f"- ID: {results['ids'][i]}")
            print(f"  Metadata: {results['metadatas'][i]}")
            # 데이터 일부 출력
            doc_sample = str(results['documents'][i])[:300]
            print(f"  Content Preview: {doc_sample}...\n")
            
    except Exception as e:
        print(f"Error inspecting SA collection: {e}")

if __name__ == "__main__":
    check_sa_rag()
