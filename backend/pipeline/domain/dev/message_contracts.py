from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PIPELINE_NAME = "DEV_PIPELINE"
MAX_RETRY = 3
_DEV_TASK_CONSTRAINTS = [
    "Do not create unspecified endpoints",
    "Do not use unapproved packages",
    "Do not hardcode secrets",
]
_STATUS_FIELDS = [
    "uiux_domain_gate_result",
    "backend_domain_gate_result",
    "frontend_domain_gate_result",
    "global_fe_sync_result",
    "fullstack_runtime_verification",
    "integration_qa_result",
    "branch_pr_result",
    "embedding_result",
    "dev_fallback_result",
]


def is_dev_pipeline_node(node_name: str) -> bool:
    return node_name == "dev_task_planner" or node_name.startswith("develop_")


def attach_dev_contract_outputs(state: dict[str, Any], result: dict[str, Any], node_name: str) -> dict[str, Any]:
    if not is_dev_pipeline_node(node_name):
        return {}

    combined = {**state, **result}
    message = build_message_envelope(state=state, result=result, node_name=node_name)
    project_state = build_project_state_snapshot(combined, node_name=node_name)
    update = {
        "node": node_name,
        "feature_id": project_state["current_feature_id"],
        "last_gate_status": project_state["last_gate_status"],
        "rag_sync_status": project_state["rag_sync_status"],
        "next_action": project_state["next_action"],
        "timestamp": message["timestamp"],
    }
    write_result = write_project_state_markdown(combined, project_state)
    if write_result:
        update["project_state_path"] = write_result.get("path", "")
        if write_result.get("error"):
            update["error"] = write_result["error"]

    return {
        "dev_message_log": [message],
        "project_state": project_state,
        "project_state_updates": [update],
    }


def build_message_envelope(*, state: dict[str, Any], result: dict[str, Any], node_name: str) -> dict[str, Any]:
    feature_id = _feature_id({**state, **result})
    message_type = _message_type(node_name)
    payload = _message_payload(message_type=message_type, state=state, result=result, node_name=node_name)
    message = {
        "message_id": _message_id(state, node_name),
        "pipeline": PIPELINE_NAME,
        "feature_id": feature_id,
        "sender": _sender_name(node_name),
        "receiver": "DevPipelineState",
        "message_type": message_type,
        "retry_count": _retry_count(state, node_name),
        "max_retry": MAX_RETRY,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    }
    validate_dev_message(message)
    return message


def validate_dev_message(message: dict[str, Any]) -> None:
    required = {
        "message_id",
        "pipeline",
        "feature_id",
        "sender",
        "receiver",
        "message_type",
        "retry_count",
        "max_retry",
        "payload",
        "timestamp",
    }
    missing = sorted(key for key in required if key not in message)
    if missing:
        raise ValueError(f"INVALID_JSON_MESSAGE missing fields: {missing}")
    if message["pipeline"] != PIPELINE_NAME:
        raise ValueError("INVALID_JSON_MESSAGE pipeline must be DEV_PIPELINE")
    if not isinstance(message["payload"], dict):
        raise ValueError("INVALID_JSON_MESSAGE payload must be an object")

    message_type = str(message["message_type"])
    payload = message["payload"]
    payload_required = {
        "DEV_TASK": {"task_id", "domain", "instruction", "constraints"},
        "QA_RESULT": {"domain", "status"},
        "GATE_RESULT": {"gate", "status", "next_action"},
    }.get(message_type)
    if payload_required is None:
        raise ValueError(f"INVALID_JSON_MESSAGE unsupported message_type={message_type}")
    payload_missing = sorted(key for key in payload_required if key not in payload)
    if payload_missing:
        raise ValueError(f"INVALID_JSON_MESSAGE {message_type} payload missing fields: {payload_missing}")


def build_project_state_snapshot(state: dict[str, Any], *, node_name: str) -> dict[str, Any]:
    generated_files = _generated_files(state)
    completed_domains, failed_domains = _domain_statuses(state)
    return {
        "current_feature_id": _feature_id(state),
        "current_phase": "DEV_PIPELINE",
        "pipeline_status": _pipeline_status(state),
        "completed_domains": completed_domains,
        "failed_domains": failed_domains,
        "last_gate_status": _last_gate_status(state, node_name),
        "generated_files": generated_files,
        "rtm_coverage": _rtm_coverage(state),
        "rag_sync_status": _rag_sync_status(state),
        "next_action": _next_action(state, node_name),
        "failed_gate": _fallback_field(state, "failed_gate"),
        "required_action": _fallback_field(state, "required_action"),
        "blocked_reason": _fallback_field(state, "blocked_reason"),
        "retry_count": _retry_count(state, node_name),
        "max_retry": MAX_RETRY,
    }


def render_project_state_markdown(project_state: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# PROJECT_STATE",
            "",
            "```json",
            json.dumps(project_state, ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )


def write_project_state_markdown(state: dict[str, Any], project_state: dict[str, Any]) -> dict[str, str] | None:
    source_dir = state.get("source_dir")
    if not source_dir:
        return None
    path = Path(str(source_dir)) / "PROJECT_STATE.md"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_project_state_markdown(project_state), encoding="utf-8")
        return {"path": str(path)}
    except OSError as exc:
        return {"path": str(path), "error": f"PROJECT_STATE_UPDATE_FAILED: {exc}"}


def _feature_id(state: dict[str, Any]) -> str:
    direct = state.get("current_feature_id")
    if direct:
        return str(direct)
    feature = state.get("development_request_feature")
    if isinstance(feature, dict):
        for key in ("feature_id", "id"):
            if feature.get(key):
                return str(feature[key])
    queue = state.get("dev_feature_queue")
    if isinstance(queue, list) and queue:
        first = queue[0]
        if isinstance(first, dict):
            for key in ("feature_id", "id"):
                if first.get(key):
                    return str(first[key])
    rtm = state.get("requirements_rtm")
    if isinstance(rtm, list) and rtm:
        first = rtm[0]
        if isinstance(first, dict) and first.get("id"):
            return str(first["id"])
    return "FEATURE_UNKNOWN"


def _message_id(state: dict[str, Any], node_name: str) -> str:
    run_id = _safe_id(str(state.get("run_id") or "unknown"))
    sequence = len(state.get("dev_message_log") or []) + 1
    return f"msg_{run_id}_{_safe_id(node_name)}_{sequence:03d}"


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_") or "unknown"


def _sender_name(node_name: str) -> str:
    return "".join(part.capitalize() for part in node_name.split("_"))


def _message_type(node_name: str) -> str:
    if "qa_agent" in node_name:
        return "QA_RESULT"
    if "gate" in node_name or "verifier" in node_name or "blocker" in node_name or "fallback" in node_name:
        return "GATE_RESULT"
    return "DEV_TASK"


def _message_payload(
    *,
    message_type: str,
    state: dict[str, Any],
    result: dict[str, Any],
    node_name: str,
) -> dict[str, Any]:
    combined = {**state, **result}
    domain = _domain(node_name)
    status = _status_from_result(combined, node_name)
    result_keys = sorted(key for key in result.keys() if not key.startswith("_"))
    if message_type == "QA_RESULT":
        return {
            "domain": domain,
            "status": status.upper(),
            "error_type": _error_type(combined),
            "suggested_fix": _suggested_fix(combined),
            "node": node_name,
            "result_keys": result_keys,
        }
    if message_type == "GATE_RESULT":
        return {
            "gate": _sender_name(node_name),
            "status": status.upper(),
            "next_action": _next_action(combined, node_name),
            "node": node_name,
            "result_keys": result_keys,
        }
    return {
        "task_id": f"task_{_feature_id(combined)}_{_safe_id(node_name)}",
        "domain": domain,
        "instruction": f"Execute {node_name} for {_feature_id(combined)}.",
        "constraints": list(_DEV_TASK_CONSTRAINTS),
        "node": node_name,
        "status": status.upper(),
        "result_keys": result_keys,
    }


def _domain(node_name: str) -> str:
    if "uiux" in node_name:
        return "UIUX"
    if "backend" in node_name:
        return "Backend"
    if "frontend" in node_name:
        return "Frontend"
    if "integration" in node_name or "fullstack" in node_name:
        return "Integration"
    if "branch_pr" in node_name:
        return "BranchPR"
    if "embedding" in node_name:
        return "RAG"
    if "fallback" in node_name:
        return "Governance"
    return "Development"


def _status_from_result(state: dict[str, Any], node_name: str) -> str:
    for key in _candidate_status_fields(node_name):
        payload = state.get(key)
        if isinstance(payload, dict) and payload.get("status"):
            return str(payload["status"]).lower()
    if state.get("error"):
        return "failed"
    return "ready"


def _candidate_status_fields(node_name: str) -> list[str]:
    if "uiux_domain_gate" in node_name:
        return ["uiux_domain_gate_result"]
    if "backend_domain_gate" in node_name:
        return ["backend_domain_gate_result"]
    if "frontend_domain_gate" in node_name:
        return ["frontend_domain_gate_result"]
    if "global_fe_sync" in node_name:
        return ["global_fe_sync_result"]
    if "fullstack_runtime" in node_name:
        return ["fullstack_runtime_verification"]
    if "integration_qa" in node_name:
        return ["integration_qa_result"]
    if "branch_pr" in node_name:
        return ["branch_pr_result"]
    if "embedding" in node_name:
        return ["embedding_result"]
    if "fallback" in node_name:
        return ["dev_fallback_result"]
    if "uiux_qa_agent" in node_name:
        return ["uiux_qa_result"]
    if "backend_qa_agent" in node_name:
        return ["backend_qa_result"]
    if "frontend_qa_agent" in node_name:
        return ["frontend_qa_result"]
    if "backend_codegen_verifier" in node_name:
        return ["backend_codegen_verification", "backend_codegen_reverify_result"]
    if "frontend_codegen_verifier" in node_name:
        return ["frontend_codegen_verification", "frontend_codegen_reverify_result"]
    return list(_STATUS_FIELDS)


def _error_type(state: dict[str, Any]) -> str:
    for key in _STATUS_FIELDS:
        payload = state.get(key)
        if isinstance(payload, dict):
            if payload.get("error_type"):
                return str(payload["error_type"])
            if payload.get("failure_type"):
                return str(payload["failure_type"])
    return ""


def _suggested_fix(state: dict[str, Any]) -> str:
    for key in _STATUS_FIELDS:
        payload = state.get(key)
        if not isinstance(payload, dict):
            continue
        value = payload.get("suggested_fix") or payload.get("reason") or payload.get("message")
        if value:
            return str(value)
    return ""


def _domain_statuses(state: dict[str, Any]) -> tuple[list[str], list[str]]:
    completed = []
    failed = []
    mapping = {
        "UIUX": "uiux_domain_gate_result",
        "Backend": "backend_domain_gate_result",
        "Frontend": "frontend_domain_gate_result",
    }
    for domain, key in mapping.items():
        payload = state.get(key)
        if not isinstance(payload, dict):
            continue
        status = str(payload.get("status", "") or "").lower()
        if status in {"pass", "ready", "completed", "complete"}:
            completed.append(domain)
        elif status:
            failed.append(domain)
    return completed, failed


def _last_gate_status(state: dict[str, Any], node_name: str) -> str:
    for key in reversed(_STATUS_FIELDS):
        payload = state.get(key)
        if isinstance(payload, dict) and payload.get("status"):
            return f"{_label_for_status_key(key)}_{str(payload['status']).upper()}"
    return f"{_sender_name(node_name)}_READY"


def _label_for_status_key(key: str) -> str:
    return {
        "uiux_domain_gate_result": "UIUX_DOMAIN_GATE",
        "backend_domain_gate_result": "BACKEND_DOMAIN_GATE",
        "frontend_domain_gate_result": "FRONTEND_DOMAIN_GATE",
        "global_fe_sync_result": "GLOBAL_FE_SYNC",
        "fullstack_runtime_verification": "FULLSTACK_RUNTIME",
        "integration_qa_result": "INTEGRATION_QA",
        "branch_pr_result": "BRANCH_PR",
        "embedding_result": "RAG_SYNC",
        "dev_fallback_result": "FALLBACK",
    }[key]


def _generated_files(state: dict[str, Any]) -> list[str]:
    files: list[str] = []
    for key in ("backend_codegen_result", "frontend_codegen_result"):
        payload = state.get(key)
        if not isinstance(payload, dict):
            continue
        for field in ("generated_files", "changed_files", "files"):
            value = payload.get(field)
            if isinstance(value, list):
                files.extend(_path_from_file_item(item) for item in value)
        output_dir = payload.get("output_dir")
        if output_dir:
            files.append(str(output_dir))
    branch_pr = state.get("branch_pr_result")
    if isinstance(branch_pr, dict):
        for item in branch_pr.get("changed_files_manifest") or []:
            path = _path_from_file_item(item)
            if path:
                files.append(path)
    return sorted({item for item in files if item})


def _path_from_file_item(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in ("path", "file_path", "relative_path"):
            if item.get(key):
                return str(item[key])
    return ""


def _rtm_coverage(state: dict[str, Any]) -> str:
    rtm = state.get("requirements_rtm")
    if not isinstance(rtm, list) or not rtm:
        return "UNKNOWN"
    completion = state.get("dev_feature_completion")
    if isinstance(completion, dict) and completion.get("status") == "completed":
        return "100%"
    return "PENDING"


def _rag_sync_status(state: dict[str, Any]) -> str:
    fallback = state.get("dev_fallback_result")
    if isinstance(fallback, dict) and fallback.get("rag_update_blocked"):
        return "BLOCKED"
    result = state.get("embedding_result")
    if not isinstance(result, dict) or not result.get("status"):
        return "PENDING"
    status = str(result["status"]).lower()
    if status in {"persisted", "synced", "pass", "ready"}:
        return "SYNCED"
    if status == "partial":
        return "PARTIAL"
    return "FAILED"


def _next_action(state: dict[str, Any], node_name: str) -> str:
    fallback = state.get("dev_fallback_result")
    if isinstance(fallback, dict) and fallback.get("next_action"):
        return str(fallback["next_action"]).upper()
    explicit = state.get("develop_next_action")
    if explicit:
        return str(explicit).upper()
    branch = state.get("branch_pr_result")
    if isinstance(branch, dict) and branch.get("status") == "ready":
        return "RAG_UPDATE"
    embedding = state.get("embedding_result")
    if isinstance(embedding, dict) and embedding.get("status") in {"persisted", "partial"}:
        return "FEATURE_COMPLETION"
    if "integration_qa" in node_name:
        return "BRANCH_PR_ORCHESTRATOR"
    if "branch_pr" in node_name:
        return "RAG_UPDATE"
    return "CONTINUE"


def _pipeline_status(state: dict[str, Any]) -> str:
    fallback = state.get("dev_fallback_result")
    if isinstance(fallback, dict) and fallback.get("status"):
        return str(fallback["status"]).upper()
    completion = state.get("dev_feature_completion")
    if isinstance(completion, dict) and completion.get("status"):
        return str(completion["status"]).upper()
    return "IN_PROGRESS"


def _fallback_field(state: dict[str, Any], key: str) -> str:
    fallback = state.get("dev_fallback_result")
    if isinstance(fallback, dict) and fallback.get(key):
        return str(fallback[key])
    return ""


def _retry_count(state: dict[str, Any], node_name: str) -> int:
    if "uiux" in node_name:
        return int(state.get("uiux_retry_count", 0) or 0)
    if "backend" in node_name:
        return int(state.get("backend_retry_count", 0) or 0)
    if "frontend" in node_name:
        return int(state.get("frontend_retry_count", 0) or 0)
    if "integration" in node_name:
        return int(state.get("develop_integration_rework_count", 0) or 0)
    return int(state.get("total_retries", 0) or 0)
