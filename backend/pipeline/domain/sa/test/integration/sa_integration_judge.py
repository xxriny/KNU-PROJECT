import json
import os
from typing import Dict, Any
from pydantic import BaseModel, Field
from pipeline.core.utils import call_structured
from dotenv import load_dotenv

load_dotenv()

class SAIntegrationJudgeOutput(BaseModel):
    score: int = Field(..., description="1-5점 사이의 통합 설계 점수")
    rationale: str = Field(..., description="점수 부여 근거 (노드 간 정합성 중심)")
    interface_consistency: str = Field(..., description="API와 컴포넌트 간 인터페이스 일치 여부")
    requirement_coverage: str = Field(..., description="전체 요구사항 반영도")
    suggestions: str = Field(..., description="파이프라인 개선 제안")

JUDGE_SYSTEM_PROMPT = """
당신은 SA 파이프라인의 통합 품질을 평가하는 '수석 통합 아키텍트'이자 QA 전문가입니다.
개별 노드의 결과가 아닌, 여러 노드가 협력하여 생성한 '최종 SA 번들'의 통합 품질을 평가합니다.

[평가 대상 구분]
1. 설계 결과물 (Components, APIs, Tables):
   - 노드 간 데이터 흐름이 완벽하며, 인터페이스(필드명, 타입)가 일치하는지 평가합니다.
2. 검증 결과물 (Analysis Status & Gaps):
   - **중요**: 파이프라인이 설계상의 결함을 정확히 찾아냈는지를 평가합니다.
   - 만약 설계에 결함(누락 등)이 있더라도, `sa_analysis` 노드가 이를 정확히 'FAIL'로 판정하고 원인을 찾아냈다면 **그 검증 능력에 대해 만점**을 주어야 합니다.

[평가 기준]
1. 인터페이스 일치: API 스키마와 컴포넌트 로직 간의 필드명/데이터 타입 일치 여부.
2. 데이터 정합성: API가 참조하는 모든 엔티티가 DB 테이블로 정의되었는가?
3. 검증 정확성: 설계의 결함을 놓치지 않고 분석 결과(status, gaps)에 반영했는가?
"""

def judge_integration(scenario_name: str, requirements: list, sa_bundle: Dict[str, Any]):
    print(f"\n" + "-"*25 + f" [INTEGRATION JUDGE] {scenario_name} " + "-"*25)
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in .env")
        return

    user_msg = f"""
    [Scenario]
    {scenario_name}
    
    [Requirements]
    {json.dumps(requirements, indent=2, ensure_ascii=False)}
    
    [Final SA Bundle]
    {json.dumps(sa_bundle, indent=2, ensure_ascii=False)}
    """

    try:
        res = call_structured(
            api_key=api_key,
            model="gemini-3.1-pro-preview",
            schema=SAIntegrationJudgeOutput,
            system_prompt=JUDGE_SYSTEM_PROMPT,
            user_msg=user_msg
        )
        
        report = res.parsed
        print(f"▶ Score: {report.score} / 5")
        print(f"▶ Rationale: {report.rationale}")
        print(f"▶ Interface: {report.interface_consistency}")
        print(f"▶ Coverage: {report.requirement_coverage}")
        print(f"▶ Suggestions: {report.suggestions}")
        print("-"*80 + "\n")
        
    except Exception as e:
        print(f"Judge Error: {str(e)}")
