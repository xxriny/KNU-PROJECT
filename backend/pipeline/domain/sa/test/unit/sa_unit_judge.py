import os
import json
from typing import Dict, List, Any
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from pipeline.core.utils import call_structured, _get_effective_key

# .env 로드
load_dotenv()

# Judge LLM 출력 스키마
class SAJudgeOutput(BaseModel):
    score: int = Field(..., description="1-5점 사이의 정수 점수")
    rationale: str = Field(..., description="채점 근거 및 논리적 추론")
    suggestions: List[str] = Field(..., description="개선 제안 사항")
    consistency_check: str = Field(..., description="설계 일관성 검토 결과")

JUDGE_SYSTEM_PROMPT = """
당신은 베테랑 소프트웨어 아키텍트이자 품질 보증(QA) 전문가입니다.
입력으로 주어지는 '요구사항'과 '노드 실행 결과물'을 바탕으로 해당 노드의 수행 능력을 평가하십시오.

[평가 대상 구분]
1. 설계 노드 (Merge, Scheduler, Modeler):
   - 결과물이 요구사항을 얼마나 반영하고 일관되게 설계되었는지를 평가합니다.
2. 검증 노드 (Analysis):
   - 결과물이 설계상의 결함이나 요구사항 누락을 얼마나 **정확하게 찾아냈는지**를 평가합니다.
   - 설계가 완벽하지 않더라도, 노드가 그 결함을 'FAIL'로 판정하고 정확한 'gaps'를 찾아냈다면 만점을 주어야 합니다.

[평가 기준]
1. 정확성: 요구사항과 설계물 간의 차이를 정확히 식별했는가? (검증 노드 전용)
2. 추적성: 요구사항이 누락 없이 설계(또는 검증)에 반영되었는가?
3. 구조적 건전성: 제안된 해결책이나 설계 구조가 아키텍처 표준을 따르는가?
"""

def judge_node(node_name: str, state: Dict[str, Any], result: Dict[str, Any]):
    """
    단일 노드 실행 결과를 채점합니다.
    """
    print(f"\n" + "-"*60)
    print(f" [JUDGE] Evaluating: {node_name} ".center(60, "-"))
    print("-"*60)

    api_key = _get_effective_key(state.get("api_key", ""))
    judge_model = "gemini-3.1-pro-preview" 

    # 채점 대상 컨텍스트 구성
    user_msg = f"""
### [Node Name]
{node_name}

### [Input Context / Requirements]
{json.dumps(state.get("merged_project", {}), indent=2, ensure_ascii=False)}

### [Node Output]
{json.dumps(result, indent=2, ensure_ascii=False)}
"""

    try:
        judge_res = call_structured(
            api_key=api_key,
            model=judge_model,
            schema=SAJudgeOutput,
            system_prompt=JUDGE_SYSTEM_PROMPT,
            user_msg=user_msg,
            temperature=0.0
        )
        
        eval_data = judge_res.parsed
        
        print(f"▶ Score: {eval_data.score} / 5")
        print(f"▶ Rationale: {eval_data.rationale}")
        print(f"▶ Consistency: {eval_data.consistency_check}")
        if eval_data.suggestions:
            print(f"▶ Suggestions:")
            for sug in eval_data.suggestions:
                print(f"  - {sug}")
        print("-"*60 + "\n")
        
        return eval_data
    except Exception as e:
        print(f" [X] Judge failed: {e}")
        return None
