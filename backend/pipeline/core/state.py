"""
PM Agent Pipeline — 공유 상태 정의 v9.0
LangGraph StateGraph에서 모든 노드가 읽고 쓰는 상태 스키마.

상태를 _BaseState / _AnalysisFields / _ChatFields / _IdeaFields 로 분리하고,
PipelineState 는 이들의 합집합(union)으로 유지하여 하위 호환성 보장.
"""

from typing import TypedDict, Annotated


# ── 리듀서 함수 ─────────────────────────────────

def _merge_thinking_logs(existing_logs, new_logs):
    """여러 노드에서 동시에 thinking_log를 업데이트할 때 누적"""
    if not isinstance(existing_logs, list):
        existing_logs = []
    if not isinstance(new_logs, list):
        new_logs = []
    return existing_logs + new_logs


def _keep_last_step(existing_step, new_step):
    """여러 노드에서 동시에 current_step을 업데이트할 때 마지막 값 유지"""
    if not new_step:
        return existing_step
    return new_step


def _merge_usage_history(existing, new):
    """토큰 사용 이력을 누적합니다."""
    if not isinstance(existing, list):
        existing = []
    if not isinstance(new, list):
        new = []
    return existing + new


def _sum_cost(existing, new):
    """비용을 합산합니다."""
    return (existing or 0.0) + (new or 0.0)


# ── 기본 상태 (모든 모드 공통) ───────────────────

class _BaseState(TypedDict):
    api_key: str
    model: str
    run_id: str
    error: str
    thinking_log: Annotated[list, _merge_thinking_logs]
    current_step: Annotated[str, _keep_last_step]
    total_retries: int               # LLM 재시도 횟수 누적 (Benchmark용)
    
    # ── 비용 및 토큰 추적 (REQ-010/Phase 0) ──────
    accumulated_usage: Annotated[list, _merge_usage_history] # [{"node": "...", "total_tokens": 100, ...}]
    accumulated_cost: Annotated[float, _sum_cost]           # 총 USD 소모 비용


# ── 분석 모드 필드 ──────────────────────────────

class _AnalysisFields(TypedDict, total=False):
    input_idea: str                  # 사용자 아이디어 텍스트
    project_context: str             # 기존 프로젝트 컨텍스트 (폴더/GitHub)
    source_dir: str                  # AST 스캔 대상 소스코드 폴더 경로
    action_type: str                 # CREATE / UPDATE / REVERSE_ENGINEER / Needs_Clarification
    raw_requirements: list           # [{"id": "REQ-001", ...}]
    features: list                   # RequirementFeature 목록 (requirement_analyzer 산출물)
    next_crawler_inputs: list        # Planner -> Crawler 루프용 쿼리 목록
    prioritized_requirements: list   # raw_requirements + priority, rationale
    rtm_matrix: list                 # [DEPRECATED] requirements_rtm 사용 권장
    requirements_rtm: list           # 최종 RTM (모든 필드 포함)
    semantic_graph: dict             # {"nodes": [...], "edges": [...]}
    context_spec: dict               # {"summary": "...", "key_decisions": [...], ...}
    metadata: dict                   # {"project_name": "...", "action_type": "...", ...}
    clarification_questions: list    # Needs_Clarification 시 질문 목록
    system_scan: dict                  # 기존 코드 구조 분석 결과
    sa_phase2: dict                  # 영향도 분석 결과
    sa_phase3: dict                  # 기술 타당성 결과
    sa_phase4: dict                  # 의존성 샌드박스 검증 결과
    sa_phase5: dict                  # 패턴 기반 아키텍처 매핑 결과
    sa_phase6: dict                  # 보안 경계 설계 결과
    sa_phase7: dict                  # 인터페이스/가드레일 설계 결과
    sa_phase8: dict                  # 위상 정렬 결과
    sa_output: dict                  # SA 최종 통합 산출물
    merged_project: dict             # merge_project가 생성한 단일 결합 입력
    merge_report: dict               # merge_project 판정/병합 리포트

    # ── 기술 스택 (PM Loop) 필드 ────────────────
    loop_count: int                  # 회귀 루프 횟수 추적
    stack_crawler_output: dict       # 크롤링 결과
    guardian_output: dict            # 검증 결과
    stack_embedding_output: dict     # 벡터화 결과
    stack_planner_output: dict       # 최종 매핑 결과
    stack_rag_context: str           # RAG에서 검색된 승인된 스택 정보

    # ── PM Analysis 최종 산출물 ─────────────────
    pm_bundle: dict                  # 최종 PM_BUNDLE JSON (RTM + tech_stacks)
    pm_coverage_rate: float          # APPROVED 스택 커버리지 (0~1)
    pm_warnings: list                # 미매핑/호환성 경고 목록
    is_integration_fail: bool        # 데이터 정합성 실패 여부 (Gate용)


# ── 채팅 수정 모드 필드 ─────────────────────────

class _ChatFields(TypedDict, total=False):
    user_request: str                # 사용자 수정 요청 텍스트
    chat_history: list               # [{"role": "user"|"assistant", "content": str}]
    agent_reply: str                 # 에이전트 응답 메시지
    previous_result: dict            # 이전 파이프라인 결과 (수정 기반)


# ── 아이디어 채팅 모드 필드 ─────────────────────

class _IdeaFields(TypedDict, total=False):
    idea_ready: bool                 # 아이디어 준비 완료 여부
    idea_summary: str                # 분석용 아이디어 요약
    suggested_mode: str              # create | update | reverse


# ── RAG 파이프라인 필드 ──────────────────────────

class _RAGFields(TypedDict, total=False):
    rag_chunks: list                 # CodeChunk dict 목록 (code_chunker 산출물)
    rag_ingest_output: dict          # RAGIngestOutput dict (code_embedding 산출물)
    rag_query_input: str             # 코드 검색 쿼리 텍스트
    rag_query_result: list           # RAGQueryResult dict 목록 (code_retriever 산출물)


# ── 통합 상태 (하위 호환) ───────────────────────

class PipelineState(_BaseState, _AnalysisFields, _ChatFields, _IdeaFields, _RAGFields, total=False):
    """LangGraph 파이프라인 공유 상태 — 모든 모드의 합집합.

    개별 모드가 사용하는 필드는 _AnalysisFields, _ChatFields, _IdeaFields를 참조.
    """
    pass


# ── 헬퍼 함수 ───────────────────────────────────

def sget(state: PipelineState, key: str, default=None):
    """Shared helper to read values from dict-like/object-like PipelineState."""
    if hasattr(state, "get"):
        value = state.get(key, default)
    else:
        value = getattr(state, key, default)
    return default if value is None else value


def make_sget(state: PipelineState):
    """Curried sget — 노드 함수 상단에서 ``sget = make_sget(state)`` 로 사용."""
    def _sget(key: str, default=None):
        return sget(state, key, default)
    return _sget
