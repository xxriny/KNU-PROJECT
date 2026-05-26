from __future__ import annotations

from typing import Any

from .utils import _as_dict


def _call_structured_for_intent(**kwargs):
    from pipeline.core.utils import call_structured

    return call_structured(**kwargs)


def _call_structured_for_forensic(**kwargs):
    from pipeline.core.utils import call_structured

    return call_structured(**kwargs)


def _call_structured_for_gap(**kwargs):
    from pipeline.core.utils import call_structured

    return call_structured(**kwargs)


def _llm_meta(
    mode: str,
    *,
    attempted: bool,
    fallback_used: bool,
    preliminary: bool,
    error: Exception | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = {
        "mode": mode,
        "llm_attempted": attempted,
        "fallback_used": fallback_used,
        "preliminary": preliminary,
        "llm_error_type": type(error).__name__ if error else "",
        "llm_error_message": str(error) if error else "",
        "raw_error": repr(error) if error else "",
    }
    if extra:
        meta.update(extra)
    return meta


def _extend_llm_warnings(
    state: dict[str, Any],
    *,
    node: str,
    message: str,
    error: Exception | None = None,
) -> list[dict[str, Any]]:
    warnings = [
        item
        for item in state.get("llm_warnings") or []
        if isinstance(item, dict)
    ]
    warnings.append(
        {
            "node": node,
            "message": message,
            "llm_error_type": type(error).__name__ if error else "",
            "llm_error_message": str(error) if error else "",
            "raw_error": repr(error) if error else "",
            "requires_pm_review": True,
        }
    )
    return warnings


def _dev_tracking_llm_enabled(state: dict[str, Any], flag_name: str) -> bool:
    # author:xxrin
    # 요청 api_key뿐 아니라 서버 GEMINI_API_KEY fallback까지 반영해야 실제 호출 가능 여부와 일치한다.
    try:
        from pipeline.core.utils import get_effective_key

        get_effective_key(str(state.get("api_key") or ""))
    except Exception:
        return False
    if flag_name in state and state.get(flag_name) is not None:
        return bool(state.get(flag_name))
    return True


def _inventory_file_set(state: dict[str, Any]) -> set[str]:
    inventory = _as_dict(state.get("code_inventory"))
    files = inventory.get("files", []) if isinstance(inventory.get("files"), list) else []
    return {
        str(item.get("file") or "")
        for item in files
        if isinstance(item, dict) and str(item.get("file") or "")
    }


def _validate_llm_implementation_profile(
    profile: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    # author:xxrin
    # 자동 오판 방지를 위해 LLM profiler가 실제 inventory 밖의 파일을 발명하지 못하게 막는다.
    known_files = _inventory_file_set(state)
    role_map = _as_dict(profile.get("file_role_map"))
    if known_files:
        unknown_role_files = sorted(path for path in role_map if path not in known_files)
        if unknown_role_files:
            raise ValueError(f"LLM profiler returned unknown file_role_map files: {unknown_role_files[:5]}")

    for field_name in ("detected_apis", "detected_components"):
        items = profile.get(field_name) or []
        if not isinstance(items, list):
            raise ValueError(f"LLM profiler returned non-list {field_name}")
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"LLM profiler returned invalid {field_name}[{index}]")
            name = str(item.get("name") or "").strip()
            file_path = str(item.get("file") or "").strip()
            if not name or not file_path:
                raise ValueError(f"LLM profiler returned {field_name}[{index}] without name/file")
            if known_files and file_path not in known_files:
                raise ValueError(f"LLM profiler returned unknown {field_name}[{index}].file: {file_path}")
    return profile


def _validate_llm_intent_classification(
    classifications: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    # author:xxrin
    # 자동 승인과 직접 연결되는 노드라 input GAP과 1:1 매칭 및 preliminary 승인 금지를 강제한다.
    known_gap_ids = {
        str(gap.get("gap_id") or "").strip()
        for gap in gaps
        if isinstance(gap, dict) and str(gap.get("gap_id") or "").strip()
    }
    preliminary_gap_ids = {
        str(gap.get("gap_id") or "").strip()
        for gap in gaps
        if isinstance(gap, dict) and gap.get("preliminary") and str(gap.get("gap_id") or "").strip()
    }
    seen: set[str] = set()
    for index, item in enumerate(classifications):
        if not isinstance(item, dict):
            raise ValueError(f"LLM intent classification {index} is not an object")
        gap_id = str(item.get("gap_id") or "").strip()
        if not gap_id:
            raise ValueError(f"LLM intent classification {index} has empty gap_id")
        if gap_id not in known_gap_ids:
            raise ValueError(f"LLM intent classifier returned unknown gap_id: {gap_id}")
        if gap_id in seen:
            raise ValueError(f"LLM intent classifier returned duplicate gap_id: {gap_id}")
        seen.add(gap_id)
        if not str(item.get("reason") or "").strip():
            raise ValueError(f"LLM intent classification {gap_id} has empty reason")
        confidence = item.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
            raise ValueError(f"LLM intent classification {gap_id} has invalid confidence")
        if gap_id in preliminary_gap_ids and item.get("recommended_action") == "APPROVE_AS_INTENTIONAL":
            raise ValueError(f"LLM intent classifier approved preliminary gap_id: {gap_id}")

    missing = sorted(known_gap_ids - seen)
    if missing:
        raise ValueError(f"LLM intent classifier missed gap_id(s): {missing}")
    return classifications
