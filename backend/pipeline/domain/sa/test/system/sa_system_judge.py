import json
import os
from typing import Dict, Any
from pydantic import BaseModel, Field
from pipeline.core.utils import call_structured
from dotenv import load_dotenv

load_dotenv()

class SASystemJudgeOutput(BaseModel):
    score: int = Field(..., description="1-5점 사이의 시스템 통합 점수")
    rationale: str = Field(..., description="시스템 맥락(RAG) 유지 및 설계 정합성 평가")
    rag_consistency: str = Field(..., description="기존 시스템(system_scan)과의 일관성")
    production_readiness: str = Field(..., description="실제 배포 가능 수준 평가")
    suggestions: str = Field(..., description="아키텍처 고도화 제안")

JUDGE_SYSTEM_PROMPT = """
당신은 실제 서비스 운영 환경을 고려하는 '수석 시스템 아키텍트'입니다.
신규 요구사항이 기존 시스템(RAG/Scan)의 구조를 파괴하지 않고 얼마나 조화롭게 설계되었는지를 평가합니다.

[평가 포인트]
1. RAG 기반 설계: 기존에 존재하는 엔티티, 기술 스택, API 스타일을 존중하며 확장했는가?
2. 중복 방지: 이미 존재하는 기능을 중복으로 설계하지 않았는가?
3. 확장성: 신규 추가된 테이블이나 API가 향후 기능 확장에 유연한 구조인가?
4. 검증 능력: `sa_analysis`가 하이브리드 설계(기존+신규)의 충돌 지점을 정확히 감지했는가?

결함을 발견하면 점수를 깎기보다, 분석가(SA Analysis)가 그 결함을 정확히 보고했는지에 더 큰 비중을 두어 평가하세요.
"""

def judge_system(scenario_name: str, requirements: list, system_scan: dict, sa_bundle: Dict[str, Any]):
    print(f"\n" + "#"*25 + f" [SYSTEM JUDGE] {scenario_name} " + "#"*25)
    
    api_key = os.getenv("GEMINI_API_KEY")
    user_msg = f"""
    [Scenario]
    {scenario_name}
    
    [Requirements]
    {json.dumps(requirements, indent=2, ensure_ascii=False)}
    
    [Existing System Context (RAG)]
    {json.dumps(system_scan, indent=2, ensure_ascii=False)}
    
    [Final SA Bundle]
    {json.dumps(sa_bundle, indent=2, ensure_ascii=False)}
    """

    try:
        res = call_structured(
            api_key=api_key,
            model="gemini-3.1-pro-preview",
            schema=SASystemJudgeOutput,
            system_prompt=JUDGE_SYSTEM_PROMPT,
            user_msg=user_msg
        )
        
        report = res.parsed
        print(f"▶ Score: {report.score} / 5")
        print(f"▶ Rationale: {report.rationale}")
        print(f"▶ RAG Consistency: {report.rag_consistency}")
        print(f"▶ Production Readiness: {report.production_readiness}")
        print(f"▶ Suggestions: {report.suggestions}")
        print("#"*80 + "\n")
        
    except Exception as e:
        print(f"Judge Error: {str(e)}")
