import json
import os
import sys
from unittest.mock import MagicMock, patch

# ?꾨줈?앺듃 猷⑦듃 諛?backend 寃쎈줈 ?먮룞 異붽? (?대뵒?쒕뱺 ?ㅽ뻾 媛?ν븯?꾨줉)
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.abspath(os.path.join(current_dir, "../../../../../"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from pipeline.domain.sa.nodes.merge_project import sa_merge_project_node
from pipeline.domain.sa.schemas import MergeProjectOutput
from sa_unit_judge import judge_node
from dotenv import load_dotenv

load_dotenv()

def run_experiment(use_judge=True):
    # 1. ?쒕굹由ъ삤 ?ㅼ젙 (湲곗〈 濡쒓렇?몄뿉 OAuth 異붽?)
    state = {
        "input_idea": "湲곗〈 ?대찓??濡쒓렇?몄뿉 OAuth 異붽?",
        "system_scan": {
            "status": "Pass", 
            "detected_frameworks": ["FastAPI", "SQLAlchemy"]
        },
        "requirements_rtm": [{"id": "REQ-002", "desc": "Google OAuth ?곕룞"}],
        "api_key": "[.env]", 
        "model": "gemini-2.5-flash"
    }

    # 2. ?몃뱶 ?ㅽ뻾 (?ㅼ젣 紐⑤뜽 ?몄텧)
    result = sa_merge_project_node(state)
        
    # 3. 寃곌낵 異쒕젰
    print("\n" + "="*60)
    print(" [SA EXPERIMENT] sa_merge_project (Real LLM Call)")
    print("="*60)
    print(f"???먯젙 紐⑤뱶: {result['action_type']}")
    print(f"??蹂묓빀 ?꾨왂: {result['merged_project']['merge_strategy']}")
    print("-" * 60)
    print(json.dumps(result["sa_merge_project_output"], indent=2, ensure_ascii=False))
    print("="*60 + "\n")

    # 4. Judge ?됯? (Gemini 3.1 Pro)
    if use_judge:
        # merge_project 寃곌낵臾?援ъ“??留욎떠 state 援ъ꽦
        judge_node("sa_merge_project", state, result["sa_merge_project_output"])

if __name__ == "__main__":
    run_experiment()
