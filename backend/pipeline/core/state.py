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


# ── 기본 상태 (모든 모드 공통) ───────────────────

class _BaseState(TypedDict):
    api_key: str
    model: str
    run_id: str
    error: str
    thinking_log: Annotated[list, _merge_thinking_logs]
    current_step: Annotated[str, _keep_last_step]


# ── 분석 모드 필드 ──────────────────────────────

class _AnalysisFields(TypedDict, total=False):
    input_idea: str                  # 사용자 아이디어 텍스트
    project_context: str             # 기존 프로젝트 컨텍스트 (폴더/GitHub)
    source_dir: str                  # AST 스캔 대상 소스코드 폴더 경로
    action_type: str                 # CREATE / UPDATE / REVERSE_ENGINEER / Needs_Clarification
    raw_requirements: list           # [{"id": "REQ-001", ...}]
    prioritized_requirements: list   # raw_requirements + priority, rationale
    rtm_matrix: list                 # [DEPRECATED] requirements_rtm 사용 권장
    requirements_rtm: list           # 최종 RTM (모든 필드 포함)
    semantic_graph: dict             # {"nodes": [...], "edges": [...]}
    context_spec: dict               # {"summary": "...", "key_decisions": [...], ...}
    metadata: dict                   # {"project_name": "...", "action_type": "...", ...}
    clarification_questions: list    # Needs_Clarification 시 질문 목록
    project_state_path: str          # PROJECT_STATE.md 저장 경로
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


# ── 통합 상태 (하위 호환) ───────────────────────

class PipelineState(_BaseState, _AnalysisFields, _ChatFields, _IdeaFields, total=False):
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
