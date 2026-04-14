from __future__ import annotations

from pipeline.core.state import PipelineState, make_sget


def _scan_is_sufficient(system_scan: dict) -> bool:
    if not isinstance(system_scan, dict):
        return False
    status = (system_scan.get("status") or "").strip()
    if status == "Skipped":
        return False
    scanned_files = int(system_scan.get("scanned_files", 0) or 0)
    scanned_functions = int(system_scan.get("scanned_functions", 0) or 0)
    detected_frameworks = system_scan.get("detected_frameworks", []) or []
    return (scanned_files >= 3 and scanned_functions >= 10) or bool(detected_frameworks)


def _decide_mode(input_idea: str, system_scan: dict) -> tuple[str, str]:
    """Return (mode, reason). Mode is one of CREATE|UPDATE|REVERSE_ENGINEER."""
    idea = (input_idea or "").strip()
    has_scan = _scan_is_sufficient(system_scan)
    if not idea and has_scan:
        return "REVERSE_ENGINEER", "input_idea 비어있고 As-Is 스캔 증거가 충분하여 REVERSE_ENGINEER로 판정"
    if idea and has_scan:
        return "UPDATE", "input_idea 존재 + As-Is 스캔 증거가 충분하여 UPDATE로 판정"
    return "CREATE", "As-Is 스캔 증거가 부족하여 CREATE로 판정"


def sa_merge_project_node(state: PipelineState) -> dict:
    """
    Single decision point for mode + merge.

    - Decides mode (CREATE/UPDATE/REVERSE_ENGINEER)
    - Builds merged_project contract for SA phases
    - Persists final mode to metadata.action_type and state.action_type for downstream compatibility
    """
    sget = make_sget(state)

    input_idea = sget("input_idea", "") or ""
    project_context = sget("project_context", "") or ""
    system_scan = sget("system_scan", {}) or {}

    requirements_rtm = sget("requirements_rtm", []) or []
    semantic_graph = sget("semantic_graph", {}) or {}
    context_spec = sget("context_spec", {}) or {}

    mode, reason = _decide_mode(input_idea, system_scan)
    intent = "AS_IS" if mode == "REVERSE_ENGINEER" else "TO_BE"

    as_is = {
        "source": "system_scan",
        "scan": system_scan,
        "project_context": project_context,
    }
    plan = {
        "source": "pm_pipeline",
        "requirements_rtm": requirements_rtm,
        "semantic_graph": semantic_graph,
        "context_spec": context_spec,
    }

    merged_project = {
        "mode": mode,
        "intent": intent,
        "as_is": as_is if mode in {"UPDATE", "REVERSE_ENGINEER"} else {"status": "Skipped"},
        "plan": plan if mode in {"CREATE", "UPDATE"} else {"status": "Skipped", **plan},
    }

    merge_report = {
        "mode": mode,
        "mode_reason": reason,
        "merge_strategy": (
            "ASIS_ONLY" if mode == "REVERSE_ENGINEER"
            else "ASIS_FIRST_WITH_TOBE_AUGMENT" if mode == "UPDATE"
            else "TOBE_ONLY"
        ),
        "notes": [],
    }

    metadata = sget("metadata", {}) or {}
    next_metadata = {**metadata, "action_type": mode}

    return {
        "merged_project": merged_project,
        "merge_report": merge_report,
        "metadata": next_metadata,
        "action_type": mode,
        "thinking_log": (sget("thinking_log", []) or []) + [{
            "node": "sa_merge_project",
            "thinking": f"모드 판정: {mode}. {reason}",
        }],
        "current_step": "sa_merge_project_done",
    }

