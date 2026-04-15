"""
RAG Knowledge Inspector (Refactored as Module)
ChromaDB(stack_vector_db, pm_sa_vector_db)에 저장된 실데이터를 조회합니다.
"""

import os
import sys
import json

# 경로 설정
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../.."))

from pipeline.domain.pm.nodes.pm_db import _get_collection as get_pm_collection, DB_PATH as PM_DB_PATH
from pipeline.domain.pm.nodes.stack_db import _get_collection as get_stack_collection, DB_PATH as STACK_DB_PATH

def inspect_pm_sa_rag(limit=3, filter_metadata=None):
    """PM & SA RAG 조회 함수"""
    try:
        pm_coll = get_pm_collection()
        if filter_metadata:
            results = pm_coll.get(where=filter_metadata, include=["documents", "metadatas"])
        else:
            results = pm_coll.get(limit=limit, include=["documents", "metadatas"])
        return results
    except Exception as e:
        print(f"Error inspecting PM RAG: {e}")
        return {"ids": [], "metadatas": [], "documents": []}

def inspect_stack_knowledge(limit=3, filter_metadata=None):
    """Stack RAG 조회 함수"""
    try:
        stack_coll = get_stack_collection()
        if filter_metadata:
            results = stack_coll.get(where=filter_metadata, include=["documents", "metadatas"])
        else:
            results = stack_coll.get(limit=limit, include=["documents", "metadatas"])
        return results
    except Exception as e:
        print(f"Error inspecting Stack RAG: {e}")
        return {"ids": [], "metadatas": [], "documents": []}

def inspect_db():
    print("\n" + " RAG STORAGE INSPECTION ".center(60, "="))
    
    # 1. PM & SA RAG
    print(f"\n[1] PM & SA 지식 저장소 (Table 04)")
    print(f"    Path: {PM_DB_PATH}")
    
    results = inspect_pm_sa_rag()
    count = len(results["ids"])
    print(f"    Sample Documents: {count}")
    
    for i in range(count):
        print(f"\n    - ID: {results['ids'][i]}")
        print(f"      Type: {results['metadatas'][i].get('artifact_type')}")
        print(f"      Preview: {results['documents'][i][:150]}...")

    # 2. STACK RAG
    print(f"\n[2] 기술 스택 지식 저장소 (Table 05)")
    print(f"    Path: {STACK_DB_PATH}")
    
    results = inspect_stack_knowledge()
    count = len(results["ids"])
    print(f"    Sample Documents: {count}")
    
    for i in range(count):
        print(f"\n    - ID: {results['ids'][i]}")
        print(f"      Package: {results['metadatas'][i].get('package_name')}")
        print(f"      Preview: {results['documents'][i][:150]}...")

    print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    inspect_db()
