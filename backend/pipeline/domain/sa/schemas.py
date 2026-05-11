"""
SA Pipeline Schemas — DSL 기반 초압축 출력 스키마 정의
활성 노드: merge_project → component_scheduler → sa_unified_modeler → sa_analysis
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
