"""
Stack Planner — global_stacks(gs) vs 실제 의존성 증거 대조 유닛 테스트 (LLM 호출 없음).

AGENTS.md 5.2 작업 항목 5("PM/SA 결과가 입력 증거에 실제로 존재하는지 검증"),
완료 기준("실제 의존성에 없는 패키지는 REVERSE_ENGINEER 결과에서 제거됨")에 대응한다.

실행:
    cd backend
    python -m pytest pipeline/domain/pm/test/unit/test_stack_planner_evidence_check.py -v
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../.."))

from pipeline.domain.pm.nodes.stack_planner import (  # noqa: E402
    _filter_global_stacks_against_evidence,
)
from pipeline.domain.pm.schemas import GlobalStack  # noqa: E402


def _gs(name: str) -> GlobalStack:
    return GlobalStack(name=name, version="", domain="Frontend", evidence="package.json")


def test_hallucinated_package_not_in_evidence_is_dropped():
    """의존성 증거에 없는 패키지(할루시네이션 또는 인젝션 결과)는 결과에서 제거돼야 한다."""
    global_stacks = [_gs("react"), _gs("evil-injected-backdoor-pkg")]
    evidence = [{"name": "react", "version": "18.3.1", "source": "package.json"}]

    result = _filter_global_stacks_against_evidence(global_stacks, evidence)

    names = {item.name for item in result}
    assert names == {"react"}


def test_case_insensitive_match_is_preserved():
    """대소문자만 다른 경우는 정상 매핑으로 유지돼야 한다 (과도 차단 방지)."""
    global_stacks = [_gs("React")]
    evidence = [{"name": "react", "version": "18.3.1", "source": "package.json"}]

    result = _filter_global_stacks_against_evidence(global_stacks, evidence)

    assert [item.name for item in result] == ["React"]


def test_empty_evidence_does_not_filter_anything():
    """매니페스트 파일이 아예 없는 저장소(evidence=[])면 대조 근거가 없으므로 필터를 적용하지 않는다."""
    global_stacks = [_gs("react"), _gs("some-internal-only-lib")]

    result = _filter_global_stacks_against_evidence(global_stacks, [])

    assert len(result) == 2
