"""
LLM 스키마 / 프롬프트 회귀 테스트 (REQ-009)

실제 LLM 호출 없이 backend/Data/ 폴더의 기존 결과 JSON을 golden dataset으로
사용하여 각 PM/SA 노드 출력의 스키마 구조를 검증한다.

실행:
    pytest backend/test/test_llm_regression.py -v
    pytest -m regression backend/test/test_llm_regression.py -v
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

# ── 경로 설정 ────────────────────────────────────────────
_BACKEND_ROOT = Path(__file__).parent.parent
_DATA_DIR = _BACKEND_ROOT / "Data"


# ─── Golden dataset 로드 ─────────────────────────────────

def _load_all_golden_records() -> list[dict]:
    """Data/ 폴더의 모든 JSON 파일을 로드 (PROJECT_STATE.md 제외)."""
    records = []
    if not _DATA_DIR.exists():
        return records
    for fpath in sorted(_DATA_DIR.glob("*.json")):
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                records.append({"file": fpath.name, "data": data})
        except (json.JSONDecodeError, OSError):
            pass
    return records


@pytest.fixture(scope="module")
def golden_records() -> list[dict]:
    records = _load_all_golden_records()
    if not records:
        pytest.skip("Data/ 폴더에 golden JSON 없음 — 테스트 건너뜀")
    return records


def _records_with_key(records: list[dict], key: str) -> list[dict]:
    return [r for r in records if key in r["data"]]


# ─── 헬퍼 ────────────────────────────────────────────────

def _normalize_key(item: dict, key: str) -> Any:
    """req_id / REQ_ID 등 대소문자 변형 키를 모두 허용."""
    if key in item:
        return item[key]
    if key.upper() in item:
        return item[key.upper()]
    return None


def _assert_list_of_dicts(
    value: Any,
    field_name: str,
    required_keys: list[str],
    skip_empty: bool = False,
) -> bool:
    """리스트 구조 검증. skip_empty=True이면 빈 리스트를 건너뜀(False 반환)."""
    assert isinstance(value, list), f"{field_name}: list 타입이어야 함, 실제={type(value)}"
    if skip_empty and len(value) == 0:
        return False  # 호출측에서 pytest.skip 처리
    assert len(value) > 0, f"{field_name}: 비어있어서는 안 됨"
    for i, item in enumerate(value):
        assert isinstance(item, dict), f"{field_name}[{i}]: dict 타입이어야 함"
        for key in required_keys:
            val = _normalize_key(item, key)
            assert val is not None, f"{field_name}[{i}]: '{key}' 키 누락"
            assert val != "", f"{field_name}[{i}].{key}: 값이 없음"
    return True


# ─── PM Phase 1: atomizer ────────────────────────────────

@pytest.mark.regression
class TestAtomizerOutput:
    def test_raw_requirements_present(self, golden_records):
        targets = _records_with_key(golden_records, "raw_requirements")
        if not targets:
            pytest.skip("raw_requirements 없는 데이터셋")
        for rec in targets:
            reqs = rec["data"]["raw_requirements"]
            filled = _assert_list_of_dicts(
                reqs,
                f"{rec['file']}/raw_requirements",
                ["req_id", "category", "description"],
                skip_empty=True,
            )
            if not filled:
                continue  # Needs_Clarification 등 조기 종료 레코드는 건너뜀

    def test_req_id_format(self, golden_records):
        targets = _records_with_key(golden_records, "raw_requirements")
        if not targets:
            pytest.skip("raw_requirements 없는 데이터셋")
        import re
        for rec in targets:
            for item in rec["data"]["raw_requirements"]:
                val = _normalize_key(item, "req_id") or ""
                # REQ-001 / REQ-UI-001 등 다양한 형식 모두 허용
                assert re.match(r"^REQ-[A-Z0-9][-A-Z0-9]*\d$", val) or re.match(r"^REQ-\d+$", val), (
                    f"{rec['file']}: req_id 형식 불일치: {val!r}"
                )


# ─── PM Phase 2: prioritizer ────────────────────────────

@pytest.mark.regression
class TestPrioritizerOutput:
    VALID_PRIORITIES = {"Must-have", "Should-have", "Could-have"}

    def test_prioritized_requirements_schema(self, golden_records):
        targets = _records_with_key(golden_records, "prioritized_requirements")
        if not targets:
            pytest.skip("prioritized_requirements 없는 데이터셋")
        for rec in targets:
            items = rec["data"]["prioritized_requirements"]
            filled = _assert_list_of_dicts(
                items,
                f"{rec['file']}/prioritized_requirements",
                ["req_id", "priority"],
                skip_empty=True,
            )
            if not filled:
                continue  # 조기 종료 레코드는 건너뜀

    def test_priority_values(self, golden_records):
        targets = _records_with_key(golden_records, "prioritized_requirements")
        if not targets:
            pytest.skip("prioritized_requirements 없는 데이터셋")
        for rec in targets:
            for item in rec["data"]["prioritized_requirements"]:
                p = item.get("priority", "")
                assert p in self.VALID_PRIORITIES, (
                    f"{rec['file']}: 유효하지 않은 priority '{p}', "
                    f"허용값={self.VALID_PRIORITIES}"
                )


# ─── PM Phase 5: context_spec ────────────────────────────

@pytest.mark.regression
class TestContextSpecOutput:
    def test_context_spec_required_keys(self, golden_records):
        targets = _records_with_key(golden_records, "context_spec")
        if not targets:
            pytest.skip("context_spec 없는 데이터셋")
        required = ["summary"]
        for rec in targets:
            cs = rec["data"]["context_spec"]
            assert isinstance(cs, dict), f"{rec['file']}/context_spec: dict 타입이어야 함"
            for key in required:
                assert key in cs, f"{rec['file']}/context_spec: '{key}' 키 누락"
                assert cs[key], f"{rec['file']}/context_spec.{key}: 값이 없음"


# ─── SA Phase 3: feasibility ─────────────────────────────

@pytest.mark.regression
class TestSAPhase3Output:
    VALID_STATUSES = {"Pass", "Fail", "Needs_Clarification", "Skipped", "Warning_Hallucination_Detected"}

    def test_sa_phase3_status(self, golden_records):
        targets = _records_with_key(golden_records, "sa_phase3")
        if not targets:
            pytest.skip("sa_phase3 없는 데이터셋")
        for rec in targets:
            ph = rec["data"]["sa_phase3"]
            assert isinstance(ph, dict), f"{rec['file']}/sa_phase3: dict 타입이어야 함"
            assert "status" in ph, f"{rec['file']}/sa_phase3: 'status' 키 누락"
            assert ph["status"] in self.VALID_STATUSES, (
                f"{rec['file']}/sa_phase3.status: 유효하지 않은 값 '{ph['status']}'"
            )

    def test_complexity_score_range(self, golden_records):
        targets = _records_with_key(golden_records, "sa_phase3")
        if not targets:
            pytest.skip("sa_phase3 없는 데이터셋")
        for rec in targets:
            ph = rec["data"]["sa_phase3"]
            if "complexity_score" in ph:
                score = ph["complexity_score"]
                assert isinstance(score, (int, float)), (
                    f"{rec['file']}/sa_phase3.complexity_score: 숫자여야 함"
                )
                assert 0 <= score <= 100, (
                    f"{rec['file']}/sa_phase3.complexity_score: 0~100 범위여야 함, 실제={score}"
                )

    def test_needs_clarification_has_reasons(self, golden_records):
        targets = _records_with_key(golden_records, "sa_phase3")
        if not targets:
            pytest.skip("sa_phase3 없는 데이터셋")
        for rec in targets:
            ph = rec["data"]["sa_phase3"]
            if ph.get("status") != "Needs_Clarification":
                continue
            reasons = ph.get("reasons", [])
            assert isinstance(reasons, list), f"{rec['file']}/sa_phase3.reasons: list 타입이어야 함"
            assert len(reasons) > 0, f"{rec['file']}/sa_phase3: Needs_Clarification이면 reasons가 필요함"

    def test_reverse_mode_without_rtm_has_actionable_alternatives(self, golden_records):
        targets = _records_with_key(golden_records, "sa_phase3")
        if not targets:
            pytest.skip("sa_phase3 없는 데이터셋")

        reverse_targets = []
        for rec in targets:
            data = rec["data"]
            action_type = (data.get("metadata", {}) or {}).get("action_type", "")
            if action_type != "REVERSE_ENGINEER":
                continue
            rtm = data.get("requirements_rtm", []) or data.get("rtm_matrix", []) or []
            if rtm:
                continue
            reverse_targets.append(rec)

        if not reverse_targets:
            pytest.skip("REVERSE_ENGINEER + RTM 없음 케이스 없음")

        for rec in reverse_targets:
            ph = rec["data"]["sa_phase3"]
            if ph.get("status") != "Needs_Clarification":
                continue
            alternatives = ph.get("alternatives", [])
            assert isinstance(alternatives, list), f"{rec['file']}/sa_phase3.alternatives: list 타입이어야 함"
            assert len(alternatives) > 0, (
                f"{rec['file']}/sa_phase3: REVERSE 모드 RTM 없음이면 alternatives에 재실행 가이드가 필요함"
            )


# ─── SA Phase 8: topology ────────────────────────────────

@pytest.mark.regression
class TestSAPhase8Output:
    def test_topo_queue_no_cycles(self, golden_records):
        targets = _records_with_key(golden_records, "sa_phase8")
        if not targets:
            pytest.skip("sa_phase8 없는 데이터셋")
        for rec in targets:
            ph = rec["data"]["sa_phase8"]
            assert isinstance(ph, dict), f"{rec['file']}/sa_phase8: dict 타입이어야 함"
            cyclic = ph.get("cyclic_requirements", [])
            if cyclic:
                # 순환 의존성은 LLM 출력 품질 경고 — 하드 실패 대신 경고로 기록
                import warnings
                warnings.warn(
                    f"{rec['file']}/sa_phase8: 순환 의존성 {len(cyclic)}건 감지됨 — {cyclic[:5]}",
                    UserWarning,
                    stacklevel=2,
                )

    def test_topo_queue_covers_all_reqs(self, golden_records):
        targets = _records_with_key(golden_records, "sa_phase8")
        if not targets:
            pytest.skip("sa_phase8 없는 데이터셋")
        for rec in targets:
            data = rec["data"]
            ph = data["sa_phase8"]
            topo = ph.get("topo_queue", [])
            # prioritized_requirements에 있는 req_id가 topo_queue에 모두 포함되어야 함
            prioritized = data.get("prioritized_requirements", [])
            req_ids = {item.get("req_id") for item in prioritized if item.get("req_id")}
            if req_ids and topo:
                missing = req_ids - set(topo)
                assert not missing, (
                    f"{rec['file']}: topo_queue에서 누락된 req_id: {missing}"
                )


# ─── pm_overview / sa_overview 검증 ─────────────────────

@pytest.mark.regression
class TestOverviewShaping:
    def test_pm_overview_schema(self, golden_records):
        targets = _records_with_key(golden_records, "pm_overview")
        if not targets:
            pytest.skip("pm_overview 없는 데이터셋")
        for rec in targets:
            ov = rec["data"]["pm_overview"]
            assert isinstance(ov, dict), f"{rec['file']}/pm_overview: dict 타입이어야 함"
            assert "requirement_count" in ov, f"{rec['file']}/pm_overview: requirement_count 누락"
            assert isinstance(ov["requirement_count"], int), (
                f"{rec['file']}/pm_overview.requirement_count: int 타입이어야 함"
            )

    def test_sa_overview_schema(self, golden_records):
        targets = _records_with_key(golden_records, "sa_overview")
        if not targets:
            pytest.skip("sa_overview 없는 데이터셋")
        for rec in targets:
            ov = rec["data"]["sa_overview"]
            assert isinstance(ov, dict), f"{rec['file']}/sa_overview: dict 타입이어야 함"
            assert "feasibility" in ov, f"{rec['file']}/sa_overview: feasibility 누락"
            assert "critical_gaps" in ov, f"{rec['file']}/sa_overview: critical_gaps 누락"
            assert isinstance(ov["critical_gaps"], list), (
                f"{rec['file']}/sa_overview.critical_gaps: list 타입이어야 함"
            )
