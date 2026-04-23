from pydantic import BaseModel, Field, model_validator
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

class SystemScanOutput(SAStatus):
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

# --- New SA Overhaul Schemas ---

class MergeProjectOutput(BaseModel):
    thinking: str = Field(default="", description="병합 전략 추론 과정")
    mode: str = Field(description="CREATE | UPDATE | REVERSE_ENGINEER")
    base_context: Dict[str, Any] = Field(description="기존 시스템의 컨텍스트 요약")
    merge_strategy: str = Field(description="충돌 해결 및 설계 방향 서술")

class ComponentDefinition(BaseModel):
    domain: str = Field(description="Frontend | Backend | etc")
    component_name: str = Field(description="컴포넌트 이름")
    role: str = Field(description="역할 설명")
    dependencies: List[str] = Field(default_factory=list, description="의존성 컴포넌트 목록")

class ComponentSchedulerOutput(BaseModel):
    thinking: str = Field(default="", description="컴포넌트 설계 추론 과정")
    components: List[ComponentDefinition] = Field(description="설계된 컴포넌트 목록")

class ApiDefinition(BaseModel):
    endpoint: str = Field(description="HTTP 메서드 및 경로 (예: POST /api/v1/auth/login)")
    request_schema: Dict[str, Any] = Field(description="요청 JSON 스키마")
    response_schema: Dict[str, Any] = Field(description="응답 JSON 스키마")

class TableDefinition(BaseModel):
    table_name: str = Field(description="테이블 이름")
    columns: List[Dict[str, Any]] = Field(description="컬럼 정의")

class ApiModelerOutput(BaseModel):
    thinking: str = Field(default="", description="API 설계 추론 과정")
    apis: List[ApiDefinition] = Field(description="API 명세 목록")

class DataModelerOutput(BaseModel):
    thinking: str = Field(default="", description="DB 스키마 설계 추론 과정")
    tables: List[TableDefinition] = Field(description="데이터베이스 테이블 정의 목록")


class SAAnalysisOutput(BaseModel):
    thinking: str = Field(default="", description="최종 검증 및 정합성 검토 과정")
    phase: str = Field(default="SA")
    version: str = Field(description="현재 버전")
    bundle_id: str = Field(description="세션 ID 기반 번들 ID")
    status: str = Field(default="PASS", description="PASS | FAIL | WARNING")
    gaps: List[str] = Field(default_factory=list, description="요구사항 대비 누락되거나 모순된 항목 목록")
    data: Dict[str, Any] = Field(description="컴포넌트, API, 테이블 통합 데이터")
