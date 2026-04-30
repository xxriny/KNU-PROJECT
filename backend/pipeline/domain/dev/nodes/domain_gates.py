from __future__ import annotations

from pipeline.core.node_base import NodeContext, pipeline_node


def _gate_payload(domain: str, qa_result: dict, retries: int) -> dict:
    fixes_required = [str(item) for item in (qa_result.get("fixes_required") or []) if str(item).strip()]
    findings = [str(item) for item in (qa_result.get("findings") or []) if str(item).strip()]
    status = (qa_result.get("status") or "").lower()

    if status == "rework" and retries < 1:
        return {
            "status": "rework",
            "domain": domain,
            "reason": "Domain QA requested one rework cycle.",
            "blocking_findings": fixes_required or findings,
        }
    if status == "rework":
        return {
            "status": "blocked",
            "domain": domain,
            "reason": "Domain QA still requires changes after the retry budget was exhausted.",
            "blocking_findings": fixes_required or findings,
        }
    return {
        "status": "pass",
        "domain": domain,
        "reason": "Domain QA passed.",
        "blocking_findings": [],
    }


@pipeline_node("develop_uiux_domain_gate")
def develop_uiux_domain_gate_node(ctx: NodeContext) -> dict:
    retries = ctx.sget("uiux_retry_count", 0)
    return {
        "uiux_domain_gate_result": _gate_payload("uiux", ctx.sget("uiux_qa_result", {}) or {}, retries),
        "uiux_retry_count": retries + 1,
        "_thinking": "uiux-domain-gate",
    }


@pipeline_node("develop_backend_domain_gate")
def develop_backend_domain_gate_node(ctx: NodeContext) -> dict:
    retries = ctx.sget("backend_retry_count", 0)
    return {
        "backend_domain_gate_result": _gate_payload("backend", ctx.sget("backend_qa_result", {}) or {}, retries),
        "backend_retry_count": retries + 1,
        "_thinking": "backend-domain-gate",
    }


@pipeline_node("develop_frontend_domain_gate")
def develop_frontend_domain_gate_node(ctx: NodeContext) -> dict:
    retries = ctx.sget("frontend_retry_count", 0)
    return {
        "frontend_domain_gate_result": _gate_payload("frontend", ctx.sget("frontend_qa_result", {}) or {}, retries),
        "frontend_retry_count": retries + 1,
        "_thinking": "frontend-domain-gate",
    }
