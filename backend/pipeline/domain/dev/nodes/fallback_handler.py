from __future__ import annotations

from typing import Any

from pipeline.core.node_base import NodeContext, pipeline_node


def _feature_id(ctx: NodeContext) -> str:
    current = ctx.sget("current_feature_id", "")
    if current:
        return str(current)
    feature = ctx.sget("development_request_feature", {}) or {}
    if isinstance(feature, dict):
        return str(feature.get("feature_id") or feature.get("id") or "FEATURE_UNKNOWN")
    rtm = ctx.sget("requirements_rtm", []) or []
    if isinstance(rtm, list) and rtm and isinstance(rtm[0], dict):
        return str(rtm[0].get("id") or "FEATURE_UNKNOWN")
    return "FEATURE_UNKNOWN"


def _status(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("status", "") or "").lower()


def _findings(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    values = []
    for key in ("findings", "blocking_findings", "errors"):
        raw = payload.get(key) or []
        if isinstance(raw, list):
            values.extend(str(item) for item in raw if str(item).strip())
    reason = payload.get("reason") or payload.get("message")
    if reason:
        values.append(str(reason))
    return list(dict.fromkeys(values))


def _failed_gate(ctx: NodeContext) -> tuple[str, dict]:
    candidates = [
        ("BranchPROrchestrator", ctx.sget("branch_pr_result", {}) or {}),
        ("IntegrationQAGate", ctx.sget("integration_qa_result", {}) or {}),
        ("GlobalFESyncGate", ctx.sget("global_fe_sync_result", {}) or {}),
        ("FrontendDomainGate", ctx.sget("frontend_domain_gate_result", {}) or {}),
        ("BackendDomainGate", ctx.sget("backend_domain_gate_result", {}) or {}),
        ("UIUXDomainGate", ctx.sget("uiux_domain_gate_result", {}) or {}),
        ("FrontendCodegenVerifier", ctx.sget("frontend_codegen_verification", {}) or {}),
        ("BackendCodegenVerifier", ctx.sget("backend_codegen_verification", {}) or {}),
    ]
    for name, payload in candidates:
        if _status(payload) in {"blocked", "failed", "error", "rework", "rework_uiux", "rework_backend", "rework_frontend"}:
            return name, payload
    completion = ctx.sget("dev_feature_completion", {}) or {}
    if _status(completion) == "blocked":
        return "FeatureCompletion", completion
    return "DevPipeline", {"status": "blocked", "reason": "Pipeline ended through fallback without a specific failed gate."}


def _rework_targets(ctx: NodeContext, failed_payload: dict) -> list[str]:
    targets = failed_payload.get("rework_targets") if isinstance(failed_payload, dict) else []
    if isinstance(targets, list) and targets:
        return [str(item).lower() for item in targets if str(item).strip()]
    failed_text = " ".join(_findings(failed_payload)).lower()
    inferred = []
    for domain in ("uiux", "backend", "frontend"):
        if domain in failed_text:
            inferred.append(domain)
    if inferred:
        return inferred
    selected = (ctx.sget("develop_main_plan", {}) or {}).get("selected_domains") or []
    if isinstance(selected, list) and selected:
        return [str(item).lower() for item in selected]
    return ["sa"]


def _required_action(failed_gate: str, findings: list[str], retry_count: int, max_retry: int) -> str:
    text = " ".join(findings).lower()
    if retry_count >= max_retry:
        return "RETURN_TO_SA_REVIEW"
    if failed_gate in {"IntegrationQAGate", "BranchPROrchestrator"}:
        return "MANUAL_REVIEW_REQUIRED"
    if any(token in text for token in ("sa", "contract", "schema", "rtm", "missing_sa")):
        return "RETURN_TO_SA_REVIEW"
    return "RETURN_TO_DOMAIN_AGENT"


@pipeline_node("develop_fallback_handler")
def develop_fallback_handler_node(ctx: NodeContext) -> dict:
    failed_gate, failed_payload = _failed_gate(ctx)
    findings = _findings(failed_payload)
    if not findings:
        findings = ["Dev Pipeline fallback was triggered."]
    retry_count = max(
        int(ctx.sget("uiux_retry_count", 0) or 0),
        int(ctx.sget("backend_retry_count", 0) or 0),
        int(ctx.sget("frontend_retry_count", 0) or 0),
        int(ctx.sget("develop_integration_rework_count", 0) or 0),
        int(ctx.sget("develop_loop_count", 0) or 0),
    )
    max_retry = int(ctx.sget("develop_max_retries", 1) or 1)
    required_action = _required_action(failed_gate, findings, retry_count, max_retry)
    targets = _rework_targets(ctx, failed_payload)
    feature_id = _feature_id(ctx)

    fallback_result = {
        "feature_id": feature_id,
        "status": "blocked",
        "failed_gate": failed_gate,
        "blocked_reason": findings[0],
        "findings": findings,
        "rework_targets": targets,
        "required_action": required_action,
        "retry_count": retry_count,
        "max_retry": max_retry,
        "auto_pr_blocked": True,
        "rag_update_blocked": True,
        "next_action": required_action,
    }
    sa_review_request = {
        "feature_id": feature_id,
        "source": "DEV_PIPELINE",
        "status": "OPEN" if required_action == "RETURN_TO_SA_REVIEW" else "NOT_REQUIRED",
        "failed_gate": failed_gate,
        "reason": findings[0],
        "evidence": findings,
        "requested_domains": targets,
        "retry_count": retry_count,
        "max_retry": max_retry,
    }

    return {
        "dev_fallback_result": fallback_result,
        "sa_review_request": sa_review_request,
        "develop_next_action": "fallback",
        "_thinking": "fallback, sa-review, stop-pr-rag",
    }
