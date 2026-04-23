import os
import sys
import json
import chromadb
from typing import List, Dict, Any, Optional

# 프로젝트 루트(backend) 경로 추가
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
sys.path.insert(0, ROOT_DIR)

from pipeline.domain.pm.nodes.pm_db import DB_PATH, _get_collection

def inspect_rag(session_id: Optional[str] = None):
    """RAG 저장소 내용을 세션별로 조회"""
    print("\n" + "="*80)
    print(f" [RAG KNOWLEDGE INSPECTOR] ".center(80, "="))
    print("="*80)
    print(f"DB Path: {DB_PATH}")

    try:
        collection = _get_collection()
        
        # 1. 모든 데이터 가져오기 (메타데이터 기준 필터링을 위해)
        # ChromaDB .get()은 where 필터를 지원함
        if session_id:
            print(f"Searching for Session ID: {session_id}...")
            results = collection.get(
                where={"session_id": session_id},
                include=["metadatas", "documents"]
            )
        else:
            print("No Session ID provided. Listing all unique sessions in RAG...")
            results = collection.get(include=["metadatas"])
            
        if not results or not results["ids"]:
            print("\n[!] No data found in RAG.")
            return

        # 2. 결과 가공 및 출력
        if session_id:
            # 특정 세션 상세 출력
            print(f"\n>>> Found {len(results['ids'])} artifacts for session '{session_id}':")
            for i in range(len(results["ids"])):
                meta = results["metadatas"][i]
                doc = results["documents"][i]
                
                print(f"\n[{i+1}] Artifact ID: {results['ids'][i]}")
                print(f"    - Phase: {meta.get('phase')}")
                print(f"    - Type: {meta.get('artifact_type')}")
                print(f"    - Version: {meta.get('version')}")
                
                # 데이터 상세 출력
                try:
                    data = json.loads(doc)
                    if isinstance(data, dict):
                        inner_data = data.get("data", {})
                        
                        # 1. PM RTM 상세
                        if "rtm" in inner_data:
                            print(f"    - RTM Items ({len(inner_data['rtm'])}):")
                            for item in inner_data["rtm"]:
                                print(f"      * [{item.get('feature_id')}] {item.get('description')} ({item.get('priority')})")
                        
                        # 2. SA Architecture 상세
                        if "apis" in inner_data:
                            print(f"    - API Endpoints ({len(inner_data['apis'])}):")
                            for api in inner_data["apis"]:
                                print(f"      * {api.get('ep')}")
                        
                        if "tables" in inner_data:
                            print(f"    - DB Tables ({len(inner_data['tables'])}):")
                            for table in inner_data["tables"]:
                                cols = ", ".join(table.get("cl", [])) if isinstance(table.get("cl"), list) else table.get("cols", "N/A")
                                print(f"      * {table.get('nm') or table.get('name')}: {cols}")
                        
                        # 3. 그 외 데이터가 있는 경우 (예: 기술 스택)
                        if "tech_stacks" in inner_data:
                            stacks = ", ".join([s.get("pkg") for s in inner_data["tech_stacks"]])
                            print(f"    - Tech Stacks: {stacks}")

                    else:
                        print(f"    - Raw Content: {doc[:500]}...")
                except Exception as e:
                    print(f"    - [!] Content display error: {e}")
        else:
            # 모든 세션 목록 요약
            unique_sessions = {}
            for meta in results["metadatas"]:
                sid = meta.get("session_id")
                phase = meta.get("phase")
                if sid not in unique_sessions:
                    unique_sessions[sid] = {"PM": 0, "SA": 0, "Total": 0}
                unique_sessions[sid][phase] = unique_sessions[sid].get(phase, 0) + 1
                unique_sessions[sid]["Total"] += 1
            
            print(f"\n>>> Unique Sessions in RAG ({len(unique_sessions)}):")
            print(f"{'Session ID':<30} | {'PM':<5} | {'SA':<5} | {'Total':<5}")
            print("-" * 60)
            for sid, counts in unique_sessions.items():
                print(f"{sid:<30} | {counts['PM']:<5} | {counts['SA']:<5} | {counts['Total']:<5}")
            
            print("\n[TIP] Run with a Session ID to see detailed contents:")
            print(f"python {os.path.basename(__file__)} <session_id>")

    except Exception as e:
        print(f"\n[ERROR] Failed to inspect RAG: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    target_sid = sys.argv[1] if len(sys.argv) > 1 else None
    inspect_rag(target_sid)
