from pydantic import BaseModel, Field
from typing import List, Optional

class AtomicRequirement(BaseModel):
    REQ_ID: str = Field(description="고유 ID")
    category: str = Field(description="카테고리: Frontend, Backend, Architecture, Database, Security, AI/ML, Infrastructure")
    description: str = Field(description="기능 설명 (한국어)")

class AtomizerMetadata(BaseModel):
    project_name: str = ""
    action_type: str = ""
    status: str = "Success"
    total_requirements: int = 0

class AtomizerOutput(BaseModel):
    thinking_process: str = Field(default="", description="기능 분해 사고 과정")
    metadata: AtomizerMetadata = Field(default_factory=AtomizerMetadata)
    clarification_questions: List[str] = Field(default_factory=list, description="모호함 해소를 위한 추가 질문")
    atomic_requirements: List[AtomicRequirement] = Field(description="원자화된 요구사항 목록")

class PrioritizedRequirement(BaseModel):
    REQ_ID: str = Field(description="고유 ID")
    category: str = Field(description="카테고리")
    description: str = Field(description="기능 설명")
    priority: str = Field(description="Must-have | Should-have | Could-have")
    rationale: str = Field(description="우선순위 근거 (한국어)")

class PrioritizerOutput(BaseModel):
    thinking: str = Field(default="", description="우선순위 부여 과정")
    requirements: List[PrioritizedRequirement] = Field(description="순위가 지정된 요구사항 목록")

class RTMRequirement(BaseModel):
    REQ_ID: str = Field(description="고유 ID")
    category: str = Field(description="카테고리")
    description: str = Field(description="기능 설명")
    priority: str = Field(description="Must-have | Should-have | Could-have")
    rationale: str = Field(default="")
    depends_on: List[str] = Field(default_factory=list, description="의존 REQ_ID 목록")
    test_criteria: str = Field(default="미정", description="수락 기준")

class RTMBuilderOutput(BaseModel):
    thinking: str = Field(default="", description="의존성 매핑 추론")
    requirements: List[RTMRequirement] = Field(description="RTM 요구사항 목록")

class CodeFunctionLink(BaseModel):
    file: str
    func_name: str
    lineno: int
    confidence: float
    reason: str = ""

class SemanticNode(BaseModel):
    id: str
    label: str
    category: str
    tags: List[str] = Field(default_factory=list)
    code_links: List[CodeFunctionLink] = Field(default_factory=list)

class SemanticEdge(BaseModel):
    source: str
    target: str
    relation: str

class SemanticIndexerOutput(BaseModel):
    thinking: str = ""
    nodes: List[SemanticNode]
    edges: List[SemanticEdge]

class ContextSpecOutput(BaseModel):
    thinking: str = ""
    summary: str
    key_decisions: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
    tech_stack_suggestions: List[str] = Field(default_factory=list)
    risk_factors: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
