from __future__ import annotations

import json

import pytest

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.domain.dev.message_contracts import validate_dev_message


@pipeline_node("develop_backend_domain_gate")
def _sample_gate_node(ctx: NodeContext) -> dict:
    return {
        "backend_domain_gate_result": {
            "status": "pass",
            "reason": "fixture",
        },
        "_thinking": "fixture-gate-pass",
    }


def test_dev_node_outputs_message_envelope_and_project_state(tmp_path) -> None:
    result = _sample_gate_node(
        {
            "run_id": "run-contract",
            "source_dir": str(tmp_path),
            "current_feature_id": "FEAT_001",
            "requirements_rtm": [{"id": "FEAT_001"}],
            "backend_retry_count": 1,
        }
    )

    message = result["dev_message_log"][0]
    validate_dev_message(message)
    assert message["pipeline"] == "DEV_PIPELINE"
    assert message["feature_id"] == "FEAT_001"
    assert message["sender"] == "DevelopBackendDomainGate"
    assert message["receiver"] == "DevPipelineState"
    assert message["message_type"] == "GATE_RESULT"
    assert message["retry_count"] == 1
    assert message["payload"]["gate"] == "DevelopBackendDomainGate"
    assert message["payload"]["status"] == "PASS"

    project_state = result["project_state"]
    assert project_state["current_feature_id"] == "FEAT_001"
    assert project_state["completed_domains"] == ["Backend"]
    assert project_state["last_gate_status"] == "BACKEND_DOMAIN_GATE_PASS"
    assert project_state["rag_sync_status"] == "PENDING"

    project_state_path = tmp_path / "PROJECT_STATE.md"
    assert project_state_path.is_file()
    rendered = project_state_path.read_text(encoding="utf-8")
    payload = rendered.split("```json", 1)[1].split("```", 1)[0].strip()
    assert json.loads(payload)["last_gate_status"] == "BACKEND_DOMAIN_GATE_PASS"


def test_dev_message_validation_rejects_missing_payload_fields() -> None:
    with pytest.raises(ValueError, match="INVALID_JSON_MESSAGE"):
        validate_dev_message(
            {
                "message_id": "msg_001",
                "pipeline": "DEV_PIPELINE",
                "feature_id": "FEAT_001",
                "sender": "BackendQaAgent",
                "receiver": "BackendDomainGate",
                "message_type": "QA_RESULT",
                "retry_count": 0,
                "max_retry": 3,
                "payload": {"domain": "Backend"},
                "timestamp": "2026-05-14T18:00:00+09:00",
            }
        )
