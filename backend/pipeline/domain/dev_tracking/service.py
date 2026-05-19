from __future__ import annotations

from typing import Any

from . import nodes


# author:xxrin
# navi_v3 Dev Tracking MVP를 순서대로 실행하는 서비스 러너.
# 기존 graph builder와 분리해서 다른 팀이 작업한 PM/SA/Agile/RAG 노드를
# 새 PR 추적 흐름 때문에 직접 수정하지 않도록 한다.


def _merge(state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    state.update(result)
    return state


def run_dev_tracking_analysis(
    payload: dict[str, Any],
    *,
    shared_db: Any = None,
) -> dict[str, Any]:
    """navi_v3 PR 기반 Dev Tracking MVP 흐름을 실행한다.

    author:xxrin

    기존 PM/SA/Agile/RAG 노드를 직접 고치지 않기 위해 의도적으로 분리했다.
    이 함수는 공개 helper만 호출하고, 생성된 분석 결과를 반환 state와
    Agile 승인 태스크에 보관한다.
    """

    state = dict(payload)
    timeline: list[dict[str, Any]] = []

    def step(name: str, fn, *args):
        result = fn(state, *args)
        timeline.append(
            {
                "node": name,
                "status": result.get("status", ""),
                "next_action": result.get("dev_tracking_next_action", ""),
                "error_type": result.get("error_type", ""),
            }
        )
        _merge(state, result)
        return result

    blocking = {"blocked", "pm_approval_pending"}

    step("dev_task_planner", nodes.dev_task_planner)
    if state.get("dev_tracking_next_action") in blocking:
        return {"status": "error", "timeline": timeline, "data": state}

    step("branch_fetcher", nodes.branch_fetcher)
    if state.get("dev_tracking_next_action") in blocking:
        return {"status": "error", "timeline": timeline, "data": state}

    step("reverse_analyzer", nodes.reverse_analyzer)
    step("code_inventory_builder", nodes.code_inventory_builder)
    if state.get("dev_tracking_next_action") in blocking:
        return {"status": "error", "timeline": timeline, "data": state}

    step("forensic_profiler", nodes.forensic_profiler)
    step("spec_loader", nodes.spec_loader, shared_db)
    step("gap_analyzer", nodes.gap_analyzer)
    if state.get("dev_tracking_next_action") == "intent_classifier":
        step("intent_classifier", nodes.intent_classifier)
    else:
        state.setdefault("intent_classification", [])

    step("milestone_tracker", nodes.milestone_tracker)
    step("pm_report_generator", nodes.pm_report_generator)
    step("pr_comment_notifier", nodes.pr_comment_notifier)
    step("task_coordinator", nodes.task_coordinator)
    step("develop_embedding", nodes.develop_embedding)
    step("develop_loop_controller", nodes.develop_loop_controller)

    final_status = "pending_pm_approval"
    if state.get("approval_status") == "NO_GAP_DETECTED":
        final_status = "complete"
    return {
        "status": final_status,
        "timeline": timeline,
        "data": state,
    }
