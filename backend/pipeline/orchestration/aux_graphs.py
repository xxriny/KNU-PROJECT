"""
보조(비분석) 파이프라인.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from pipeline.core.state import PipelineState
from pipeline.domain.chat.idea_chat import idea_chat_node


class _PipelineRegistry:
    _cache: dict[str, object] = {}

    @classmethod
    def get_or_build(cls, key: str, builder_fn):
        if key not in cls._cache:
            cls._cache[key] = builder_fn()
        return cls._cache[key]


def get_idea_pipeline():
    """아이디어 발전 파이프라인 (START -> idea_chat -> END)"""

    def _build():
        workflow = StateGraph(PipelineState)
        workflow.add_node("idea_chat", idea_chat_node)
        workflow.add_edge(START, "idea_chat")
        workflow.add_edge("idea_chat", END)
        return workflow.compile()

    return _PipelineRegistry.get_or_build("idea_chat", _build)


def get_idea_chat_routing_map() -> dict:
    return {
        "first_node": "idea_chat",
        "next_nodes": {"idea_chat": []},
        "start_message": "아이디어 탐색 중...",
    }
