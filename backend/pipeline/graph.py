"""
PM Agent Pipeline — LangGraph 파이프라인 빌더 v10.0 (완전체)
- 모드별(CREATE/UPDATE/REVERSE) 완벽한 노드 순서 재배치
- 에러 및 정보 부족 시 즉시 종료되는 방어선(Defense Line) 적용
"""

from langgraph.graph import StateGraph, START, END
from pipeline.action_type import normalize_action_type
from pipeline.state import PipelineState
from pipeline.nodes.pm_phase1 import atomizer_node
from pipeline.nodes.pm_phase2 import prioritizer_node
from pipeline.nodes.pm_phase3 import rtm_builder_node
from pipeline.nodes.pm_phase4 import semantic_indexer_node
from pipeline.nodes.pm_phase5 import context_spec_node
from pipeline.nodes.chat_revision import chat_revision_node
from pipeline.nodes.idea_chat import idea_chat_node
from pipeline.nodes.sa_phase1 import sa_phase1_node
from pipeline.nodes.sa_phase2 import sa_phase2_node
from pipeline.nodes.sa_phase3 import sa_phase3_node
from pipeline.nodes.sa_phase4 import sa_phase4_node
from pipeline.nodes.sa_phase5 import sa_phase5_node
from pipeline.nodes.sa_phase6 import sa_phase6_node
from pipeline.nodes.sa_phase7 import sa_phase7_node
from pipeline.nodes.sa_phase8 import sa_phase8_node
from pipeline.nodes.sa_reverse_context import sa_reverse_context_node


class _PipelineRegistry:
    _cache: dict[str, object] = {}

    @classmethod
    def get_or_build(cls, key: str, builder_fn):
        if key not in cls._cache:
            cls._cache[key] = builder_fn()
        return cls._cache[key]

    @classmethod
    def clear(cls):
        cls._cache.clear()

"""
파이프라인 종료 정책 (Termination Policy)

[SA 단계 — 분석 단서]
- Fail: 타당성/부채 리스크는 기록하되 후속 구조 분석은 계속 진행
    (이유: SA4~SA8 산출물까지 확보해 대안 설계와 후속 판단 근거를 남김)
  
- Needs_Clarification: 정보 부족하지만 SA 내부 재분석으로 해결 가능 → 계속 진행
  (이유: SA4/5/6/7/8에서 추가 증거 수집 및 검증 담당, 판정 재평가 가능)
  
- Error: 시스템 오류 → 즉시 END

[PM 단계 — 입력 준비 단계]
- Needs_Clarification: 초기 입력(RTM) 또는 컨텍스트 불완전 → 즉시 END
  (이유: SA가 진행할 기초 정보 부족 → 사용자 개입 필요)
  
- Completed_with_errors: 부분 성공이지만 품질 의심 → 즉시 END
  (이유: SA 입력 신뢰도 낮음 → 정확도 보장 불가)
  
- Error: 시스템 오류 → 즉시 END

[비대칭성의 의도]
SA와 PM의 "Needs_Clarification"은 의미가 다릅니다:
- SA: "불확실한 정보" → SA 단계 반복으로 수정 가능 → 계속
- PM: "입력 준비 불완전" → 추가 입력 필요 → 중단
"""

# SA: Error만 즉시 중단, Fail은 후속 구조 분석을 계속 수행
SA_EARLY_TERMINATION_STATUSES = {"Error"}

# PM: Needs_Clarification/Error/부분 실패 = 입력/품질 문제 (사용자 개입 필요)
PM_INPUT_READINESS_FAILURE_STATUSES = {"Needs_Clarification", "Error", "Completed_with_errors"}


def _check_status(state: PipelineState) -> str:
    """노드 실행 후 상태를 검사하여 에러/정보 부족 시 파이프라인을 조기 종료하는 라우터"""
    if hasattr(state, "get"):
        if state.get("error"):
            return "error"
            
        # PM 단계 에러 체크
        metadata = state.get("metadata", {})
        if metadata.get("status") in PM_INPUT_READINESS_FAILURE_STATUSES:
            return "error"
            
        # SA 단계 에러 체크
        for phase in [f"sa_phase{i}" for i in range(1, 9)]:
            phase_data = state.get(phase)
            if isinstance(phase_data, dict):
                if phase_data.get("status") in SA_EARLY_TERMINATION_STATUSES:
                    return "error"
                    
    return "continue"


def _add_all_analysis_nodes(workflow: StateGraph):
    """분석 파이프라인에 사용될 모든 에이전트 노드 등록"""
    workflow.add_node("atomizer", atomizer_node)
    workflow.add_node("prioritizer", prioritizer_node)
    workflow.add_node("rtm_builder", rtm_builder_node)
    workflow.add_node("semantic_indexer", semantic_indexer_node)
    workflow.add_node("context_spec", context_spec_node)
    workflow.add_node("sa_phase1", sa_phase1_node)
    workflow.add_node("sa_phase2", sa_phase2_node)
    workflow.add_node("sa_phase3", sa_phase3_node)
    workflow.add_node("sa_phase4", sa_phase4_node)
    workflow.add_node("sa_phase5", sa_phase5_node)
    workflow.add_node("sa_phase6", sa_phase6_node)
    workflow.add_node("sa_phase7", sa_phase7_node)
    workflow.add_node("sa_phase8", sa_phase8_node)
    workflow.add_node("sa_reverse_context", sa_reverse_context_node)


def _wire_linear_pipeline(workflow: StateGraph, chain: tuple[str, ...]):
    """순차 파이프라인 배선: START→chain[0]→…→chain[-1]→END (조건부 에러 처리 포함)."""
    workflow.add_edge(START, chain[0])
    for src, dst in zip(chain[:-1], chain[1:]):
        workflow.add_conditional_edges(src, _check_status, {"continue": dst, "error": END})
    workflow.add_edge(chain[-1], END)


# ── 노드 실행 시퀀스 (Single Source of Truth) ──────────────
# 그래프 배선과 라우팅 맵이 모두 이 튜플에서 자동 도출된다.

_CREATE_CHAIN: tuple[str, ...] = (
    "atomizer", "prioritizer", "rtm_builder", "semantic_indexer", "context_spec",
    "sa_phase3", "sa_phase4", "sa_phase5", "sa_phase6", "sa_phase7", "sa_phase8",
    "sa_reverse_context",
)

_UPDATE_CHAIN: tuple[str, ...] = (
    "sa_phase1", "atomizer", "prioritizer", "rtm_builder", "semantic_indexer", "context_spec",
    "sa_phase2", "sa_phase3", "sa_phase4", "sa_phase5", "sa_phase6", "sa_phase7", "sa_phase8",
)

_REVERSE_CHAIN: tuple[str, ...] = (
    "sa_phase1",
    "sa_phase3", "sa_phase4", "sa_phase5", "sa_phase6", "sa_phase7", "sa_phase8",
)


def _chain_to_next_nodes(chain: tuple[str, ...]) -> dict[str, list[str]]:
    """노드 시퀀스에서 라우팅 next_nodes 맵을 자동 생성."""
    return {node: ([chain[i + 1]] if i + 1 < len(chain) else []) for i, node in enumerate(chain)}


def _build_analysis_pipeline(key: str, chain: tuple[str, ...]):
    def _build():
        workflow = StateGraph(PipelineState)
        _add_all_analysis_nodes(workflow)
        _wire_linear_pipeline(workflow, chain)
        return workflow.compile()
    return _PipelineRegistry.get_or_build(key, _build)


def _get_create_pipeline():
    return _build_analysis_pipeline("analysis_create", _CREATE_CHAIN)


def get_update_sa_pipeline():
    return _build_analysis_pipeline("analysis_update", _UPDATE_CHAIN)


def get_reverse_sa_pipeline():
    return _build_analysis_pipeline("analysis_reverse", _REVERSE_CHAIN)


# ---------------------------------------------------------
# 라우팅 및 보조 파이프라인
# ---------------------------------------------------------
def get_analysis_pipeline(action_type: str = "CREATE"):
    """action_type 기반 분석 파이프라인 선택"""
    normalized_action = normalize_action_type(action_type)
    if normalized_action == "REVERSE_ENGINEER":
        return get_reverse_sa_pipeline()
    if normalized_action == "UPDATE":
        return get_update_sa_pipeline()
    return _get_create_pipeline()


def get_revision_pipeline():
    """수정 파이프라인 (START -> chat_revision -> END)"""
    def _build():
        workflow = StateGraph(PipelineState)
        workflow.add_node("chat_revision", chat_revision_node)
        workflow.add_edge(START, "chat_revision")
        workflow.add_edge("chat_revision", END)
        return workflow.compile()

    return _PipelineRegistry.get_or_build("revision", _build)


def get_idea_pipeline():
    """아이디어 발전 파이프라인 (START -> idea_chat -> END)"""
    def _build():
        workflow = StateGraph(PipelineState)
        workflow.add_node("idea_chat", idea_chat_node)
        workflow.add_edge(START, "idea_chat")
        workflow.add_edge("idea_chat", END)
        return workflow.compile()

    return _PipelineRegistry.get_or_build("idea_chat", _build)

# ---------------------------------------------------------
# 라우팅 맵 — transport/orchestration에서 공유 (REQ-007)
# action_type -> {first_node, next_nodes, start_message}
# ---------------------------------------------------------

_PIPELINE_ROUTING_CONFIGS: dict[str, dict] = {
    "CREATE": {"chain": _CREATE_CHAIN, "start_message": "요구사항 원자화 시작..."},
    "UPDATE": {"chain": _UPDATE_CHAIN, "start_message": "기존 코드 구조 분석 후 변경 설계 시작..."},
    "REVERSE_ENGINEER": {"chain": _REVERSE_CHAIN, "start_message": "프로젝트 구조 심층 분석 시작..."},
}


def get_pipeline_routing_map(action_type: str = "CREATE") -> dict:
    """action_type에 따른 파이프라인 라우팅 맵 반환.

    Returns:
        {"first_node": str, "next_nodes": dict[str, list[str]], "start_message": str}
    """
    normalized = normalize_action_type(action_type)
    config = _PIPELINE_ROUTING_CONFIGS.get(normalized, _PIPELINE_ROUTING_CONFIGS["CREATE"])
    chain = config["chain"]
    return {
        "first_node": chain[0],
        "next_nodes": _chain_to_next_nodes(chain),
        "start_message": config["start_message"],
    }


def get_revision_routing_map() -> dict:
    return {
        "first_node": "chat_revision",
        "next_nodes": {"chat_revision": []},
        "start_message": "수정 요청 처리 중...",
    }


def get_idea_chat_routing_map() -> dict:
    return {
        "first_node": "idea_chat",
        "next_nodes": {"idea_chat": []},
        "start_message": "아이디어 탐색 중...",
    }
