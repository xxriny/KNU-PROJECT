import json
import os
import sys
from unittest.mock import MagicMock, patch

# 프로젝트 루트 및 backend 경로 자동 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.abspath(os.path.join(current_dir, "../../../../../"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from pipeline.domain.sa.nodes.sa_analysis import sa_analysis_node
from pipeline.domain.sa.schemas import SAAnalysisOutput
from sa_unit_judge import judge_node
from dotenv import load_dotenv

load_dotenv()

def run_experiment(use_judge=True):
    # 1. 시나리오 설정 (추적성 검증: '비밀번호 찾기' 요구사항 누락 상황)
    state = {
        "component_scheduler_output": {
            "components": [
                {"component_name": "LoginView", "role": "로그인 UI"},
                {"component_name": "AuthService", "role": "인증 서비스"}
            ]
        },
        "api_data_modeler_output": {
            "apis": [{"endpoint": "POST /api/v1/auth/login", "description": "로그인 API"}],
            "tables": [{"table_name": "users", "columns": []}]
        },
        "merged_project": {
            "plan": {
                "requirements_rtm": [
                    {"id": "REQ-001", "desc": "사용자 로그인"},
                    {"id": "REQ-002", "desc": "비밀번호 찾기 (이메일 발송)"}
                ]
            }
        },
        "run_id": "eval_sa_analysis",
        "api_key": "[.env]", 
        "model": "gemini-2.5-flash"
    }

    # 2. 노드 실행
    result = sa_analysis_node(state)
    output = result["sa_analysis_output"]
        
    # 3. 결과 출력
    print("\n" + "="*60)
    print(" [SA EXPERIMENT] sa_analysis (Real LLM Call)")
    print("="*60)
    print(f"▶ 검증 상태: {output.get('status')}")
    print(f"▶ 발견된 Gaps: {output.get('gaps')}")
    print("-" * 60)
    print(json.dumps(output, indent=2, ensure_ascii=False))
    print("="*60 + "\n")

    # 4. Judge 평가
    if use_judge:
        judge_node("sa_analysis", state, output)

if __name__ == "__main__":
    run_experiment()
