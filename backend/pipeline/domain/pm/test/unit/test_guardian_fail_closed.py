"""
Guardian — llm_semantic_check() 예외 시 fail-open 회귀 테스트 (LLM 호출 없음).

배경: llm_semantic_check()가 예외를 잡아 (True, "...스킵") 즉 무조건 승인을
반환하고 있었다. compress_prompt 버그(별도 커밋에서 수정)로 매번 예외가 나서
사실상 검증이 한 번도 작동한 적이 없었는데, 그 버그가 없어져도 진짜 API
오류(타임아웃, 요금 한도 등)가 나면 여전히 이 fail-open 경로를 탄다.
AGENTS.md 11장 Fail-closed 원칙 위반.

네트워크/LLM 호출 없이 call_structured_with_usage를 monkeypatch로 강제 실패시켜
검증한다.

실행:
    cd backend
    python -m pytest pipeline/domain/pm/test/unit/test_guardian_fail_closed.py -v
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../.."))

from pipeline.domain.pm.nodes import guardian as guardian_module  # noqa: E402
from pipeline.domain.pm.schemas import StackSourceData  # noqa: E402


def _fake_data() -> StackSourceData:
    return StackSourceData(
        name="zustand",
        description="Bear necessities for state management",
        version="5.0.0",
        license="MIT",
        last_updated="2026-04-14T00:00:00Z",
        stars=45000,
        source_type="npm",
        url="https://www.npmjs.com/package/zustand",
    )


def test_semantic_check_exception_fails_closed(monkeypatch):
    """LLM 호출이 예외를 던지면 승인(True)이 아니라 거절(False)로 처리돼야 한다."""

    def raise_error(**kwargs):
        raise RuntimeError("simulated transient API failure")

    monkeypatch.setattr(guardian_module, "call_structured_with_usage", raise_error)

    is_legit, reason = guardian_module.llm_semantic_check(
        api_key="dummy",
        model="dummy-model",
        data=_fake_data(),
        inventory={},
    )

    assert is_legit is False, (
        f"semantic check 예외가 여전히 승인(fail-open)으로 처리됨: is_legit={is_legit}, reason={reason}"
    )


def test_guardian_node_rejects_when_semantic_check_errors(monkeypatch):
    """guardian_node 전체 흐름에서도 semantic check 예외 시 최종 status가 REJECTED여야 한다."""

    def raise_error(**kwargs):
        raise RuntimeError("simulated transient API failure")

    monkeypatch.setattr(guardian_module, "call_structured_with_usage", raise_error)

    state = {
        "api_key": "dummy",
        "stack_crawler_output": {
            "status": "Pass",
            "results": [
                {
                    "name": "zustand",
                    "description": "Bear necessities for state management",
                    "version": "5.0.0",
                    "license": "MIT",
                    "last_updated": "2026-04-14T00:00:00Z",
                    "stars": 45000,
                    "source_type": "npm",
                    "url": "https://www.npmjs.com/package/zustand",
                }
            ],
        },
    }

    result = guardian_module.guardian_node(state)
    output = result.get("guardian_output", {})

    assert output.get("status") != "APPROVED", (
        f"semantic check 시스템 오류가 guardian_node 최종 승인으로 이어짐: {output}"
    )
