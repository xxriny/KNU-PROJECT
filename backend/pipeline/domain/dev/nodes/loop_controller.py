from __future__ import annotations

from pipeline.core.node_base import NodeContext, pipeline_node


@pipeline_node("develop_loop_controller")
def develop_loop_controller_node(ctx: NodeContext) -> dict:
    loop_count = ctx.sget("develop_loop_count", 0)
    merge_ready = bool((ctx.sget("branch_pr_result", {}) or {}).get("merge_ready"))
    next_action = "complete" if merge_ready else ("retry_main" if loop_count < 1 else "complete_with_warnings")
    return {
        "develop_next_action": next_action,
        "develop_loop_count": loop_count + 1,
        "_thinking": "merge-state, loop-control, next-cycle",
    }
