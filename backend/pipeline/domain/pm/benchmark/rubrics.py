"""
PM Benchmark Scoring Rubrics
Judge LLM(Gemini 3.0 Pro)이 사용할 정교한 채점 기준표입니다.
"""

PM_BENCH_RUBRICS = {
    "EdgeCaseCoverage": {
        "name": "예외 상황 도출력 (Edge-Case Coverage)",
        "description": "정상 흐름 외에 발생 가능한 예외 시나리오(장애, 오류, 유효성 검사 등)를 얼마나 잘 예측하여 기율에 반영했는가?",
        "criteria": {
            "5": "3개 이상의 핵심 예외 시나리오(예: 네트워크 장애, 유효성 오류, 중복 요청 등)를 명확히 정의함.",
            "3": "1-2개의 기본적인 예외 상황만 언급했거나, 구체성이 부족함.",
            "1": "해피 패스(정상 흐름)만 서술하고 예외 상황에 대한 고려가 없음."
        }
    },
    "OverSpecPenalty": {
        "name": "오버 엔지니어링 방지 (Over-specification Penalty)",
        "description": "주어진 요구사항 범위를 넘어선 과도한 인프라나 복잡한 기능을 추가하지 않았는가? (감점 지표)",
        "criteria": {
            "5": "요구사항 범위를 정확히 지켰으며 불필요한 복잡성이 없음.",
            "3": "약간의 과잉 설계가 보이나 전체 시스템의 복잡성을 크게 해치지 않음.",
            "1": "간단한 기능에 불필요한 마이크로서비스, 메시지 큐 등 과도한 아키텍처를 도입함."
        }
    },
    "Actionability": {
        "name": "실행 가능성 및 원자성 (Actionability / Atomicity)",
        "description": "생성된 기능 명세가 개발자가 즉시 구현에 착수할 수 있을 만큼 원자적이고 명확한가?",
        "criteria": {
            "5": "각 기능이 단일 책임 원칙에 따라 명확히 분해되어 있으며, 수락 기준(Test Criteria)이 구체적임.",
            "3": "기능 단위가 다소 뭉쳐 있어 추가적인 분해가 필요해 보임.",
            "1": "명세가 모호하여 개발자가 구현 방향을 잡기 위해 추가 질문이 필수적임."
        }
    }
}

JUDGE_SYSTEM_PROMPT = f"""
당신은 베테랑 Product Manager이자 시스템 설계 전문가입니다.
사용자가 제출한 PM 파이프라인의 결과물을 아래의 루브릭(Rubric)에 따라 엄격하게 채점하세요.

[채점 가이드라인]
{PM_BENCH_RUBRICS}

[출력 형식]
반드시 아래 JSON 형식을 지켜주세요.
{{
    "scores": {{
        "EdgeCaseCoverage": <점수1-5>,
        "OverSpecPenalty": <점수1-5>,
        "Actionability": <점수1-5>
    }},
    "rationale": {{
        "EdgeCaseCoverage": "<상세 근거>",
        "OverSpecPenalty": "<상세 근거>",
        "Actionability": "<상세 근거>"
    }},
    "overall_feedback": "<전체적인 총평>"
}}

[주의사항]
- 숫자로만 평가하지 말고, 왜 그런 점수를 주었는지 'rationale'에 구체적인 예시를 들어 설명하세요.
- 비판적이고 냉철하게 평가하세요.
"""
