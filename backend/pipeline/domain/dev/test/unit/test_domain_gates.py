from __future__ import annotations

from pipeline.domain.dev.test.fixtures import *


def test_domain_gate_blocks_after_retry_budget() -> None:
    # 1회차 재시도: 상태가 rework로 설정되고 카운트 증가 확인
    first = develop_backend_domain_gate_node(
        {
            "backend_qa_result": {
                "status": "rework",
                "findings": ["API contract missing"],
                "fixes_required": ["Add request schema"],
            },
            "backend_retry_count": 0,
        }
    )
    assert first["backend_domain_gate_result"]["status"] == "rework"
    assert first["backend_retry_count"] == 1
    # 2회차 재시도 (한계 도달 시): 더 이상 루프를 돌지 않고 blocked 처리
    second = develop_backend_domain_gate_node(
        {
            "backend_qa_result": {
                "status": "rework",
                "findings": ["API contract missing"],
                "fixes_required": ["Add request schema"],
            },
            "backend_retry_count": 1,
        }
    )
    assert second["backend_domain_gate_result"]["status"] == "blocked"
    assert second["backend_domain_gate_result"]["blocking_findings"] == ["Add request schema"]
