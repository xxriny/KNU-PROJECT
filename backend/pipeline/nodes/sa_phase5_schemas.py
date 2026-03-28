"""SA Phase 5 — Pydantic 스키마 및 LLM 프롬프트"""

from typing import List
from pydantic import BaseModel, Field


class RequirementMapping(BaseModel):
    REQ_ID: str = Field(description="요구사항 ID")
    layer: str = Field(description="반드시 다음 중 하나: Presentation | Application | Domain | Infrastructure")
    reason: str = Field(description="해당 레이어에 배치한 구체적인 기술적 이유 (한국어 1문장)")


class ArchitectureMappingOutput(BaseModel):
    thinking: str = Field(default="", description="매핑 추론 과정 (3줄 이내)")
    pattern_name: str = Field(default="Clean Architecture", description="적용된 아키텍처 패턴")
    mapped_requirements: List[RequirementMapping] = Field(description="각 요구사항의 레이어 매핑 결과")


class ModuleFunctionalLabel(BaseModel):
    canonical_id: str = Field(description="모듈 canonical ID (입력값 그대로 반환)")
    functional_name: str = Field(description="모듈의 핵심 기능명/역할 (한국어, 15자 이내, 명사형). 예: 파이프라인 오케스트레이터, 코드 AST 스캐너")


class ModuleLabelBatchOutput(BaseModel):
    labels: List[ModuleFunctionalLabel] = Field(description="각 모듈의 기능명 레이블 목록 (입력 모듈 전부 포함)")


MAPPING_SYSTEM_PROMPT = """\
당신은 소프트웨어 시스템 아키텍트입니다.
제공된 요구사항(RTM)을 분석하여 '클린 아키텍처(Clean Architecture)'의 고정된 4가지 계층 중 하나에 각각 매핑하세요.

[고정된 계층(Layer) 및 매핑 가이드]
1. Presentation: 사용자 UI, 클라이언트 통신, 컨트롤러, API 엔드포인트 (예: 화면 렌더링, API 응답)
2. Application: 유스케이스, 비즈니스 흐름 제어, 트랜잭션 관리 (예: 사용자 인증 로직 흐름, 특정 기능 오케스트레이션)
3. Domain: 시스템의 핵심 비즈니스 룰, 엔티티, 순수 알고리즘 (예: 역량 평가 계산식, 연봉 산정 로직 등 프레임워크에 의존하지 않는 순수 로직)
4. Infrastructure: 외부 DB 연동, API 통신, 파일 I/O, 보안/암호화 등 기술적 구현체 (예: 카카오톡 연동, MongoDB 저장, On-Device 벡터화)

[규칙]
1. 새로운 계층을 절대 임의로 만들어내지 마세요. 오직 위 4개 중 하나만 선택해야 합니다.
2. 요구사항의 'description'을 깊이 읽고, 단순 카테고리(Frontend/Backend)에 속지 말고 실제 수행하는 역할을 바탕으로 배치하세요.
3. 각 매핑의 이유(reason)를 1문장으로 명확히 작성하세요."""


MODULE_LABEL_SYSTEM_PROMPT = """\
당신은 소프트웨어 아키텍트입니다.
제공된 모듈 목록의 파일 경로와 주요 함수명을 분석하여 각 모듈의 핵심 기능명 또는 역할을 한국어로 작성하세요.

[규칙]
1. functional_name은 15자 이내 한국어 명사형으로 작성하세요. (예: "파이프라인 오케스트레이터", "코드 AST 스캐너", "WS 수신 핸들러")
2. canonical_id는 입력값을 절대 변경하지 말고 그대로 반환하세요.
3. 파일 경로와 함수명을 모두 참고하여 역할을 정확히 추론하세요.
4. 입력된 모든 모듈에 대해 빠짐없이 labels를 채워주세요."""
