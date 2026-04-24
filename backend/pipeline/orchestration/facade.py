"""
Pipeline facade.

목표: 내부 그래프를 도메인 패키지(pm/sa/analysis/shared)로 리팩토링하는 동안 외부 임포트를 안정적으로 유지합니다.
"""

from __future__ import annotations

from pipeline.orchestration.graph import (
    get_analysis_pipeline,
    get_pipeline_routing_map,
    get_pm_pipeline,
    get_sa_pipeline,
    get_scan_pipeline,
    get_pm_routing_map,
    get_sa_routing_map,
    get_scan_routing_map,
)
from pipeline.orchestration.aux_graphs import (
    get_idea_pipeline,
    get_idea_chat_routing_map,
)
from pipeline.orchestration.rag_graph import (
    get_rag_ingest_pipeline,
    get_rag_query_pipeline,
    get_rag_routing_map,
)

__all__ = [
    "get_analysis_pipeline",
    "get_pipeline_routing_map",
    "get_pm_pipeline",
    "get_sa_pipeline",
    "get_scan_pipeline",
    "get_pm_routing_map",
    "get_sa_routing_map",
    "get_scan_routing_map",
    "get_idea_pipeline",
    "get_idea_chat_routing_map",
    "get_rag_ingest_pipeline",
    "get_rag_query_pipeline",
    "get_rag_routing_map",
]

