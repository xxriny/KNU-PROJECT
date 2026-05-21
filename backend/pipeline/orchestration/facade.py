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
    get_pm_routing_map,
    get_sa_routing_map,
)
from pipeline.orchestration.aux_graphs import (
    get_idea_pipeline,
    get_idea_chat_routing_map,
)
from pipeline.orchestration.dev_tracking_graphs import (
    get_dev_tracking_pipeline,
    get_dev_tracking_routing_map,
)
# author: xxrin
# 호출부가 안정적인 facade import 경로를 사용하도록 Dev Tracking getter를 재노출합니다.
__all__ = [
    "get_analysis_pipeline",
    "get_pipeline_routing_map",
    "get_pm_pipeline",
    "get_sa_pipeline",
    "get_pm_routing_map",
    "get_sa_routing_map",
    "get_idea_pipeline",
    "get_idea_chat_routing_map",
    "get_dev_tracking_pipeline",
    "get_dev_tracking_routing_map",
]

