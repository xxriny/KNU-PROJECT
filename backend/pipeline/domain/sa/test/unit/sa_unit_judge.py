import os
import json
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from pipeline.core.utils import call_structured, _get_effective_key

# .env 로드
load_dotenv()

# Judge LLM 출력 스키마
class SAJudgeOutput(BaseModel):
    score: int = Field(..., description="1-5점 사이의 정수 점수 (4점 이상 PASS)")
    rationale: str = Field(..., description="채점 근거 및 논리적 추론")
    suggestions: List[str] = Field(..., description="개선 제안 사항")
    consistency_check: str = Field(..., description="설계 일관성 및 정합성 검토 결과")
    passed: bool = Field(..., description="성공 여부 (점수 4점 이상 혹은 치명적 결함 없음)")

JUDGE_SYSTEM_PROMPT = """
당신은 베테랑 소프트웨어 아키텍트이자 품질 보증(QA) 전문가입니다.
입력으로 주어지는 '요구사항'과 '노드 실행 결과물'을 바탕으로 해당 노드의 수행 능력을 매우 엄격하게 평가하십시오.

[평가 대상별 핵심 체크리스트]
1. sa_merge_project:
   - 모든 사용자 요구사항이 'plan'과 'requirements_rtm'에 누락 없이 통합되었는가?
   - 중복되거나 모순되는 요구사항이 해결되었는가?
2. component_scheduler:
   - 도메인별 컴포넌트 분리가 적절하며, 의존성 관계가 순환(Circular)하지 않는가?
   - 요구사항(RTM)의 기능들이 컴포넌트의 'role'에 모두 할당되었는가?
3. api_data_modeler:
   - [필수] Naming Dictionary 준수 (id는 uuid, user_id, snake_case 등)
   - [필수] 참조 무결성: API에서 사용하는 foreign key가 tables 목록에 존재하는가?
   - [필수] Zero-Null Policy: 모든 필드가 의미 있는 값으로 채워졌는가? (특히 request/response schema)
4. sa_analysis:
   - [핵심] 설계의 결함을 정확히 찾아냈는가? (설계가 나쁘더라도 분석 노드가 이를 'FAIL'로 짚어내면 만점)
   - 'gaps'가 구체적이고 수정 가능한 형태로 제안되었는가?

[채점 가이드라인]
- 5점 (Excellent): 완벽함. 모든 표준 준수 및 요구사항 충족.
- 4점 (Good): 사소한 개선점은 있으나 실무 적용 가능. (PASS)
- 3점 (Fair): 주요 기능은 동작하나 아키텍처적 결함이나 명칭 미준수 존재.
- 1-2점 (Poor/Fail): 핵심 요구사항 누락, 데이터 정합성 파괴, 또는 표준 위반.
"""

def judge_node(node_name: str, state: Dict[str, Any], result: Dict[str, Any]) -> Optional[SAJudgeOutput]:
    """
    단일 노드 실행 결과를 채점합니다.
    """
    print(f"\n" + "="*80)
    print(f" [JUDGE] Evaluating: {node_name} ".center(80, "="))
    print("="*80)

    api_key = _get_effective_key(state.get("api_key", ""))
    # 최신 고성능 모델 사용 (환경에 맞는 2.5 Flash 사용)
    judge_model = "gemini-2.5-flash" 

    # 채점 대상 컨텍스트 구성
    # state에서 필요한 부분만 추출하여 컨텍스트 비대화 방지
    input_context = {
        "requirements": state.get("merged_project", {}),
        "scheduler_output": state.get("component_scheduler_output", {}),
        "analysis_feedback": state.get("sa_analysis_output", {}).get("gaps", [])
    }

    user_msg = f"""
### [Node Name]
{node_name}

### [Input Context / Previous Steps]
{json.dumps(input_context, indent=2, ensure_ascii=False)}

### [Node Output to Evaluate]
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
        
        status_str = "[PASS]" if eval_data.passed else "[FAIL]"
        print(f"{status_str} Score: {eval_data.score} / 5")
        print(f"▶ Rationale: {eval_data.rationale}")
        print(f"▶ Consistency: {eval_data.consistency_check}")
        
        if eval_data.suggestions:
            print(f"▶ Suggestions:")
            for sug in eval_data.suggestions:
                print(f"  - {sug}")
        print("="*80 + "\n")
        
        return eval_data
    except Exception as e:
        print(f" [X] Judge failed: {e}")
        return None
