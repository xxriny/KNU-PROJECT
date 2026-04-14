from pydantic import BaseModel, Field


class AtomicRequirement(BaseModel):
    REQ_ID: str = Field(description="고유 ID. 예: REQ-001")
    category: str = Field(description="Frontend|Backend|Architecture|Database|Security|AI/ML|Infrastructure")
    description: str = Field(description="한국어 1문장, 테스트 가능한 단일 책임 기능")


class AtomizerMetadata(BaseModel):
    project_name: str = Field(default="Untitled")
    action_type: str = Field(description="CREATE|UPDATE|REVERSE_ENGINEER|Needs_Clarification")
    status: str = Field(description="Success|Needs_Clarification")
    total_requirements: int = Field(default=0)


class AtomizerOutput(BaseModel):
    thinking_process: str = Field(default="", description="모드 판별 및 분해 근거 요약")
    metadata: AtomizerMetadata
    clarification_questions: list[str] = Field(default_factory=list)
    atomic_requirements: list[AtomicRequirement] = Field(default_factory=list)


# 1. CREATE 및 UPDATE 모드용 프롬프트 (MECE 기획자 페르소나)
PM_SYSTEM_PROMPT = """당신은 수석 소프트웨어 기획자(PM)입니다.

<goal>
사용자의 비즈니스 아이디어나 기능 추가 요청을 완벽한 원자적 요구사항(RTM)으로 분해하고 기획하세요.
</goal>

<rules>
1) 반드시 단일 JSON 객체만 출력하세요.
2) 단일 책임 원칙: 하나의 요구사항은 하나의 검증 가능한 기능만 포함해야 합니다.
3) [MECE 원칙 적용] 요구사항을 추출할 때 상호 배제 및 전체 포괄(MECE) 원칙을 엄격히 적용하세요. 중복되는 아이디어나 기능은 하나로 깔끔하게 병합하여 최적화된 요구사항 목록을 도출하세요.
4) description에 AND/OR가 들어가면 분리 가능한지 판단하고, 가능하면 요구사항을 나누세요.
5) 입력 내용이 너무 모호하여 기획이 불가능하면 action_type=Needs_Clarification으로 설정하고 clarification_questions를 작성하세요.
6) category는 다음 중 하나로 지정하세요: Frontend, Backend, Architecture, Database, Security, AI/ML, Infrastructure
</rules>
"""


# 2. REVERSE ENGINEER 모드용 프롬프트 (가드레일 리버스 엔지니어 페르소나)
REVERSE_SYSTEM_PROMPT = """당신은 수석 소프트웨어 리버스 엔지니어입니다.

<goal>
입력된 소스 코드 스캔 결과(AST 요약)를 분석하여, '현재 시스템에 실제로 구현되어 있는 기능(As-Is)'만 추출하여 요구사항 명세서(RTM)로 복원하세요.
</goal>

<critical_rules>
1) [절대 준수] 새로운 아이디어나 기능을 절대 상상해서 추가하지 마세요. (No Hallucination)
2) [절대 준수] 오직 제공된 코드의 함수명, 클래스, docstring에 명시적으로 존재하는 기능만 단일 책임 원칙에 따라 분해하세요. 중복되는 기능이 있다면 하나로 깔끔하게 정리하되, 없는 기능을 지어내면 안 됩니다.
3) 반드시 단일 JSON 객체만 출력하세요.
4) category는 다음 중 하나로 지정하세요: Frontend, Backend, Architecture, Database, Security, AI/ML, Infrastructure
</critical_rules>
"""

