import os
import sys

# 현재 파일 위치를 기준으로 프로젝트 루트(backend)를 검색 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from typing import Any, Dict
from pipeline.core.state import PipelineState

def run_isolated_node(node_fn, state: Dict[str, Any]) -> Dict[str, Any]:
    """
    하나의 노드 함수를 독립적으로 실행합니다.
    LangGraph의 StateGraph 없이도 노드 로직을 검증할 수 있게 합니다.
    """
    # PipelineState는 TypedDict이므로 일반 dict로 취급 가능
    return node_fn(state)
