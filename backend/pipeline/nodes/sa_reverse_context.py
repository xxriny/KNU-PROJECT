from __future__ import annotations

from collections import Counter
import os

from pipeline.schemas import ReverseContextOutput
from pipeline.state import PipelineState


def _sget(state: PipelineState, key: str, default=None):
    if hasattr(state, "get"):
        value = state.get(key, default)
    else:
        value = getattr(state, key, default)
    return default if value is None else value


def _top_frameworks(sa_phase1: dict) -> list[str]:
    frameworks = list(dict.fromkeys(sa_phase1.get("detected_frameworks", []) or []))
    for item in sa_phase1.get("framework_evidence", []) or []:
        name = (item.get("framework") or "").strip()
        if name and name not in frameworks:
            frameworks.append(name)
    return frameworks[:6]


def _layer_distribution(mapped_requirements: list[dict]) -> Counter:
    counter: Counter = Counter()
    for item in mapped_requirements:
        layer = item.get("layer") or "Unknown"
        counter[layer] += 1
    return counter


def _top_low_confidence_modules(mapped_requirements: list[dict], limit: int = 3) -> list[dict]:
    ranked = sorted(
        [item for item in mapped_requirements if isinstance(item, dict)],
        key=lambda item: (item.get("layer_confidence", 0), item.get("name", "")),
    )
    return ranked[:limit]


def _module_name(item: dict) -> str:
    return item.get("name") or item.get("REQ_ID") or "unknown-module"


def sa_reverse_context_node(state: PipelineState) -> dict:
    metadata = _sget(state, "metadata", {}) or {}
    source_dir = (_sget(state, "source_dir", "") or "").strip()
    project_name = metadata.get("project_name") or (os.path.basename(source_dir.rstrip("\\/")) if source_dir else "프로젝트")
    sa_phase1 = _sget(state, "sa_phase1", {}) or {}
    sa_phase3 = _sget(state, "sa_phase3", {}) or {}
    sa_phase5 = _sget(state, "sa_phase5", {}) or {}
    sa_phase8 = _sget(state, "sa_phase8", {}) or {}

    scanned_files = int(sa_phase1.get("scanned_files", 0) or 0)
    scanned_functions = int(sa_phase1.get("scanned_functions", 0) or 0)
    frameworks = _top_frameworks(sa_phase1)
    mapped_requirements = sa_phase5.get("mapped_requirements", []) or []
    layer_distribution = _layer_distribution(mapped_requirements)
    layer_summary = ", ".join(
        f"{layer} {count}개" for layer, count in layer_distribution.most_common(4)
    ) or "레이어 분류 근거가 부족합니다"

    topology_batches = sa_phase8.get("parallel_batches", []) or []
    first_batch = topology_batches[0] if topology_batches else []
    cycles = sa_phase8.get("cyclic_requirements", []) or []
    inferred_dependencies = sa_phase8.get("inferred_dependencies", []) or []
    low_confidence_modules = _top_low_confidence_modules(mapped_requirements)

    framework_text = ", ".join(frameworks) if frameworks else "프레임워크 증거가 제한적"
    cycle_text = (
        f"순환 의존성 {len(cycles)}건이 남아 있습니다"
        if cycles
        else "치명적 순환 의존성은 보이지 않습니다"
    )
    summary = (
        f"{project_name} 코드는 {scanned_files}개 파일과 {scanned_functions}개 함수를 기준으로 역분석되었습니다. "
        f"주요 실행 기술 신호는 {framework_text}이며, 현재 구조는 {layer_summary} 중심으로 해석됩니다. "
        f"위상 정렬 기준 {len(topology_batches)}개 병렬 배치로 나뉘며 {cycle_text}."
    )

    architecture_highlights = [
        f"아키텍처 패턴 추정: {sa_phase5.get('pattern') or 'Clean Architecture'}",
        f"레이어 분포: {layer_summary}",
    ]
    for item in sorted(mapped_requirements, key=lambda entry: entry.get("layer_confidence", 0), reverse=True)[:3]:
        architecture_highlights.append(
            f"대표 모듈 {_module_name(item)} -> {item.get('layer') or 'Unknown'} ({item.get('layer_confidence', 0)}%)"
        )

    dependency_observations = [
        f"병렬 개발 배치: {len(topology_batches)}개",
    ]
    if first_batch:
        dependency_observations.append(f"선행 검증 후보: {', '.join(first_batch[:4])}")
    if inferred_dependencies:
        dependency_observations.append(f"계약/데이터흐름 기반 추론 의존성: {len(inferred_dependencies)}건")
    if cycles:
        dependency_observations.append(f"해소가 필요한 순환 의존성: {', '.join(cycles[:4])}")

    risk_factors: list[str] = []
    for warning in ((sa_phase3.get("evidence_summary") or {}).get("warnings") or [])[:3]:
        if warning not in risk_factors:
            risk_factors.append(warning)
    if cycles:
        risk_factors.append(f"위상 정렬 실패 원인인 순환 의존성 {len(cycles)}건이 존재합니다.")
    if low_confidence_modules:
        risk_factors.append(
            "레이어 신뢰도가 낮은 모듈이 남아 있습니다: "
            + ", ".join(f"{_module_name(item)}({item.get('layer_confidence', 0)}%)" for item in low_confidence_modules)
        )
    if not frameworks:
        risk_factors.append("프레임워크 증거가 제한적이어서 런타임 경계 확인이 더 필요합니다.")

    next_steps: list[str] = []
    if cycles:
        next_steps.append("순환 의존성 모듈부터 호출 방향과 책임 분리를 수동 검증하세요.")
    if low_confidence_modules:
        next_steps.append("레이어 신뢰도가 낮은 모듈의 실제 진입점과 데이터 흐름을 코드 레벨로 교차 확인하세요.")
    if inferred_dependencies:
        next_steps.append("추론 의존성 상위 항목을 API 계약 또는 함수 호출 근거와 대조해 확정하세요.")
    if not next_steps:
        next_steps.append("병렬 배치 1부터 실제 실행 경로와 주요 계약을 검증해 설계 기준선으로 고정하세요.")

    output = ReverseContextOutput(
        summary=summary,
        architecture_highlights=architecture_highlights,
        tech_stack_observations=frameworks,
        dependency_observations=dependency_observations,
        risk_factors=risk_factors,
        next_steps=next_steps,
    ).model_dump()

    return {
        "sa_reverse_context": output,
        "thinking_log": (_sget(state, "thinking_log", []) or []) + [{
            "node": "sa_reverse_context",
            "thinking": "역분석 전용 요약 컨텍스트 생성 완료",
        }],
        "current_step": "sa_reverse_context_done",
    }