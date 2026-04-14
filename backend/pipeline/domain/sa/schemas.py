from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

class SAStatusEnum(str, Enum):
    PASS = "Pass"
    NEEDS_CLARIFICATION = "Needs_Clarification"
    FAIL = "Fail"
    SKIPPED = "Skipped"
    WARNING = "Warning_Hallucination_Detected"
    ERROR = "Error"

class SAStatus(BaseModel):
    status: SAStatusEnum = Field(description="상태 판정")
    confidence: float = Field(default=0.7, description="신뢰도 0.0 ~ 1.0")
    assumptions: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)

class RequirementImpact(BaseModel):
    """요구사항별 영향도 분석 정보"""
    req_id: str = Field(description="요구사항 ID")
    impact_level: str = Field(description="High | Medium | Low")
    change_type: str = Field(description="Create | Modify | Delete")
    side_effects: str = Field(description="예상 부작용 및 주의사항")

class GapReportOutput(BaseModel):
    """sa_phase2 LLM 출력 스키마"""
    thinking: str = Field(default="", description="영향도 분석 추론 과정")
    overall_risk: str = Field(description="프로젝트 전체의 아키텍처 수정 위험도 요약")
    gap_report: List[RequirementImpact] = Field(description="요구사항별 상세 영향도 분석")

class SAPhase1Output(SAStatus):
    thinking: str = ""
    architecture_assessment: str = ""
    key_modules: List[str] = Field(default_factory=list)
    concerns: List[str] = Field(default_factory=list)
    recommended_focus: List[str] = Field(default_factory=list)

class ArchitectureMappingOutput(BaseModel):
    thinking: str = ""
    pattern_name: str = "Clean Architecture"
    mapped_requirements: List[dict] = Field(default_factory=list)

class SecurityDesignOutput(BaseModel):
    thinking: str = ""
    defined_roles: List[dict] = Field(default_factory=list)
    authz_matrix: List[dict] = Field(default_factory=list)
    trust_boundaries: List[dict] = Field(default_factory=list)

class InterfaceDesignOutput(BaseModel):
    thinking: str = ""
    interface_contracts: List[dict] = Field(default_factory=list)
    guardrails: List[str] = Field(default_factory=list)

class SAPhase8Output(SAStatus):
    topo_queue: List[str] = Field(default_factory=list)
    cyclic_requirements: List[str] = Field(default_factory=list)
    parallel_batches: List[List[str]] = Field(default_factory=list)
    dependency_sources: Dict[str, Any] = Field(default_factory=dict)
