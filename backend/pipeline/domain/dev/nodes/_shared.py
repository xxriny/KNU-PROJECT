from __future__ import annotations

import re
from typing import Any


def _previous_result(state_get) -> dict[str, Any]:
    return state_get("previous_result", {}) or {}


def get_requirements(state_get) -> list[dict[str, Any]]:
    previous = _previous_result(state_get)
    return (
        state_get("requirements_rtm", [])
        or previous.get("requirements_rtm", [])
        or previous.get("pm_bundle", {}).get("data", {}).get("rtm", [])
        or []
    )


def get_components(state_get) -> list[dict[str, Any]]:
    previous = _previous_result(state_get)
    return (
        state_get("components", [])
        or previous.get("components", [])
        or previous.get("component_scheduler_output", {}).get("components", [])
        or []
    )


def get_apis(state_get) -> list[dict[str, Any]]:
    previous = _previous_result(state_get)
    return previous.get("apis", []) or []


def get_tables(state_get) -> list[dict[str, Any]]:
    previous = _previous_result(state_get)
    return previous.get("tables", []) or []


def get_goal(state_get) -> str:
    return str(
        state_get("develop_goal", "")
        or state_get("development_request", "")
        or "Implement the next iteration safely"
    )


def slugify(value: str) -> str:
    lowered = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "").strip().lower())
    return lowered.strip("-") or "work-item"


def requirement_id(req: dict[str, Any], index: int) -> str:
    return str(req.get("REQ_ID") or req.get("feature_id") or req.get("id") or f"REQ_{index:03d}")


def requirement_desc(req: dict[str, Any]) -> str:
    return str(req.get("description") or req.get("desc") or "Unnamed requirement")


def component_name(component: dict[str, Any]) -> str:
    return str(
        component.get("component_name")
        or component.get("name")
        or component.get("nm")
        or "UnknownComponent"
    )


def component_rtms(component: dict[str, Any]) -> list[str]:
    raw = component.get("rtms") or component.get("rt") or []
    if isinstance(raw, list):
        return [str(item) for item in raw]
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    return []


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def requirement_index(requirements: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for idx, req in enumerate(requirements, start=1):
        indexed[requirement_id(req, idx)] = req
    return indexed


def requirement_ids_for_components(
    requirements: list[dict[str, Any]],
    components: list[dict[str, Any]],
    component_names: list[str],
) -> list[str]:
    known_ids = set(requirement_index(requirements).keys())
    requested = set(component_names)
    matched: list[str] = []
    for component in components:
        if component_name(component) not in requested:
            continue
        for req_id in component_rtms(component):
            if req_id in known_ids and req_id not in matched:
                matched.append(req_id)
    return matched


def fallback_requirement_ids(requirements: list[dict[str, Any]], limit: int = 8) -> list[str]:
    return [
        requirement_id(req, idx)
        for idx, req in enumerate(requirements[:limit], start=1)
    ]
