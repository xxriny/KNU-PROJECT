"""
PM Agent Pipeline — Pydantic 출력 스키마 정의

모든 LangGraph 노드의 LLM 출력을 Pydantic 모델로 강제한다.
with_structured_output()에 주입하여 JSON 파싱 에러를 근본적으로 제거.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


# ── 노드 2: Prioritizer ──────────────────────────

class PrioritizedRequirement(BaseModel):
    """우선순위가 부여된 요구사항"""
    REQ_ID: str = Field(description="고유 ID")
    category: str = Field(description="카테고리")
    description: str = Field(description="기능 설명 (한국어)")
    priority: str = Field(description="Must-have | Should-have | Could-have")
    rationale: str = Field(description="우선순위 근거 (한국어, 1문장)")


class PrioritizerOutput(BaseModel):
    """Prioritizer 노드의 구조화된 출력"""
    thinking: str = Field(default="", description="간결한 추론 과정")
    requirements: List[PrioritizedRequirement] = Field(description="우선순위 부여된 요구사항 목록")


# ── 노드 3: RTM Builder ──────────────────────────

class RTMRequirement(BaseModel):
    """RTM 매트릭스 요구사항 (의존성 포함)"""
    REQ_ID: str = Field(description="고유 ID")
    category: str = Field(description="카테고리")
    description: str = Field(description="기능 설명")
    priority: str = Field(description="Must-have | Should-have | Could-have")
    rationale: str = Field(default="", description="우선순위 근거")
    depends_on: List[str] = Field(default_factory=list, description="선행 REQ_ID 목록. 데이터 흐름에 따라 반드시 명시.")
    test_criteria: str = Field(default="미정", description="테스트 수락 기준 (한국어, 1문장)")


class RTMBuilderOutput(BaseModel):
    """RTM Builder 노드의 구조화된 출력"""
    thinking: str = Field(default="", description="의존성 체인 추론 과정")
    requirements: List[RTMRequirement] = Field(description="의존성이 매핑된 RTM 요구사항 목록")


# ── 노드 4: Semantic Indexer ──────────────────────

class CodeFunctionLink(BaseModel):
    """REQ_ID ↔ 소스코드 함수 매핑"""
    file: str = Field(description="소스파일 상대 경로")
    func_name: str = Field(description="함수명")
    lineno: int = Field(description="함수 시작 라인 번호")
    confidence: float = Field(default=0.0, description="매핑 신뢰도 0.0 ~ 1.0")
    reason: str = Field(default="", description="매핑 근거 (한국어 1문장)")


class SemanticNode(BaseModel):
    """시맨틱 그래프 노드"""
    id: str = Field(description="REQ_ID")
    label: str = Field(description="기능 설명")
    category: str = Field(description="카테고리")
    tags: List[str] = Field(default_factory=list, description="시맨틱 검색용 키워드 2-3개")
    code_links: List[CodeFunctionLink] = Field(default_factory=list, description="연결된 소스코드 함수 목록")


class SemanticEdge(BaseModel):
    """시맨틱 그래프 엣지"""
    source: str = Field(description="출발 REQ_ID")
    target: str = Field(description="도착 REQ_ID")
    relation: str = Field(description="depends_on | related_to | part_of | extends")


class SemanticIndexerOutput(BaseModel):
    """Semantic Indexer 노드의 구조화된 출력"""
    thinking: str = Field(default="", description="시맨틱 분석 과정")
    nodes: List[SemanticNode] = Field(description="시맨틱 노드 목록")
    edges: List[SemanticEdge] = Field(description="시맨틱 엣지 목록")


# ── 노드 5: Context Spec ─────────────────────────

class ContextSpecOutput(BaseModel):
    """Context Spec 노드의 구조화된 출력"""
    thinking: str = Field(default="", description="종합 추론 과정")
    summary: str = Field(description="프로젝트 요약 (한국어, 2-3문장)")
    key_decisions: List[str] = Field(default_factory=list, description="핵심 결정 사항")
    open_questions: List[str] = Field(default_factory=list, description="미해결 질문")
    tech_stack_suggestions: List[str] = Field(default_factory=list, description="기술 스택 제안")
    risk_factors: List[str] = Field(default_factory=list, description="리스크 요인")
    next_steps: List[str] = Field(default_factory=list, description="SA 에이전트 다음 단계")


# ── SA 8단계 공통/출력 스키마 ─────────────────

class SAStatusEnum(str, Enum):
    PASS = "Pass"
    NEEDS_CLARIFICATION = "Needs_Clarification"
    FAIL = "Fail"
    SKIPPED = "Skipped"
    WARNING = "Warning_Hallucination_Detected"
    ERROR = "Error"

class SAStatus(BaseModel):
    status: SAStatusEnum = Field(description="Pass | Needs_Clarification | Fail | Skipped | Warning_Hallucination_Detected | Error")
    confidence: float = Field(default=0.7, description="0.0 ~ 1.0")
    assumptions: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)


class SAPhase1Output(SAStatus):
    source_dir: str = ""
    scanned_files: int = 0
    scanned_functions: int = 0


class SAPhase2Output(SAStatus):
    requirement_count: int = 0
    touched_files: List[str] = Field(default_factory=list)


class SAPhase3Output(SAStatus):
    decision: str = Field(description="Pass | Needs_Clarification | Fail")
    alternatives: List[str] = Field(default_factory=list)


class SAPhase4Output(SAStatus):
    proposed_packages: List[str] = Field(default_factory=list)
    verified_packages: List[str] = Field(default_factory=list)
    rejected_packages: List[str] = Field(default_factory=list)


class SAPhase5Output(SAStatus):
    pattern: str = "Clean Architecture"
    mapped_requirements: List[dict] = Field(default_factory=list)


class SAPhase6Output(SAStatus):
    rbac_roles: List[str] = Field(default_factory=list)
    trust_boundaries: List[str] = Field(default_factory=list)


class SAPhase7Output(SAStatus):
    interface_contracts: List[dict] = Field(default_factory=list)
    guardrails: List[str] = Field(default_factory=list)


class SAPhase8Output(SAStatus):
    topo_queue: List[str] = Field(default_factory=list)
    cyclic_requirements: List[str] = Field(default_factory=list)


class SAOutput(BaseModel):
    code_analysis: dict = Field(default_factory=dict)
    impact_analysis: dict = Field(default_factory=dict)
    feasibility: dict = Field(default_factory=dict)
    dependency_sandbox: dict = Field(default_factory=dict)
    architecture_mapping: dict = Field(default_factory=dict)
    security_boundary: dict = Field(default_factory=dict)
    interface_contracts: dict = Field(default_factory=dict)
    topology_queue: dict = Field(default_factory=dict)
