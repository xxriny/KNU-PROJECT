import json
import os
import sys
from unittest.mock import MagicMock, patch

# 프로젝트 루트 및 backend 경로 자동 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.abspath(os.path.join(current_dir, "../../../../../"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from pipeline.domain.sa.nodes.component_scheduler import component_scheduler_node
from pipeline.domain.sa.schemas import ComponentSchedulerOutput, ComponentDefinition
from sa_unit_judge import judge_node
from dotenv import load_dotenv

load_dotenv()

def run_experiment(use_judge=True):
    # 1. 시나리오 설정 (게시글 작성 및 이미지 업로드)
    state = {
        "merged_project": {
            "merge_strategy": "게시판 기능 확장: 게시글 작성 및 이미지 업로드 기능 추가",
            "base_context": {"tech_stack": "React, FastAPI"},
            "plan": {"requirements_rtm": [{"id": "REQ-101", "desc": "게시글 및 이미지 업로드"}]}
        },
        "api_key": "[.env]", 
        "model": "gemini-2.5-flash"
    }

    # 2. 노드 실행
    result = component_scheduler_node(state)
    output = result["component_scheduler_output"]
        
    # 3. 결과 출력
    print("\n" + "="*60)
    print(" [SA EXPERIMENT] component_scheduler (Real LLM Call)")
    print("="*60)
    print(f"▶ 설계된 컴포넌트 개수: {len(output.get('components', []))}")
    print("-" * 60)
    print(json.dumps(output, indent=2, ensure_ascii=False))
    print("="*60 + "\n")

    # 4. Judge 평가
    if use_judge:
        judge_node("component_scheduler", state, output)

if __name__ == "__main__":
    run_experiment()
