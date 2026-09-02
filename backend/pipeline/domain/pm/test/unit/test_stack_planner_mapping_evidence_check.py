"""
Stack Planner — stack_mapping(m) vs 실제 의존성 증거 + 표준 라이브러리 대조 유닛 테스트.

AGENTS.md 5.2 작업 항목 5("PM/SA 결과가 입력 증거에 실제로 존재하는지 검증"),
완료 기준("실제 의존성에 없는 패키지는 REVERSE_ENGINEER 결과에서 제거됨")의
stack_mapping(m) 쪽을 다룬다. gs 필터(test_stack_planner_evidence_check.py)와
달리, RECOVERY_PROMPT가 "Internal Modules"(pathlib, ast, os 등)를 config 파일
근거 없이 쓰는 걸 명시적으로 허용하므로 표준 라이브러리는 예외로 인정한다.

실행:
    cd backend
    python -m pytest pipeline/domain/pm/test/unit/test_stack_planner_mapping_evidence_check.py -v
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../.."))

from pipeline.domain.pm.nodes.stack_planner import (  # noqa: E402
    _filter_stack_mapping_against_evidence,
)
from pipeline.domain.pm.schemas import StackMapping  # noqa: E402


def _mapping(f_id: str, pkg: str) -> StackMapping:
    return StackMapping(f_id=f_id, dom="Backend", pkg=pkg, ver="", reason="test", status="APPROVED")


EVIDENCE = [
    {"name": "fastapi", "version": "0.104.0", "source": "requirements.txt"},
    {"name": "pydantic", "version": "2.5.0", "source": "requirements.txt"},
]


def test_hallucinated_package_is_dropped():
    """의존성 증거에도, 표준 라이브러리에도 없는 패키지는 제거돼야 한다."""
    mapping = [_mapping("FEAT_001", "evil-injected-backdoor-pkg")]

    result = _filter_stack_mapping_against_evidence(mapping, EVIDENCE)

    assert result == []


def test_stdlib_reference_is_kept_without_manifest_evidence():
    """pathlib 같은 표준 라이브러리는 매니페스트에 없어도 정당하므로 유지돼야 한다."""
    mapping = [_mapping("FEAT_001", "pathlib")]

    result = _filter_stack_mapping_against_evidence(mapping, EVIDENCE)

    assert [item.pkg for item in result] == ["pathlib"]


def test_comma_separated_pkg_all_verified_is_kept():
    """쉼표로 나열된 여러 패키지가 전부 증거/표준 라이브러리면 유지된다."""
    mapping = [_mapping("FEAT_001", "FastAPI, pydantic, os")]

    result = _filter_stack_mapping_against_evidence(mapping, EVIDENCE)

    assert len(result) == 1


def test_comma_separated_pkg_partially_fake_is_dropped():
    """쉼표로 나열된 패키지 중 단 하나라도 근거가 없으면 항목 전체를 제거한다."""
    mapping = [_mapping("FEAT_001", "FastAPI, evil-injected-backdoor-pkg")]

    result = _filter_stack_mapping_against_evidence(mapping, EVIDENCE)

    assert result == []


def test_unknown_pkg_is_always_kept():
    """pkg='unknown'(스키마 기본값)은 특정 패키지를 주장하지 않으므로 항상 유지한다."""
    mapping = [_mapping("FEAT_001", "unknown")]

    result = _filter_stack_mapping_against_evidence(mapping, EVIDENCE)

    assert len(result) == 1


def test_empty_evidence_does_not_filter_anything():
    """매니페스트 파일이 없는 저장소(evidence=[])면 대조 근거가 없으므로 필터를 적용하지 않는다."""
    mapping = [_mapping("FEAT_001", "some-random-lib")]

    result = _filter_stack_mapping_against_evidence(mapping, [])

    assert len(result) == 1
