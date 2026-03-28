"""
PM Agent Pipeline — 공유 상태 정의 v8.0
LangGraph StateGraph에서 모든 노드가 읽고 쓰는 상태 스키마.
분석/수정/아이디어 3가지 파이프라인이 공유한다.
"""

from typing import TypedDict, Annotated

# 병렬 노드의 thinking_log 누적 함수
def _merge_thinking_logs(existing_logs, new_logs):
    """여러 노드에서 동시에 thinking_log를 업데이트할 때 누적"""
    if not isinstance(existing_logs, list):
        existing_logs = []
    if not isinstance(new_logs, list):
        new_logs = []
    return existing_logs + new_logs

# 병렬 노드의 current_step 유지 함수 (마지막 값 유지)
def _keep_last_step(existing_step, new_step):
    """여러 노드에서 동시에 current_step을 업데이트할 때 마지막 값 유지"""
    if not new_step:
        return existing_step
    return new_step


class PipelineState(TypedDict):
    """LangGraph 파이프라인 공유 상태"""

    # ── 입력 ──────────────────────────────────
    input_idea: str                  # 사용자 아이디어 텍스트
    project_context: str             # 기존 프로젝트 컨텍스트 (폴더/GitHub)
    source_dir: str                  # AST 스캔 대상 소스코드 폴더 경로 (선택적, 빈 문자열이면 스캔 생략)
    model: str                       # Gemini 모델명
    api_key: str                     # Gemini API Key

    # ── 모드 감지 ─────────────────────────────
    action_type: str                 # CREATE / UPDATE / REVERSE_ENGINEER / Needs_Clarification

    # ── 노드 1: 요구사항 원자화 ───────────────
    raw_requirements: list           # [{"id": "REQ-001", "description": "...", "category": "..."}]

    # ── 노드 2: 비즈니스 우선순위 ─────────────
    prioritized_requirements: list   # raw_requirements + priority, rationale 추가

    # ── 노드 3: RTM 매트릭스 ──────────────────
    rtm_matrix: list                 # prioritized + depends_on 추가

    # ── 노드 4: 시맨틱 인덱싱 ─────────────────
    semantic_graph: dict             # {"nodes": [...], "edges": [...]}

    # ── 노드 5: 롤링 컨텍스트 명세서 ──────────
    context_spec: dict               # {"summary": "...", "key_decisions": [...], "open_questions": [...]}
    sa_reverse_context: dict         # REVERSE_ENGINEER 전용 경량 컨텍스트 요약

    # ── 최종 출력 ─────────────────────────────
    metadata: dict                   # {"project_name": "...", "action_type": "...", "status": "..."}
    requirements_rtm: list           # 최종 RTM (모든 필드 포함)
    clarification_questions: list    # Needs_Clarification 시 질문 목록

    # ── UI 연동 ────────────────────────
    thinking_log: Annotated[list, _merge_thinking_logs]  # [{"node": "atomizer", "thinking": "..."}] (병렬 누적)
    current_step: Annotated[str, _keep_last_step]  # 현재 실행 중인 노드명 (UI 진행 표시, 병렬 마지막값 유지)

    # ── 파이프라인 산출물 경로 ─────────────
    project_state_path: str          # PROJECT_STATE.md 저장 경로 (빈 문자열이면 미저장)
    run_id: str                      # 세션 타임스탬프 (YYYYMMDD_HHMMSS, ChromaDB 메타데이터용)
    error: str                       # 에러 메시지

    # ── 채팅 수정 모드 (chat_revision) ────
    user_request: str                # 사용자 수정 요청 텍스트
    chat_history: list               # [{"role": "user"|"assistant", "content": str}]
    agent_reply: str                 # 에이전트 응답 메시지
    previous_result: dict            # 이전 파이프라인 결과 (수정 기반)

    # ── 아이디어 채팅 모드 (idea_chat) ────
    idea_ready: bool                 # 아이디어 준비 완료 여부
    idea_summary: str                # 분석용 아이디어 요약
    suggested_mode: str              # create | update | reverse

    # ── SA 8단계 모드 ─────────────────────
    sa_phase1: dict                  # 기존 코드 구조 분석 결과
    sa_phase2: dict                  # 영향도 분석 결과
    sa_phase3: dict                  # 기술 타당성 결과
    sa_phase4: dict                  # 의존성 샌드박스 검증 결과
    sa_phase5: dict                  # 패턴 기반 아키텍처 매핑 결과
    sa_phase6: dict                  # 보안 경계 설계 결과
    sa_phase7: dict                  # 인터페이스/가드레일 설계 결과
    sa_phase8: dict                  # 위상 정렬 결과
    sa_output: dict                  # SA 최종 통합 산출물