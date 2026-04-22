import chromadb
import os
import json

# DB 경로 설정
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BACKEND_ROOT, "storage", "pm_sa_vector_db")

def inspect_usage():
    print(f"Checking for usage data in: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("DB path does not exist.")
        return

    client = chromadb.PersistentClient(path=DB_PATH)
    
    # 1. 컬렉션 목록 확인
    collections = client.list_collections()
    print(f"Collections found: {[c.name for c in collections]}")
    
    # 2. pm_artifact_knowledge 조사
    try:
        coll = client.get_collection("pm_artifact_knowledge")
        print(f"\nScanning 'pm_artifact_knowledge' (Total: {coll.count()} items)...")
        
        # 최근 5건의 메타데이터 확인 (Usage 관련 데이터가 있는지)
        results = coll.get(limit=20)
        usage_found = False
        
        for i in range(len(results['ids'])):
            meta = results['metadatas'][i]
            doc = results['documents'][i]
            
            # 메타데이터에 'usage' 키워드가 있거나 artifact_type이 USAGE 관련인지 확인
            if "usage" in str(meta).lower() or "cost" in str(meta).lower() or "usage" in str(doc).lower():
                print(f"\n[FOUND] Usage-like data in {results['ids'][i]}")
                print(f"Metadata: {meta}")
                # 데이터가 너무 길면 일부만 출력
                print(f"Content Preview: {str(doc)[:200]}...")
                usage_found = True
        
        if not usage_found:
            print("\nNo explicit usage logs found in vector DB artifacts.")
            
    except Exception as e:
        print(f"Error inspecting collection: {e}")

if __name__ == "__main__":
    inspect_usage()
