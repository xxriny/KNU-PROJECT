from __future__ import annotations

from pipeline.core.node_base import NodeContext, pipeline_node


# @pipeline_node("develop_loop_controller")
# def develop_loop_controller_node(ctx: NodeContext) -> dict:
#     #loop_count = ctx.sget("develop_loop_count", 0)
#     loop_count = int(ctx.sget("develop_loop_count", 0) or 0)
#     merge_ready = bool((ctx.sget("branch_pr_result", {}) or {}).get("merge_ready"))
#     next_action = "complete" if merge_ready else ("retry_main" if loop_count < 1 else "complete_with_warnings")
#     return {
#         "develop_next_action": next_action,
#         "develop_loop_count": loop_count + 1,
#         "_thinking": "merge-state, loop-control, next-cycle",
#     }

@pipeline_node("develop_loop_controller")
def develop_loop_controller_node(ctx: NodeContext) -> dict:
    loop_count = int(ctx.sget("develop_loop_count", 0) or 0)
    merge_ready = bool((ctx.sget("branch_pr_result", {}) or {}).get("merge_ready"))

    integration = ctx.sget("integration_qa_result", {}) or {}
    branch = ctx.sget("branch_pr_result", {}) or {}
    completion = ctx.sget("dev_feature_completion", {}) or {}
    has_next_feature = bool(completion.get("has_next_feature"))
    completion_status = str(completion.get("status", "") or "").lower()

    blocked = (
        str(integration.get("status", "")).lower() in {"blocked", "failed", "error"}
        or str(branch.get("status", "")).lower() == "blocked"
        or completion_status == "blocked"
    )

    max_retries = int(ctx.sget("develop_max_retries", 1) or 1)

    if completion_status == "completed" and has_next_feature:
        next_action = "next_feature"
    elif merge_ready:
        next_action = "complete"
    elif blocked:
        next_action = "blocked"
    elif loop_count < max_retries:
        next_action = "retry_main"
    else:
        # 재시도 횟수 초과 시 명확하게 failed 처리 (complete_with_warnings 제거)
        next_action = "failed"

    return {
        "develop_next_action": next_action,
        "develop_loop_count": loop_count + 1,
        "_thinking": "merge-state, loop-control, next-cycle",
    }
