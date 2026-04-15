from pydantic import BaseModel, Field
from typing import List, Optional

class AtomicRequirement(BaseModel):
    REQ_ID: str = Field(description="고유 ID")
    category: str = Field(description="카테고리: Frontend, Backend, Architecture, Database, Security, AI/ML, Infrastructure")
    description: str = Field(description="기능 설명 (한국어)")

class RequirementFeature(BaseModel):
    id: str = Field(description="FEAT_XXX")
    cat: str = Field(description="Category (Frontend, Backend, etc)")
    desc: str = Field(description="Atomic feature description")
    pri: str = Field(description="MoSCoW priority")
    deps: List[str] = Field(default_factory=list, description="Dependency FEAT_IDs")
    tc: str = Field(description="Acceptance criteria / Test criteria")

class RequirementAnalyzerOutput(BaseModel):
    th: str = Field(default="", description="Thinking process")
    features: List[RequirementFeature] = Field(description="Atomic features")

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

class StackSourceData(BaseModel):
    name: str = Field(description="기술 스택 이름")
    description: str = Field(description="기술 개요 및 설명")
    version: str = Field(default="unknown", description="최신 stable 버전")
    license: Optional[str] = Field(default="unknown", description="라이선스 정보")
    last_updated: str = Field(default="unknown", description="마지막 업데이트 일자")
    stars: int = Field(default=0, description="GitHub 별 개수 등 신뢰지수")
    source_type: str = Field(description="출처 구분 (npm|github|pypi|web)")
    url: str = Field(description="원천 데이터 URL")
    install_cmd: Optional[str] = Field(default=None, description="설치 명령어 (예: pip install ...)")

class StackCrawlingOutput(BaseModel):
    status: str = Field(description="Pass | Error")
    results: List[StackSourceData] = Field(default_factory=list, description="수집된 메타데이터 목록")
    error_message: Optional[str] = Field(default=None, description="에러 발생 시 상세 메시지")
    thinking: str = Field(default="", description="크롤링 및 가공 과정 기록")

class GuardianOutput(BaseModel):
    status: str = Field(description="APPROVED | REJECTED")
    final_data: Optional[StackSourceData] = Field(default=None, description="최종 정제 및 병합된 데이터")
    rejection_reason: Optional[str] = Field(default=None, description="거절 사유 (REJECTED인 경우)")
    thinking: str = Field(default="", description="가디언의 판단 근거 및 분석 사고 과정")

class EmbeddingOutput(BaseModel):
    vector: List[float] = Field(description="추출된 고차원 벡터 데이터")
    text_embedded: str = Field(description="실제 임베딩에 사용된 통합 텍스트")
    model_name: str = Field(description="사용된 임베딩 모델 명칭")
    thinking: str = Field(default="", description="임베딩 과정 및 정보")

class StackMapping(BaseModel):
    f_id: str = Field(description="Feature ID")
    dom: str = Field(description="Domain (Frontend, Backend, etc)")
    pkg: str = Field(default="unknown", description="Package/Library name")
    reason: str = Field(default="", description="Rationale")
    status: str = Field(default="PENDING_CRAWL", description="APPROVED | PENDING_CRAWL")
    query: Optional[str] = Field(default=None, description="Crawler query")

class StackPlannerOutput(BaseModel):
    th: str = Field(description="Thinking process")
    m: List[StackMapping] = Field(default_factory=list, description="Stack mappings")

# ── PM Analysis 산출물 (PM_BUNDLE) ─────────────────────────
class RTMItem(BaseModel):
    feature_id: str = Field(description="요구사항 ID (FEAT_XXX)")
    category: str = Field(description="카테고리: Frontend, Backend, ...")
    description: str = Field(description="원자 단위 기능 설명")
    priority: str = Field(description="Must-have | Should-have | Could-have | Won't-have")
    dependencies: List[str] = Field(default_factory=list, description="의존하는 FEAT_ID 목록")
    test_criteria: str = Field(default="", description="수락 기준")

class TechStackItem(BaseModel):
    f_id: str = Field(description="Feature ID")
    dom: str = Field(description="Domain")
    pkg: str = Field(default="unknown", description="Package")
    status: str = Field(default="APPROVED")

class PMBundleMetadata(BaseModel):
    session_id: str = Field(description="프로젝트 루트 (세션) 식별자")
    bundle_id: str = Field(description="번들 식별자 (예: pm_bundle_v1_0)")
    version: str = Field(default="v1.0", description="리비전 버전 (업데이트 시 증가)")
    phase: str = Field(default="PM", description="기획/설계 단계 구분 (PM, SA 등)")
    artifact_type: str = Field(default="RTM_STACK_BUNDLE", description="산출물 세부 종류")
    created_at: str = Field(description="생성 시각 (ISO 8601)")

class PMBundleData(BaseModel):
    rtm: List[RTMItem] = Field(default_factory=list, description="요구사항 추적 행렬")
    tech_stacks: List[TechStackItem] = Field(default_factory=list, description="기술 스택 매핑 목록")

class PMBundle(BaseModel):
    metadata: PMBundleMetadata
    data: PMBundleData

class PMAnalysisOutput(BaseModel):
    th: str = Field(default="", description="QA-PM validation thinking")
    bundle: PMBundle = Field(description="최종 PM_BUNDLE")
    coverage_rate: float = Field(default=0.0, description="APPROVED 스택으로 덮인 기능 비율 (0~1)")
    warnings: List[str] = Field(default_factory=list, description="미매핑 기능, 호환성 경고 등")

# ── RAG Knowledge Schemas (Table 04 & 05) ──────────────────

class ArtifactKnowledgeMetadata(BaseModel):
    """PM & SA RAG 메타데이터 (Table 04)"""
    session_id: str
    chunk_id: str
    version: str
    phase: str
    artifact_type: str
    feature_id: Optional[str] = None

class StackKnowledgeMetadata(BaseModel):
    """STACK RAG 메타데이터 (Table 05)"""
    session_id: str
    stack_id: str
    domain: str
    package_name: str
    version_req: str
    install_cmd: str
