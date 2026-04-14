"""
보조(비분석) 파이프라인
이전에는 `pipeline/graph.py`에 정의되어 있었습니다. 
이제 이 위치에 배치하여 `pipeline/facade.py`가 `pipeline/graph.py`를 임포트하지 않도록 하고 (잠재적인 임포트 순환을 방지하면서) 외부 API의 안정성을 유지할 수 있도록 했습니다.
"""

from __future__ import annotations

from langgraph.graph import StateGraph, START, END

from pipeline.core.state import PipelineState
from pipeline.domain.chat.chat_revision import chat_revision_node
from pipeline.domain.chat.idea_chat import idea_chat_node


class _PipelineRegistry:
    _cache: dict[str, object] = {}

    @classmethod
    def get_or_build(cls, key: str, builder_fn):
        if key not in cls._cache:
            cls._cache[key] = builder_fn()
        return cls._cache[key]


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

