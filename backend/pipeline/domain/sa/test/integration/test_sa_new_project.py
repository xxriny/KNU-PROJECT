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
from sa_integration_judge import judge_integration

load_dotenv()

def test_new_project_design():
    """통합 테스트 1: 신규 프로젝트 설계 생성 (Image 27)"""
    scenario_name = "IT-01: New Project (Email Login)"
    requirements = [
        {"id": "REQ-101", "desc": "이메일/비밀번호 기반 로그인 구현 (FastAPI, React)"},
        {"id": "REQ-102", "desc": "사용자 정보 저장용 MariaDB 스키마 설계"}
    ]
    
    state = {
        "input_idea": "FastAPI와 React를 사용한 이메일 로그인 기능 구현",
        "system_scan": {}, # Empty (New)
        "requirements_rtm": requirements,
        "api_key": "[.env]",
        "model": "gemini-2.5-flash",
        "run_id": "it_01_new"
    }

    # Pipeline
    res_m = sa_merge_project_node(state)
    state.update(res_m)
    res_s = component_scheduler_node(state)
    state.update(res_s)
    res_d = api_data_modeler_node(state)
    state.update(res_d)
    res_a = sa_analysis_node(state)
    
    judge_integration(scenario_name, requirements, res_a["sa_analysis_output"])

if __name__ == "__main__":
    test_new_project_design()
