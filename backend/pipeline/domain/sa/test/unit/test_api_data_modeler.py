import json
import os
import sys
from unittest.mock import MagicMock, patch

# ?꾨줈?앺듃 猷⑦듃 諛?backend 寃쎈줈 ?먮룞 異붽?
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.abspath(os.path.join(current_dir, "../../../../../"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from pipeline.domain.sa.nodes.api_data_modeler import api_data_modeler_node
from pipeline.domain.sa.schemas import ApiDataModelerOutput, ApiDefinition, TableDefinition
from sa_unit_judge import judge_node
from dotenv import load_dotenv

load_dotenv()

def run_experiment(use_judge=True):
    # 1. ?쒕굹由ъ삤 ?ㅼ젙 (寃뚯떆???뺤옣: 寃뚯떆湲 ?묒꽦 諛??대?吏 ?낅줈??
    # ?댁쟾 component_scheduler???깃났?곸씤 寃곌낵臾쇨낵 ?곌퀎???쒕굹由ъ삤 援ъ꽦
    state = {
        "component_scheduler_output": {
            "components": [
                {"domain": "Frontend", "component_name": "PostFormUI", "role": "寃뚯떆湲 ?꾩넚 ?붿껌 ?대떦", "dependencies": ["PostAPIController", "S3UploadService"]},
                {"domain": "Backend", "component_name": "PostAPIController", "role": "寃뚯떆湲 API ?붾뱶?ъ씤???쒓났", "dependencies": ["PostRepositoryService"]},
                {"domain": "Backend", "component_name": "S3UploadService", "role": "S3 ?대?吏 ?낅줈??泥섎━", "dependencies": []},
                {"domain": "Backend", "component_name": "PostRepositoryService", "role": "DB ?곸냽???대떦", "dependencies": []}
            ]
        },
        "merged_project": {
            "plan": {"requirements_rtm": [{"id": "REQ-101", "desc": "寃뚯떆湲 ?묒꽦 諛??대?吏 ?낅줈??(?대?吏??S3 ???"}]}
        },
        "api_key": "[.env]", 
        "model": "gemini-2.5-flash"
    }

    # 2. ?몃뱶 ?ㅽ뻾 (?ㅼ젣 紐⑤뜽 ?몄텧)
    result = api_data_modeler_node(state)
        
    # 3. 寃곌낵 異쒕젰
    print("\n" + "="*60)
    print(" [SA EXPERIMENT] api_data_modeler (Real LLM Call)")
    print("="*60)
    print(f"???ㅺ퀎??API 媛쒖닔: {len(result['api_data_modeler_output']['apis'])}")
    print(f"???ㅺ퀎???뚯씠釉?媛쒖닔: {len(result['api_data_modeler_output']['tables'])}")
    print("-" * 60)
    print(json.dumps(result["api_data_modeler_output"], indent=2, ensure_ascii=False))
    print("="*60 + "\n")

    # 4. Judge ?됯? (Gemini 3.1 Pro)
    if use_judge:
        judge_node("api_data_modeler", state, result["api_data_modeler_output"])

if __name__ == "__main__":
    run_experiment()
