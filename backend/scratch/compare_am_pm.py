import chromadb
import os

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BACKEND_ROOT, "storage", "pm_sa_vector_db")

def compare_am_pm():
    client = chromadb.PersistentClient(path=DB_PATH)
    coll = client.get_collection("pm_artifact_knowledge")
    
    # 오전 세션 (최적화 전/일부 적용)
    am_session = "20260422_102148"
    # 오후 세션 (최적화 후)
    pm_session = "20260422_164605"
    
    am_results = coll.get(where={"$and": [{"session_id": am_session}, {"artifact_type": "PM_BUNDLE"}]})
    pm_results = coll.get(where={"$and": [{"session_id": pm_session}, {"artifact_type": "PM_BUNDLE"}]})
    
    print(f"Comparison: AM ({am_session}) vs PM ({pm_session})\n")
    
    if am_results['ids'] and pm_results['ids']:
        am_doc = am_results['documents'][0]
        pm_doc = pm_results['documents'][0]
        
        am_len = len(am_doc)
        pm_len = len(pm_doc)
        
        print(f"[AM] Result Document Length: {am_len} chars")
        print(f"[PM] Result Document Length: {pm_len} chars")
        print(f"Reduction in Output Context: {((am_len - pm_len) / am_len * 100):.1f}% (if applicable)")
        
        # 입력 컨텍스트(RTM 등)도 비교
        am_rtm = coll.get(where={"$and": [{"session_id": am_session}, {"artifact_type": "RTM_STACK_BUNDLE"}]})
        pm_rtm = coll.get(where={"$and": [{"session_id": pm_session}, {"artifact_type": "RTM_STACK_BUNDLE"}]})
        
        if am_rtm['ids'] and pm_rtm['ids']:
            am_rtm_len = len(am_rtm['documents'][0])
            pm_rtm_len = len(pm_rtm['documents'][0])
            print(f"\n[AM] RTM Context Length: {am_rtm_len} chars")
            print(f"[PM] RTM Context Length: {pm_rtm_len} chars")
            print(f"Input Context Compression: {((am_rtm_len - pm_rtm_len) / am_rtm_len * 100):.1f}%")
    else:
        print("Could not find both sessions for comparison.")

if __name__ == "__main__":
    compare_am_pm()
