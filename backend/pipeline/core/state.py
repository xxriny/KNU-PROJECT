"""
PM Agent Pipeline — 공유 상태 정의 v9.0
LangGraph StateGraph에서 모든 노드가 읽고 쓰는 상태 스키마.

상태를 _BaseState / _AnalysisFields / _ChatFields / _IdeaFields 로 분리하고,
PipelineState 는 이들의 합집합(union)으로 유지하여 하위 호환성 보장.
"""

from typing import Any, TypedDict, Annotated
from pipeline.core.utils import make_sget


# ── 리듀서 함수 ─────────────────────────────────

def _merge_thinking_logs(existing_logs, new_logs):
    """여러 노드에서 동시에 thinking_log를 업데이트할 때 누적"""
    if not isinstance(existing_logs, list):
        existing_logs = []
    if not isinstance(new_logs, list):
        new_logs = []
    # Legacy nodes sometimes return the full prior log plus a new entry. The
    # reducer already receives the prior value, so concatenating blindly can
    # grow thinking_log exponentially during long-running flows.
    if existing_logs and new_logs[: len(existing_logs)] == existing_logs:
        merged = new_logs
    else:
        merged = existing_logs + new_logs
    return merged[-200:]


def _deep_merge_dict(a: dict, b: dict) -> dict:
    """dict b를 a에 깊게 병합 (dict 값만 재귀, 나머지는 b 우선)."""
    result = dict(a)
    for k, v in b.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge_dict(result[k], v)
        else:
            result[k] = v
    return result


def _merge_sa_arch_bundle(existing: dict, new_val: dict) -> dict:
    """병렬 SA 노드가 동시에 sa_arch_bundle을 수정할 때 data 섹션을 깊게 병합."""
    if not existing:
        return new_val or {}
    if not new_val:
        return existing
    return _deep_merge_dict(existing, new_val)


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
    session_id: str                  # source_dir 해시 기반 RAG 영속 키 (run_id와 별개)
    rag_index_status: dict           # {"has_index": bool, "chunk_count": int, "session_id": str}
    rag_warnings: list               # [{"code": "...", "message": "..."}] 사용자 알림 배너
    system_scan: dict                  # 기존 코드 구조 분석 결과
    sa_phase2: dict                  # 영향도 분석 결과
    sa_phase3: dict                  # 기술 타당성 결과
    sa_phase4: dict                  # 의존성 샌드박스 검증 결과
    sa_phase5: dict                  # 패턴 기반 아키텍처 매핑 결과
    sa_phase6: dict                  # 보안 경계 설계 결과
    sa_phase7: dict                  # 인터페이스/가드레일 설계 결과
    sa_phase8: dict                  # 위상 정렬 결과
    sa_output: dict                  # SA 최종 통합 산출물
    sa_arch_bundle: Annotated[dict, _merge_sa_arch_bundle]  # SA 최종 번들 (병렬 노드 병합 지원)
    sa_merge_project_output: dict    # merge_project 노드 전용 출력
    component_scheduler_output: dict # component_scheduler 노드 전용 출력
    api_data_modeler_output: dict    # [DEPRECATED] api_modeler_output, db_schema_architect_output 사용 권장
    api_modeler_output: dict         # api_modeler 노드 전용 출력 (APIs)
    db_schema_architect_output: dict # db_schema_architect 노드 전용 출력 (Tables)
    sa_analysis_output: dict         # sa_analysis 노드 전용 출력
    sa_advisor_output: dict          # sa_advisor 노드 수정 조언 출력
    sa_unified_modeler_output: dict  # sa_unified_modeler 노드 전용 출력
    sa_project_structure_output: dict  # sa_project_structure 노드 전용 출력
    merged_project: dict             # merge_project가 생성 단일 결합 입력
    merge_report: dict               # merge_project 판정/병합 리포트

    # ── 기술 스택 (PM Loop) 필드 ────────────────
    loop_count: int                  # 회귀 루프 횟수 추적
    sa_loop_count: int               # SA 설계 회귀 루프 횟수 추적
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
    suggested_mode: str               # create | update | reverse
    notes_to_add: list                # 채팅에서 추출된 메모(노트) 항목 목록
                                      # [{"text": "...", "section": "Idea Chat"}, ...]
                                      # LangGraph가 노드 반환 키를 스키마와 매칭하므로,
                                      # 이 필드를 명시해야 idea_chat_node의 출력이 보존된다.
    suggested_followups: list         # 매 응답마다 LLM이 제안하는 후속 질문 4개 (UI 칩으로 노출)


# ── RAG 파이프라인 필드 ──────────────────────────

class _RAGFields(TypedDict, total=False):
    rag_chunks: list                 # CodeChunk dict 목록 (code_chunker 산출물)
    rag_ingest_output: dict          # RAGIngestOutput dict (code_embedding 산출물)
    rag_query_input: str             # 코드 검색 쿼리 텍스트
    rag_query_result: list           # RAGQueryResult dict 목록 (code_retriever 산출물)


class _DevTrackingFields(TypedDict, total=False):
    """PR 기반 개발 추적/검증 파이프라인 상태."""

    trigger: str                     # GITHUB_PR_WEBHOOK 등 실행 트리거
    repository: dict                 # {"owner": "...", "repo": "..."}
    pull_request: dict               # PR 번호, 브랜치, base, head_sha, 설명
    actor: dict                      # GitHub actor 및 역할 정보
    pr_context: dict                 # dev_task_planner가 정규화한 PR 분석 컨텍스트
    code_inventory: dict             # code_inventory_builder의 AST 기반 인벤토리
    published_spec_snapshot: dict    # branch_created_at 이하의 published snapshot
    spec_outdated: bool              # 최신 published snapshot이 더 최신인지 여부
    latest_snapshot: dict            # 현재 최신 snapshot 메타데이터
    implementation_profile: dict     # reverse/forensic 분석 결과
    # author:xxrin
    # LLM primary/fallback 판단 근거를 graph 최종 state와 PM Report까지 보존한다.
    forensic_profiler_meta: dict
    gap_report: list                 # 설계 대비 구현 GAP 목록
    gap_analyzer_meta: dict
    has_high_gap: bool               # HIGH GAP 존재 여부
    intent_classification: list      # GAP별 의도/비의도/불확실 분류 결과
    intent_classifier_meta: dict
    llm_warnings: list
    milestone_status: dict           # 완료율, blocked 항목, 예상 완료일
    pm_report: dict                  # TaskApprovalPanel에 표시할 PM 판단 리포트
    approval_status: str             # PENDING/APPROVED/REJECTED/NEEDS_SA_REVIEW
    pr_comment: dict                 # PR 코멘트 생성 결과
    pr_status_check: dict            # GitHub commit status 업데이트 결과
    checkout: dict                   # branch_fetcher checkout 검증 결과
    dev_knowledge: dict              # Dev Tracking 지식 조회 결과
    dev_knowledge_context: str       # intent/SA/Agile 프롬프트에 주입할 지식 텍스트
    approval_task: dict              # task_coordinator가 생성한 PM 승인 태스크
    analysis_persistence: dict       # DevPrAnalysis/DevGapItem 저장 결과
    embedding_result: dict           # DevKnowledgeArtifact 저장 결과
    loop_decision: str               # NEXT_PR/COMPLETE/BLOCKED 등 루프 결정
    timeline: list                   # Dev Tracking 노드 실행 이력
    dev_tracking_next_action: str    # branch_fetcher/intent_classifier/complete 등
    dev_tracking_loop_count: int     # PR batch/재시도 루프 횟수
    # author:xxrin
    # Dev Tracking LLM 호출 비용/디버깅 제어용 노드별 opt-out 플래그.
    use_llm_forensic_profiler: bool
    use_llm_gap_analyzer: bool
    use_llm_intent_classifier: bool
    _shared_db: Any                  # graph 내부 DB 세션 전달용. 응답에 노출하지 않는다.


# ── 통합 상태 ────────────────────────────────────────────

class PipelineState(_BaseState, _AnalysisFields, _ChatFields, _IdeaFields, _RAGFields, _DevTrackingFields, total=False):
    """LangGraph 파이프라인 공유 상태 — 모든 모드의 합집합.

    개별 모드가 사용하는 필드는 _AnalysisFields, _ChatFields, _IdeaFields를 참조.
    """
    pass


# sget and make_sget moved to pipeline.core.utils
