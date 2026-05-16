"""
SA Pipeline Schemas — DSL 기반 초압축 출력 스키마 정의
활성 노드: merge_project → component_scheduler → sa_unified_modeler → sa_test_analysis → sa_project_structure → sa_embedding
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any


# ── Merge Project ────────────────────────────────────────

class MergeProjectOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    thinking: str = Field(alias="th", default="", description="단어 5개")
    mode: str = Field(alias="md", description="C|U|R")
    base_context: Dict[str, Any] = Field(alias="bc")
    merge_strategy: str = Field(alias="ms")


# ── Forensic Profiler ────────────────────────────────────

class FileProfile(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    path: str = Field(alias="p")
    role: str = Field(alias="r", description="DB|API|SERVICE|UI|STORE|CONFIG|UTIL")
    reason: str = Field(alias="rs", default="")

class ForensicProfilerOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    thinking: str = Field(alias="th", default="")
    profiles: List[FileProfile] = Field(alias="pf")


# ── Component Scheduler ─────────────────────────────────

class ComponentDefinition(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    domain: str = Field(alias="dm", description="F|B")
    name: str = Field(alias="nm")
    role: str = Field(alias="rl")
    rtms: str = Field(alias="rt", description="ID,ID")
    deps: str = Field(alias="dp", default="", description="ID,ID")

class ComponentSchedulerOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    thinking: str = Field(alias="th", default="", description="단어 5개")
    components: List[ComponentDefinition] = Field(alias="cp")


# ── Unified Modeler (API + DB) ──────────────────────────

class ApiDefinition(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    endpoint: str = Field(description="Method and Path (e.g., GET /api/user)")
    request_schema: str = Field(alias="req", description="Detailed request parameters/types")
    response_schema: str = Field(alias="res", description="Detailed response structure")

class TableDefinition(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    table_name: str = Field(alias="nm")
    columns: str = Field(alias="cl", description="Detailed column definitions (name:type:constraints)")

class SAUnifiedModelerOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    thinking: str = Field(alias="th", default="", description="Technical rationale")
    apis: List[ApiDefinition] = Field(alias="ap")
    tables: List[TableDefinition] = Field(alias="tb")


# ── SA Analysis (검증) ──────────────────────────────────

class SAAnalysisOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    thinking: str = Field(alias="th", default="", description="단어 5개")
    phase: str = Field(alias="ph", default="SA")
    version: str = Field(alias="vs")
    bundle_id: str = Field(alias="bi")
    status: str = Field(alias="st", default="P", description="P|F|W")
    gaps: List[str] = Field(alias="gp", default_factory=list, description="T|R|A")
    definitions: Dict[str, Any] = Field(alias="df", default_factory=dict)


# ── SA Advisor (수정 조언) ──────────────────────────────

class AdvisorRecommendation(BaseModel):
    priority: str = Field(description="Critical|Warning|Info")
    target: str = Field(description="수정 대상 (파일/필드/테이블 등)")
    action: str = Field(description="구체적 수정 방법")

class SAAdvisorOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    thinking: str = Field(alias="th", default="", description="단어 3개")
    summary: str = Field(alias="sm", default="", description="전체 요약")
    recommendations: List[AdvisorRecommendation] = Field(alias="rc", default_factory=list)


# ── SA Test Analysis ─────────────────────────────────────

class RiskZone(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    component_name: str = Field(alias="cn")
    risk_level: str = Field(alias="rl", description="critical|high|medium|low")
    reason: str = Field(alias="rs")
    mitigation: str = Field(alias="mt")

class UnitTestSpec(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    component_name: str = Field(alias="cn")
    key_invariants: List[str] = Field(alias="ki")
    mock_targets: List[str] = Field(alias="mt")
    edge_cases: List[str] = Field(alias="ec")

class IntegrationTestSpec(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    endpoint: str = Field(alias="ep")
    db_approach: str = Field(alias="db")
    transaction_scenario: str = Field(alias="ts")
    contract_pair: str = Field(alias="cp", default="")

class SystemTestSpec(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    critical_path: str = Field(alias="cp")
    sla_target: str = Field(alias="sl")
    chaos_scenarios: List[str] = Field(alias="cs")

class AcceptanceTestSpec(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    feat_id: str = Field(alias="fi")
    given: str = Field(alias="gv")
    when: str = Field(alias="wh")
    then_: str = Field(alias="tn")
    edge_case: str = Field(alias="ec", default="")

class SATestAnalysisOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    thinking: str = Field(alias="th", default="")
    test_philosophy: str = Field(alias="tp")
    risk_zones: List[RiskZone] = Field(alias="rz")
    unit_specs: List[UnitTestSpec] = Field(alias="us")
    integration_specs: List[IntegrationTestSpec] = Field(alias="is_")
    system_specs: List[SystemTestSpec] = Field(alias="ss")
    acceptance_specs: List[AcceptanceTestSpec] = Field(alias="as_")
    test_data_strategy: str = Field(alias="td")
    automation_priority: List[str] = Field(alias="ap")


class SAProjectStructureOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    thinking: str = Field(alias="th", default="")
    directories: List[str] = Field(alias="dr", description="List of directory paths to create")
    files: List[str] = Field(alias="fl", description="List of file paths to create")
    component_mapping: Dict[str, List[str]] = Field(alias="cm", default_factory=dict)
    conventions: List[str] = Field(alias="cv", default_factory=list)
