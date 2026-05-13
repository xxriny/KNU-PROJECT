from __future__ import annotations

from pipeline.domain.dev.test.fixtures import *


def test_main_agent_infers_backend_only_scope(tmp_path: Path, monkeypatch) -> None:
    import pipeline.domain.dev.nodes.main_agent as main_agent

    monkeypatch.setattr(main_agent, "_load_project_rag_context", lambda *args, **kwargs: {"chunks": []})
    monkeypatch.setattr(main_agent, "_load_artifact_rag_context", lambda *args, **kwargs: {"artifacts": []})

    result = develop_main_agent_node({
        **_base_state(tmp_path),
        "development_request": "백엔드 Todo API만 생성한다.",
        "enable_backend_codegen": True,
        "enable_frontend_codegen": False,
    })

    assert result["develop_main_plan"]["selected_domains"] == ["backend"]
    assert [item["domain"] for item in result["develop_main_plan"]["branch_strategy"]["domain_branches"]] == ["backend"]


def test_main_agent_infers_frontend_scope_with_uiux_handoff(tmp_path: Path, monkeypatch) -> None:
    import pipeline.domain.dev.nodes.main_agent as main_agent

    monkeypatch.setattr(main_agent, "_load_project_rag_context", lambda *args, **kwargs: {"chunks": []})
    monkeypatch.setattr(main_agent, "_load_artifact_rag_context", lambda *args, **kwargs: {"artifacts": []})

    result = develop_main_agent_node({
        **_base_state(tmp_path),
        "development_request": "프론트 화면만 생성한다.",
        "enable_backend_codegen": False,
        "enable_frontend_codegen": True,
    })

    assert result["develop_main_plan"]["selected_domains"] == ["uiux", "frontend"]


def test_main_agent_normalizes_sa_bundle_at_dev_boundary(tmp_path: Path, monkeypatch) -> None:
    import pipeline.domain.dev.nodes.main_agent as main_agent

    monkeypatch.setattr(main_agent, "_load_project_rag_context", lambda *args, **kwargs: {"chunks": []})
    monkeypatch.setattr(main_agent, "_load_artifact_rag_context", lambda *args, **kwargs: {"artifacts": []})

    result = develop_main_agent_node({
        **_base_state(tmp_path),
        "run_id": "session_123",
        "components": [],
        "apis": [],
        "tables": [],
        "sa_arch_bundle": {
            "metadata": {"version": "v2.3"},
            "data": {
                "components": [{"name": "PortfolioPage"}],
                "apis": [{"endpoint": "GET /portfolio"}],
                "tables": [{"table_name": "portfolios"}],
            },
        },
    })

    bundle = result["develop_main_plan"]["sa_bundle"]
    assert bundle["phase"] == "SA"
    assert bundle["version"] == "v2.3"
    assert bundle["bundle_id"] == "session_123_SA_BNDL"
    assert bundle["data"]["components"][0]["name"] == "PortfolioPage"
    assert bundle["data"]["apis"][0]["endpoint"] == "GET /portfolio"
    assert bundle["data"]["tables"][0]["table_name"] == "portfolios"
    assert result["develop_main_plan"]["sa_bundle_context"]["counts"] == {
        "components": 1,
        "apis": 1,
        "tables": 1,
    }


def test_main_agent_filters_current_feature_id_and_keeps_untraced_contracts(tmp_path: Path, monkeypatch) -> None:
    import pipeline.domain.dev.nodes.main_agent as main_agent

    monkeypatch.setattr(main_agent, "_load_project_rag_context", lambda *args, **kwargs: {"chunks": []})
    monkeypatch.setattr(main_agent, "_load_artifact_rag_context", lambda *args, **kwargs: {"artifacts": []})

    result = develop_main_agent_node({
        **_base_state(tmp_path),
        "current_feature_id": "FEAT_MSG",
        "requirements_rtm": [
            {"id": "FEAT_PROFILE", "description": "Show profile."},
            {"id": "FEAT_MSG", "description": "Send visitor messages."},
        ],
        "components": [
            {"name": "ProfilePage", "rtms": ["FEAT_PROFILE"]},
            {"name": "MessageForm", "rtms": ["FEAT_MSG"]},
        ],
        "apis": [
            {"endpoint": "GET /profile", "requirement_ids": ["FEAT_PROFILE"]},
            {"endpoint": "POST /messages"},
        ],
        "tables": [
            {"table_name": "profiles", "requirement_ids": ["FEAT_PROFILE"]},
            {"table_name": "messages"},
        ],
    })

    plan = result["develop_main_plan"]
    assert plan["current_feature_id"] == "FEAT_MSG"
    assert result["backend_task_spec"]["feature_id"] == "FEAT_MSG"
    assert result["backend_task_spec"]["requirement_ids"] == ["FEAT_MSG"]
    assert result["frontend_task_spec"]["target_components"] == ["MessageForm"]
    assert result["apis"] == [{"endpoint": "POST /messages"}]
    assert result["tables"] == [{"table_name": "messages"}]
    assert plan["project_rag_context"]["api_count"] == 1
    assert plan["project_rag_context"]["table_count"] == 1


def test_main_agent_attaches_approved_stack_and_generation_policy(tmp_path: Path, monkeypatch) -> None:
    import pipeline.domain.dev.nodes.main_agent as main_agent

    monkeypatch.setattr(main_agent, "_load_project_rag_context", lambda *args, **kwargs: {"chunks": []})
    monkeypatch.setattr(main_agent, "_load_artifact_rag_context", lambda *args, **kwargs: {"artifacts": []})

    result = develop_main_agent_node({
        **_base_state(tmp_path),
        "approved_stack": [
            {"domain": "Backend", "package": "express", "status": "APPROVED"},
            {"domain": "Frontend", "package": "react", "status": "APPROVED"},
            {"domain": "Frontend", "package": "vite", "status": "PENDING"},
        ],
    })

    backend_spec = result["backend_task_spec"]
    frontend_spec = result["frontend_task_spec"]
    assert backend_spec["approved_stack"]["packages"] == ["express"]
    assert frontend_spec["approved_stack"]["packages"] == ["react"]
    assert backend_spec["generation_policy"]["no_dummy_code"] is True
    assert result["develop_main_plan"]["generation_policy"]["no_unapproved_stack"] is True
    assert backend_spec["task_id"].startswith("task_GENERAL_BACKEND_")
    assert backend_spec["target_agent"] == "BackendAgent"
    assert backend_spec["dev_task"]["task_info"]["target_agent"] == "BackendAgent"
    assert backend_spec["dev_task"]["context"]["approved_stacks"] == ["express"]
    assert backend_spec["dev_task"]["context"]["sa_bundle"]["phase"] == "SA"
    assert backend_spec["dev_task"]["constraints"]["no_dummy_code"] is True
    assert DevTask.model_validate(backend_spec["dev_task"]).task_info.target_agent == "BackendAgent"
    assert "dev_tasks" in result["develop_main_plan"]


def test_dev_task_contract_flows_from_main_to_agents_and_codegen(tmp_path: Path, monkeypatch) -> None:
    import pipeline.domain.dev.nodes.main_agent as main_agent

    monkeypatch.setattr(main_agent, "_load_project_rag_context", lambda *args, **kwargs: {"chunks": []})
    monkeypatch.setattr(main_agent, "_load_artifact_rag_context", lambda *args, **kwargs: {"artifacts": []})

    target_repo = _init_git_repo(tmp_path / "target")
    main_state = {
        **_base_state(target_repo),
        "current_feature_id": "FEAT_LOGIN",
        "enable_backend_codegen": True,
        "enable_frontend_codegen": True,
        "approved_stack": [
            {"domain": "Backend", "package": "express", "status": "APPROVED"},
            {"domain": "Frontend", "package": "react", "status": "APPROVED"},
            {"domain": "Frontend", "package": "vite", "status": "APPROVED"},
        ],
        "requirements_rtm": [{"id": "FEAT_LOGIN", "description": "User can log in."}],
        "components": [
            {"name": "LoginPage", "domain": "frontend", "rtms": ["FEAT_LOGIN"]},
            {"name": "AuthService", "domain": "backend", "rtms": ["FEAT_LOGIN"]},
        ],
        "apis": [{"endpoint": "POST /api/auth/login", "requirement_ids": ["FEAT_LOGIN"]}],
        "tables": [{"table_name": "users", "requirement_ids": ["FEAT_LOGIN"]}],
        "integration_qa_result": {
            "status": "rework_backend",
            "findings": ["FE payload for POST /api/auth/login does not match SA request fields."],
            "rework_targets": ["backend", "frontend"],
        },

    }

    main_result = develop_main_agent_node(main_state)
    backend_task = main_result["backend_task_spec"]["dev_task"]
    frontend_task = main_result["frontend_task_spec"]["dev_task"]

    assert backend_task["context"]["target_api_specs"] == [{"endpoint": "POST /api/auth/login", "requirement_ids": ["FEAT_LOGIN"]}]
    assert backend_task["context"]["target_table_specs"] == [{"table_name": "users", "requirement_ids": ["FEAT_LOGIN"]}]
    assert backend_task["context"]["approved_stack"]["packages"] == ["express"]
    assert frontend_task["context"]["approved_stack"]["packages"] == ["react", "vite"]
    assert frontend_task["context"]["integration_feedback"]["integration_qa"]["status"] == "rework_backend"
    assert frontend_task["context"]["rework_instruction"]["active"] is True

    agent_state = {**main_state, **main_result}
    backend_result = develop_backend_agent_node(agent_state)["backend_result"]
    uiux_out = develop_uiux_agent_node(agent_state)
    frontend_state = {**agent_state, **uiux_out}
    frontend_result = develop_frontend_agent_node(frontend_state)["frontend_result"]

    assert backend_result["contract_handoff"]["apis"][0]["endpoint"] == "POST /api/auth/login"
    assert backend_result["contract_handoff"]["tables"][0]["table_name"] == "users"
    assert backend_result["approved_stack"]["packages"] == ["express"]
    assert frontend_result["frontend_plan"]["api_client_needs"] == ["POST /api/auth/login"]
    assert frontend_result["rework_instruction"]["active"] is True

    backend_codegen = develop_backend_codegen_node({
        **agent_state,
        "backend_result": backend_result,
        "backend_codegen_language": "typescript",
        "backend_codegen_framework": "express",
        "backend_codegen_mode": "template",
    })["backend_codegen_result"]
    frontend_codegen = develop_frontend_codegen_node({
        **frontend_state,
        "frontend_result": frontend_result,
        "frontend_codegen_language": "typescript",
        "frontend_codegen_framework": "react-vite",
        "frontend_codegen_mode": "template",
    })["frontend_codegen_result"]

    assert backend_codegen["status"] == "generated"
    assert backend_codegen["sa_contract"]["apis"][0]["endpoint"] == "POST /api/auth/login"
    assert backend_codegen["approved_stack"]["packages"] == ["express"]
    assert backend_codegen["task_instruction"]["dev_task"]["task_info"]["task_id"] == backend_task["task_info"]["task_id"]
    assert frontend_codegen["status"] == "generated"
    assert frontend_codegen["sa_contract"]["apis"][0]["endpoint"] == "POST /api/auth/login"
    assert frontend_codegen["approved_stack"]["packages"] == ["react", "vite"]
    assert frontend_codegen["task_instruction"]["dev_task"]["task_info"]["task_id"] == frontend_task["task_info"]["task_id"]


def test_main_agent_reselects_only_integration_rework_targets(tmp_path: Path, monkeypatch) -> None:
    import pipeline.domain.dev.nodes.main_agent as main_agent

    monkeypatch.setattr(main_agent, "_load_project_rag_context", lambda *args, **kwargs: {"chunks": []})
    monkeypatch.setattr(main_agent, "_load_artifact_rag_context", lambda *args, **kwargs: {"artifacts": []})

    result = develop_main_agent_node({
        **_base_state(tmp_path),
        "development_request": "전체 포트폴리오 사이트를 만든다.",
        "integration_qa_result": {
            "status": "rework_frontend",
            "findings": ["FE calls GET /api/debug, but SA API contract does not define it."],
            "rework_targets": ["frontend"],
        },
    })

    assert result["develop_main_plan"]["selected_domains"] == ["frontend"]
    assert result["develop_integration_rework_count"] == 1
    assert result["frontend_task_spec"]["rework_instruction"]["active"] is True
    assert "FE calls GET /api/debug" in result["frontend_task_spec"]["rework_instruction"]["findings"][0]
    dev_task = result["frontend_task_spec"]["dev_task"]
    assert dev_task["task_info"]["target_agent"] == "FrontendAgent"
    assert dev_task["context"]["integration_feedback"]["integration_qa"]["status"] == "rework_frontend"
    assert dev_task["context"]["rework_instruction"]["active"] is True


def test_main_agent_passes_sa_bundle_and_rework_instruction(tmp_path: Path, monkeypatch) -> None:
    import pipeline.domain.dev.nodes.main_agent as main_agent

    monkeypatch.setattr(main_agent, "_load_project_rag_context", lambda *args, **kwargs: {"chunks": []})
    monkeypatch.setattr(main_agent, "_load_artifact_rag_context", lambda *args, **kwargs: {"artifacts": []})

    result = develop_main_agent_node({
        **_base_state(tmp_path),
        "enable_backend_codegen": True,
        "sa_arch_bundle": {
            "apis": [{"endpoint": "GET /bundle"}],
            "tables": [{"table_name": "bundle_items"}],
        },
        "integration_qa_result": {
            "status": "rework_backend",
            "findings": ["Backend endpoint mismatch."],
            "rework_targets": ["backend"],
        },
    })

    plan = result["develop_main_plan"]
    assert plan["sa_bundle_context"]["available"] is True
    assert result["backend_task_spec"]["rework_instruction"]["active"] is True
    assert "Backend endpoint mismatch." in result["backend_task_spec"]["rework_instruction"]["findings"]


def test_domain_agents_include_rework_instruction(tmp_path: Path) -> None:
    state = {
        "backend_task_spec": {
            "requirement_ids": ["REQ_1"],
            "rework_instruction": {"active": True, "actions": ["Fix backend contract mismatch."]},
        },
        "frontend_task_spec": {
            "requirement_ids": ["REQ_1"],
            "rework_instruction": {"active": True, "actions": ["Fix frontend route mismatch."]},
        },
        "uiux_task_spec": {
            "requirement_ids": ["REQ_1"],
            "rework_instruction": {"active": True, "actions": ["Fix UIUX handoff mismatch."]},
        },
        "apis": [{"endpoint": "GET /items"}],
        "tables": [{"table_name": "items", "columns": [{"name": "id"}]}],
        "components": [{"name": "ItemsScreen"}],
    }

    backend = develop_backend_agent_node(state)["backend_result"]
    uiux = develop_uiux_agent_node(state)["uiux_result"]
    frontend_state = {
        **state,
        "uiux_artifact": develop_uiux_agent_node(state)["uiux_artifact"],
    }
    frontend = develop_frontend_agent_node(frontend_state)["frontend_result"]

    assert backend["rework_instruction"]["active"] is True
    assert any("backend contract" in item.lower() for item in backend["test_plan"])
    assert uiux["rework_instruction"]["active"] is True
    assert frontend["rework_instruction"]["active"] is True


def test_domain_agents_expose_approved_stack_and_policy_enforcement(tmp_path: Path) -> None:
    spec_stack = {"packages": ["express"], "items": [{"package": "express"}]}
    policy = {"no_dummy_code": True, "no_unapproved_stack": True}
    state = {
        "backend_task_spec": {
            "requirement_ids": ["REQ_1"],
            "approved_stack": spec_stack,
            "generation_policy": policy,
        },
        "frontend_task_spec": {
            "requirement_ids": ["REQ_1"],
            "approved_stack": {"packages": ["react"]},
            "generation_policy": policy,
        },
        "uiux_task_spec": {
            "requirement_ids": ["REQ_1"],
            "approved_stack": {"packages": ["figma-tokens"]},
            "generation_policy": policy,
        },
        "apis": [{"endpoint": "GET /items"}],
        "tables": [{"table_name": "items", "columns": [{"name": "id"}]}],
        "components": [{"name": "ItemsScreen"}],
    }

    backend = develop_backend_agent_node(state)["backend_result"]
    uiux = develop_uiux_agent_node(state)["uiux_result"]
    frontend = develop_frontend_agent_node({
        **state,
        "uiux_artifact": develop_uiux_agent_node(state)["uiux_artifact"],
    })["frontend_result"]

    assert backend["approved_stack"]["packages"] == ["express"]
    assert backend["contract_handoff"]["approved_stack"]["packages"] == ["express"]
    assert backend["policy_enforcement"]["status"] == "passed"
    assert uiux["approved_stack"]["packages"] == ["figma-tokens"]
    assert frontend["approved_stack"]["packages"] == ["react"]


def test_domain_agents_prefer_dev_task_context_over_legacy_state() -> None:
    dev_task = {
        "task_info": {"task_id": "task_FEAT_DEV_BACKEND_01", "target_agent": "BackendAgent", "feature_id": "FEAT_DEV"},
        "context": {
            "approved_stack": {"packages": ["express"]},
            "target_api_specs": [{"endpoint": "POST /from-dev-task"}],
            "target_table_specs": [{"table_name": "dev_task_items"}],
            "component_specs": [{"name": "DevTaskService"}],
            "target_components": ["DevTaskScreen"],
            "rework_instruction": {"active": True, "actions": ["Use DEV_TASK context."]},
        },
        "constraints": {"no_dummy_code": True},
    }

    backend = develop_backend_agent_node({
        "backend_task_spec": {"requirement_ids": ["REQ_1"], "dev_task": dev_task},
        "apis": [{"endpoint": "GET /from-state"}],
        "tables": [{"table_name": "state_items"}],
        "components": [{"name": "StateService"}],
    })["backend_result"]
    assert backend["contract_handoff"]["apis"][0]["endpoint"] == "POST /from-dev-task"
    assert backend["contract_handoff"]["tables"][0]["table_name"] == "dev_task_items"
    assert backend["approved_stack"]["packages"] == ["express"]
    assert backend["generation_policy"]["no_dummy_code"] is True

    frontend = develop_frontend_agent_node({
        "frontend_task_spec": {"requirement_ids": ["REQ_1"], "dev_task": dev_task},
        "uiux_artifact": {"frontend_handoff": {"routes": ["/dev-task"]}},
        "apis": [{"endpoint": "GET /from-state"}],
    })["frontend_result"]
    assert frontend["frontend_plan"]["api_client_needs"] == ["POST /from-dev-task"]
    assert "DevTaskScreen" in frontend["files"][1]
