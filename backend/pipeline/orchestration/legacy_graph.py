"""
Compatibility wrapper.

All pipeline graph public APIs are now served via `pipeline.facade`.
This module remains to avoid breaking older imports.
"""

from __future__ import annotations

from pipeline.orchestration.facade import (
    get_analysis_pipeline,
    get_pipeline_routing_map,
    get_revision_pipeline,
    get_idea_pipeline,
    get_revision_routing_map,
    get_idea_chat_routing_map,
)

__all__ = [
    "get_analysis_pipeline",
    "get_pipeline_routing_map",
    "get_revision_pipeline",
    "get_idea_pipeline",
    "get_revision_routing_map",
    "get_idea_chat_routing_map",
]
