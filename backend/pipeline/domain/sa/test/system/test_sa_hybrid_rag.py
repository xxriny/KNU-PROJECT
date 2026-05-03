import json
import os
import sys
from dotenv import load_dotenv

# 프로젝트 루트 및 backend 경로 자동 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.abspath(os.path.join(current_dir, "../../../../../"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from pipeline.domain.sa.nodes.merge_project import sa_merge_project_node
from pipeline.domain.sa.nodes.component_scheduler import component_scheduler_node
from pipeline.domain.sa.nodes.api_data_modeler import api_data_modeler_node
from pipeline.domain.sa.nodes.sa_analysis import sa_analysis_node
from sa_system_judge import judge_system

load_dotenv()

def test_hybrid_rag_integration():
    """시스템 테스트: 하이브리드 설계 통합 및 RAG 지식 확장 (Image 30)"""
    scenario_name = "ST-01: Hybrid RAG Integration (Post Update/Delete)"
    
    # PROJECT_RAG에 이미 게시판 조회 기능이 있는 상태
    existing_rag = {
        "status": "Pass",
        "detected_frameworks": ["FastAPI", "MariaDB"],
        "existing_entities": ["Post"],
        "existing_apis": ["GET /api/v1/posts (목록)", "GET /api/v1/posts/{id} (상세)"]
    }
    
    # 신규 요구사항: 수정 및 삭제 추가
    requirements = [
        {"id": "REQ-401", "desc": "게시글 수정 API 추가"},
        {"id": "REQ-402", "desc": "게시글 삭제 API 추가"}
    ]
    
    state = {
        "input_idea": "게시글 수정 및 삭제 기능을 추가해주세요.",
        "system_scan": existing_rag,
        "requirements_rtm": requirements,
        "api_key": "[.env]",
        "model": "gemini-2.5-flash",
        "run_id": "st_01_hybrid"
    }

    print(f"\n>>> Running System Integration Test: {scenario_name}")

    # Pipeline
    res_m = sa_merge_project_node(state)
    state.update(res_m)
    res_s = component_scheduler_node(state)
    state.update(res_s)
    res_d = api_data_modeler_node(state)
    state.update(res_d)
    res_a = sa_analysis_node(state)
    
    final_output = res_a["sa_analysis_output"]

    judge_system(scenario_name, requirements, existing_rag, final_output)

if __name__ == "__main__":
    test_hybrid_rag_integration()
