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

def test_project_extension():
    """통합 테스트 2: 기존 프로젝트 기능 확장 (Image 28)"""
    scenario_name = "IT-02: Project Extension (Google OAuth)"
    
    existing_context = {
        "status": "Pass",
        "detected_frameworks": ["FastAPI"],
        "existing_entities": ["User"],
        "existing_apis": ["POST /api/v1/auth/login"]
    }
    
    requirements = [
        {"id": "REQ-201", "desc": "구글 소셜 로그인 추가 연동"}
    ]
    
    state = {
        "input_idea": "기존 이메일 로그인 시스템에 구글 로그인을 추가하고 싶습니다.",
        "system_scan": existing_context,
        "requirements_rtm": requirements,
        "api_key": "[.env]",
        "model": "gemini-2.5-flash",
        "run_id": "it_02_ext"
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
    test_project_extension()
