import chromadb
import os
import json
import ast

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BACKEND_ROOT, "storage", "pm_sa_vector_db")

def inspect_artifact_detail(session_id, artifact_type):
    client = chromadb.PersistentClient(path=DB_PATH)
    coll = client.get_collection("pm_artifact_knowledge")
    
    res = coll.get(where={"$and": [{"session_id": session_id}, {"artifact_type": artifact_type}]})
    
    if not res['ids']:
        print(f"No artifact found for {session_id} / {artifact_type}")
        return

    doc_str = res['documents'][0]
    print(f"--- Raw Document Content (First 1000 chars) ---")
    print(doc_str[:1000])
    print("-" * 50)
    
    # 파싱 시도
    try:
        data = json.loads(doc_str)
        print("Successfully parsed as JSON.")
    except:
        try:
            data = ast.literal_eval(doc_str)
            print("Successfully parsed as Python Literal (ast).")
        except:
            print("Failed to parse document.")
            return

    # API 스키마 집중 조사
    apis = []
    if isinstance(data, dict):
        apis = data.get('apis', data.get('data', {}).get('apis', []))
    
    print(f"\nFound {len(apis)} APIs in artifact.")
    for idx, api in enumerate(apis[:3]): # 상위 3개만 확인
        print(f"[{idx}] Endpoint: {api.get('endpoint')}")
        print(f"    Request Schema: {api.get('request_schema')}")
        print(f"    Response Schema: {api.get('response_schema')}")

if __name__ == "__main__":
    inspect_artifact_detail("20260422_164029", "SA_ARCH_BUNDLE")
