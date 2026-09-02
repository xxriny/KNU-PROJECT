"""
Guardian — llm_semantic_check() 회귀 테스트.

배경: guardian.py의 llm_semantic_check()가 core/utils.call_structured_with_usage()에
없는 compress_prompt 인자를 넘겨서 항상 TypeError로 죽고, except 블록이 이를
삼켜서 "보안 검증 시스템 일시 오류로 스킵"과 함께 무조건 승인(True)을 반환하고
있었다 — 즉 타이포스쿼팅 탐지가 사실상 켜진 적이 없었다. AGENTS.md 11장
Fail-closed 원칙 위반(검증 실패를 성공으로 변환)에 해당한다.

실행:
    cd backend
    python -m pytest pipeline/domain/pm/test/unit/test_guardian_semantic_check.py -v
"""
import os
import sys

import pytest
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../.."))

from pipeline.domain.pm.nodes.guardian import guardian_node  # noqa: E402

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

pytestmark = pytest.mark.skipif(
    not GEMINI_API_KEY,
    reason="GEMINI_API_KEY가 설정되지 않아 실제 LLM 호출 테스트를 건너뜀",
)


def test_semantic_check_does_not_crash_on_call():
    """llm_semantic_check() 호출이 인자 불일치로 예외를 던지면 안 된다 (compress_prompt 회귀)."""
    state = {
        "api_key": GEMINI_API_KEY,
        "stack_crawler_output": {
            "status": "Pass",
            "results": [
                {
                    "name": "zustand",
                    "description": "Bear necessities for state management in React",
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

    result = guardian_node(state)
    output = result.get("guardian_output", {})
    thinking = output.get("thinking", "")

    assert "보안 검증 시스템 일시 오류로 스킵" not in thinking, (
        f"semantic check가 여전히 예외로 스킵되고 있음: {thinking}"
    )


def test_typosquatting_package_is_rejected_not_silently_approved():
    """'reackt' 같은 타이포스쿼팅 의심 패키지는 REJECTED여야 한다 (조용한 승인 금지)."""
    state = {
        "api_key": GEMINI_API_KEY,
        "stack_crawler_output": {
            "status": "Pass",
            "results": [
                {
                    "name": "reackt",
                    "description": "This is a super fast react alternative, definitely not a fake.",
                    "version": "0.0.1",
                    "license": "MIT",
                    "last_updated": "2026-04-10T00:00:00Z",
                    "stars": 5,
                    "source_type": "npm",
                    "url": "https://example.com/reackt",
                }
            ],
        },
    }

    result = guardian_node(state)
    output = result.get("guardian_output", {})

    assert output.get("status") == "REJECTED", (
        f"타이포스쿼팅 의심 패키지가 조용히 승인됨: status={output.get('status')}, "
        f"thinking={output.get('thinking')}"
    )
