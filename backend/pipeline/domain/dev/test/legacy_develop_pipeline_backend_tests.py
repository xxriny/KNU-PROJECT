from __future__ import annotations

import subprocess
import py_compile
from types import SimpleNamespace
from pathlib import Path

from orchestration.executor import execute_pipeline
from pipeline.domain.dev.nodes.backend_codegen import develop_backend_codegen_node
from pipeline.domain.dev.nodes.backend_agent import develop_backend_agent_node
from pipeline.domain.dev.nodes.backend_qa_agent import develop_backend_qa_agent_node
from pipeline.domain.dev.nodes.backend_codegen_verifier import (
    _extract_failed_file_paths,
    _semantic_slices,
    develop_backend_codegen_repair_node,
    develop_backend_codegen_verifier_node,
    develop_backend_runtime_blocker_node,
)
from pipeline.domain.dev.nodes.branch_pr_orchestrator import develop_branch_pr_orchestrator_node
from pipeline.domain.dev.nodes.domain_gates import develop_backend_domain_gate_node
from pipeline.domain.dev.nodes.frontend_agent import develop_frontend_agent_node
from pipeline.domain.dev.nodes.frontend_codegen import develop_frontend_codegen_node
from pipeline.domain.dev.nodes.frontend_codegen_verifier import (
    develop_frontend_codegen_repair_node,
    develop_frontend_codegen_reverifier_node,
    develop_frontend_codegen_verifier_node,
    develop_frontend_runtime_blocker_node,
)
from pipeline.domain.dev.nodes.frontend_qa_agent import develop_frontend_qa_agent_node
from pipeline.domain.dev.nodes.fullstack_runtime_verifier import develop_fullstack_runtime_verifier_node
from pipeline.domain.dev.nodes.global_sync_gate import develop_global_fe_sync_gate_node
from pipeline.domain.dev.nodes.integration_qa_gate import develop_integration_qa_gate_node
from pipeline.domain.dev.nodes.main_agent import develop_main_agent_node
from pipeline.domain.dev.nodes.uiux_agent import develop_uiux_agent_node
from pipeline.domain.dev.nodes.uiux_qa_agent import develop_uiux_qa_agent_node
from pipeline.domain.dev.schemas import DevTask
from pipeline.orchestration.dev_graphs import (
    _route_backend_codegen_repair,
    _route_backend_codegen_reverification,
    _route_backend_codegen_verification,
    _route_backend_static_qa_recheck,
    _route_frontend_codegen_repair,
    _route_frontend_codegen_reverification,
    _route_frontend_codegen_verification,
    _route_frontend_static_qa_recheck,
    _route_integration_qa_gate,
    get_develop_pipeline,
)

# --- 유틸리티 함수: Git 작업 및 환경 초기화 ---
def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "README.md").write_text("# fixture\n", encoding="utf-8")
    _git(["init"], path)
    _git(["config", "user.email", "test@example.com"], path)
    _git(["config", "user.name", "Test User"], path)
    _git(["add", "README.md"], path)
    _git(["commit", "-m", "initial"], path)
    _git(["branch", "develop"], path)
    return path


def _base_state(source_dir: Path) -> dict:
    """테스트에 사용될 기본 파이프라인 상태(State) 정의"""
    return {
        "run_id": "20260504_000000",
        "source_dir": str(source_dir),
        "development_request": "사용자 로그인 API와 화면을 추가한다",
        "previous_result": {"metadata": {"session_id": "source_session"}},
        "requirements_rtm": [ # PM Layer에서 전달된 요구사항 (FEAT_XXX)
            {
                "id": "FEAT_001",
                "description": "사용자는 이메일과 비밀번호로 로그인할 수 있어야 한다.",
                "priority": "must-have",
            }
        ],
        "components": [ # SA Layer에서 설계된 컴포넌트 목록
            {"name": "LoginPage", "domain": "frontend"},
            {"name": "AuthService", "domain": "backend"},
        ],
        "apis": [{"endpoint": "POST /api/auth/login"}], # SA 설계 API 명세
        "tables": [{"table_name": "users"}], # SA 설계 DB 테이블 명세
        "project_overview": {"summary": "로그인 기능이 필요한 서비스"},
        "pm_overview": {},
        "sa_overview": {},
        "sa_artifacts": {},
    }

# --- 단위 테스트: 각 도메인 및 노드별 로직 검증 ---

def test_domain_gate_blocks_after_retry_budget() -> None:
    # 1회차 재시도: 상태가 rework로 설정되고 카운트 증가 확인
    first = develop_backend_domain_gate_node(
        {
            "backend_qa_result": {
                "status": "rework",
                "findings": ["API contract missing"],
                "fixes_required": ["Add request schema"],
            },
            "backend_retry_count": 0,
        }
    )
    assert first["backend_domain_gate_result"]["status"] == "rework"
    assert first["backend_retry_count"] == 1
    # 2회차 재시도 (한계 도달 시): 더 이상 루프를 돌지 않고 blocked 처리
    second = develop_backend_domain_gate_node(
        {
            "backend_qa_result": {
                "status": "rework",
                "findings": ["API contract missing"],
                "fixes_required": ["Add request schema"],
            },
            "backend_retry_count": 1,
        }
    )
    assert second["backend_domain_gate_result"]["status"] == "blocked"
    assert second["backend_domain_gate_result"]["blocking_findings"] == ["Add request schema"]


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


def test_integration_qa_rework_routes_back_to_main_agent() -> None:
    assert _route_integration_qa_gate({"integration_qa_result": {"status": "rework_frontend"}}) == "retry_main"
    assert _route_integration_qa_gate({"integration_qa_result": {"status": "rework_backend"}}) == "retry_main"
    assert _route_integration_qa_gate({
        "integration_qa_result": {"status": "rework_backend"},
        "develop_integration_rework_count": 1,
    }) == "block"
    assert _route_integration_qa_gate({"integration_qa_result": {"status": "pass"}}) == "pass"


def test_integration_qa_ignores_unselected_domains() -> None:
    result = develop_integration_qa_gate_node({
        "develop_main_plan": {"selected_domains": ["backend"]},
        "backend_result": {"files": ["api:/todos"]},
        "frontend_result": {},
        "uiux_result": {},
    })["integration_qa_result"]

    assert result["status"] == "pass"


def test_fullstack_runtime_verifier_skips_without_fullstack_scope() -> None:
    result = develop_fullstack_runtime_verifier_node({
        "develop_main_plan": {"selected_domains": ["backend"]},
        "backend_codegen_result": {"status": "generated"},
        "frontend_codegen_result": {"status": "generated"},
    })["fullstack_runtime_verification"]

    assert result["status"] == "skipped"


def test_fullstack_runtime_verifier_fails_missing_generated_outputs(tmp_path: Path) -> None:
    result = develop_fullstack_runtime_verifier_node({
        "develop_main_plan": {"selected_domains": ["backend", "frontend"]},
        "backend_codegen_result": {"status": "generated", "output_dir": str(tmp_path / "backend")},
        "frontend_codegen_result": {"status": "generated", "output_dir": str(tmp_path / "frontend")},
    })["fullstack_runtime_verification"]

    assert result["status"] == "failed" # 불일치로 인한 재작업 지시 확인
    assert "backend" in result["rework_targets"]
    assert "frontend" in result["rework_targets"]


def test_fullstack_runtime_verifier_flags_package_generated_without_package_json(tmp_path: Path) -> None:
    backend_dir = tmp_path / "backend"
    frontend_dir = tmp_path / "frontend"
    backend_dir.mkdir()
    frontend_dir.mkdir()
    (backend_dir / "package.generated.json").write_text('{"scripts":{"dev":"node src/index.js"}}', encoding="utf-8")
    (frontend_dir / "package.json").write_text('{"scripts":{"dev":"vite"}}', encoding="utf-8")
    (frontend_dir / "node_modules").mkdir()

    result = develop_fullstack_runtime_verifier_node({
        "develop_main_plan": {"selected_domains": ["backend", "frontend"]},
        "backend_codegen_result": {"status": "generated", "output_dir": str(backend_dir)},
        "frontend_codegen_result": {"status": "generated", "output_dir": str(frontend_dir)},
    })["fullstack_runtime_verification"]

    assert result["status"] == "failed"
    assert result["rework_targets"] == ["backend"]
    assert any("package.generated.json" in finding for finding in result["findings"])


def test_fullstack_runtime_verifier_installs_dependencies_when_enabled(tmp_path: Path, monkeypatch) -> None:
    import pipeline.domain.dev.nodes.fullstack_runtime_verifier as verifier

    backend_dir = tmp_path / "backend"
    frontend_dir = tmp_path / "frontend"
    backend_dir.mkdir()
    frontend_dir.mkdir()
    (backend_dir / "package.json").write_text('{"scripts":{"dev":"node server.js"}}', encoding="utf-8")
    (frontend_dir / "package.json").write_text('{"scripts":{"dev":"vite"}}', encoding="utf-8")
    (backend_dir / "src").mkdir()
    (frontend_dir / "src" / "api").mkdir(parents=True)
    (frontend_dir / "src" / "api" / "client.ts").write_text(
        "const API_BASE_URL = import.meta.env.VITE_API_BASE_URL; fetch(`${API_BASE_URL}/todos`);",
        encoding="utf-8",
    )

    def fake_install(path: Path):
        (path / "node_modules").mkdir()
        return {"status": "passed", "command": ["npm", "install"], "returncode": 0}

    class FakeProcess:
        returncode = None

        def poll(self):
            return None

        def terminate(self):
            self.returncode = 0

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(verifier, "_run_dependency_install", fake_install)
    monkeypatch.setattr(verifier, "_start_backend", lambda output_dir, port: (FakeProcess(), ""))
    monkeypatch.setattr(verifier, "_start_frontend", lambda output_dir, port, backend_url: (FakeProcess(), ""))
    monkeypatch.setattr(verifier, "_wait_for_backend", lambda base_url, probes: (True, "", {"path": "/todos"}))
    monkeypatch.setattr(verifier, "_wait_for_text", lambda url: (True, "", "<html><div id='root'></div></html>"))

    result = develop_fullstack_runtime_verifier_node({
        "enable_dependency_install": True,
        "develop_main_plan": {"selected_domains": ["backend", "frontend"]},
        "apis": [{"endpoint": "GET /todos"}],
        "backend_codegen_result": {"status": "generated", "output_dir": str(backend_dir)},
        "frontend_codegen_result": {"status": "generated", "output_dir": str(frontend_dir)},
    })["fullstack_runtime_verification"]

    assert result["status"] == "passed"
    assert any(check["name"] == "backend_dependency_install" for check in result["checks"])
    assert any(check["name"] == "frontend_dependency_install" for check in result["checks"])


def test_integration_qa_blocks_failed_fullstack_runtime() -> None:
    result = develop_integration_qa_gate_node({
        "develop_main_plan": {"selected_domains": ["backend", "frontend"]},
        "backend_result": {"files": ["backend:api"]},
        "frontend_result": {"files": ["frontend:app"]},
        "uiux_result": {"files": ["uiux:screen"]},
        "fullstack_runtime_verification": {
            "status": "failed",
            "findings": ["Backend did not respond."],
            "rework_targets": ["backend", "frontend"],
        },
    })["integration_qa_result"]

    assert result["status"] == "rework_backend"
    assert result["rework_targets"] == ["backend", "frontend"]
    assert result["fullstack_runtime_verification"]["status"] == "failed"


def test_integration_qa_cross_checks_fe_be_code_against_sa_contract(tmp_path: Path) -> None:
    backend_dir = tmp_path / "backend_generated"
    frontend_dir = tmp_path / "frontend_generated"
    backend_src = backend_dir / "src"
    frontend_src = frontend_dir / "src"
    backend_src.mkdir(parents=True)
    frontend_src.mkdir(parents=True)
    (backend_src / "routes.ts").write_text(
        "router.get('/api/projects', handler);\n",
        encoding="utf-8",
    )
    (frontend_src / "client.ts").write_text(
        "export const load = () => axios.get('/api/messages');\n",
        encoding="utf-8",
    )

    result = develop_integration_qa_gate_node({
        "develop_main_plan": {"selected_domains": ["backend", "frontend"]},
        "backend_result": {"files": ["backend:api"]},
        "frontend_result": {"files": ["frontend:app"]},
        "uiux_result": {"files": ["uiux:screen"]},
        "apis": [{"endpoint": "GET /api/projects"}],
        "backend_codegen_result": {
            "status": "generated",
            "output_dir": str(backend_dir),
            "files": [{"path": str(backend_src / "routes.ts")}],
        },
        "frontend_codegen_result": {
            "status": "generated",
            "output_dir": str(frontend_dir),
            "files": [{"path": str(frontend_src / "client.ts")}],
        },
    })["integration_qa_result"]

    assert result["status"] == "rework_frontend"
    assert result["interface_contract_check"]["status"] == "failed"
    assert "GET /api/messages" in result["interface_contract_check"]["frontend_calls"][0]["endpoint"]
    assert "frontend" in result["rework_targets"]


def test_integration_qa_detects_frontend_payload_contract_mismatch(tmp_path: Path) -> None:
    backend_dir = tmp_path / "backend_generated"
    frontend_dir = tmp_path / "frontend_generated"
    backend_src = backend_dir / "src"
    frontend_src = frontend_dir / "src"
    backend_src.mkdir(parents=True)
    frontend_src.mkdir(parents=True)
    (backend_src / "routes.ts").write_text("router.post('/api/messages', handler);\n", encoding="utf-8")
    (frontend_src / "client.ts").write_text(
        "export const send = () => axios.post('/api/messages', { name: 'Ning' });\n",
        encoding="utf-8",
    )

    result = develop_integration_qa_gate_node({
        "develop_main_plan": {"selected_domains": ["backend", "frontend"]},
        "backend_result": {"files": ["backend:api"]},
        "frontend_result": {"files": ["frontend:app"]},
        "uiux_result": {"files": ["uiux:screen"]},
        "apis": [{
            "endpoint": "POST /api/messages",
            "request_schema": {"properties": {"senderName": {}, "senderEmail": {}, "content": {}}},
        }],
        "backend_codegen_result": {
            "status": "generated",
            "output_dir": str(backend_dir),
            "files": [{"path": str(backend_src / "routes.ts")}],
        },
        "frontend_codegen_result": {
            "status": "generated",
            "output_dir": str(frontend_dir),
            "files": [{"path": str(frontend_src / "client.ts")}],
        },
    })["integration_qa_result"]

    mismatch = result["interface_contract_check"]["mismatches"][0]
    assert result["status"] == "rework_frontend"
    assert mismatch["type"] == "fe_payload_not_matching_sa_contract"
    assert mismatch["responsible_domain"] == "frontend"


def test_integration_qa_extracts_custom_clients_fastapi_and_spring_routes(tmp_path: Path) -> None:
    backend_dir = tmp_path / "backend_generated"
    frontend_dir = tmp_path / "frontend_generated"
    backend_src = backend_dir / "src"
    frontend_src = frontend_dir / "src"
    backend_src.mkdir(parents=True)
    frontend_src.mkdir(parents=True)
    (backend_src / "routes.py").write_text(
        '@router.get("/api/projects")\ndef list_projects():\n    pass\n',
        encoding="utf-8",
    )
    (backend_src / "MessageController.java").write_text(
        '@PostMapping("/api/messages")\npublic void createMessage() {}\n',
        encoding="utf-8",
    )
    (frontend_src / "client.ts").write_text(
        "export const load = () => apiClient.get('/api/projects');\n"
        "export const send = () => client.request({ method: 'POST', url: '/api/messages' });\n",
        encoding="utf-8",
    )

    result = develop_integration_qa_gate_node({
        "develop_main_plan": {"selected_domains": ["backend", "frontend"]},
        "backend_result": {"files": ["backend:api"]},
        "frontend_result": {"files": ["frontend:app"]},
        "apis": [
            {"endpoint": "GET /api/projects"},
            {"endpoint": "POST /api/messages"},
        ],
        "backend_codegen_result": {
            "status": "generated",
            "output_dir": str(backend_dir),
            "files": [
                {"path": str(backend_src / "routes.py")},
                {"path": str(backend_src / "MessageController.java")},
            ],
        },
        "frontend_codegen_result": {
            "status": "generated",
            "output_dir": str(frontend_dir),
            "files": [{"path": str(frontend_src / "client.ts")}],
        },
    })["integration_qa_result"]

    check = result["interface_contract_check"]
    assert result["status"] == "pass"
    assert check["status"] == "pass"
    assert {call["source"] for call in check["frontend_calls"]} == {"custom_client"}
    assert {route["source"] for route in check["backend_routes"]} == {"fastapi", "spring"}


def test_uiux_agent_generates_structured_artifact(tmp_path: Path) -> None:
    result = develop_uiux_agent_node({
        "uiux_task_spec": {
            "requirement_ids": ["REQ_TODO_001"],
            "target_components": ["TodoListScreen", "TodoEditor"],
            "acceptance_criteria": ["User can create todos"],
            "inputs": ["GET /todos", "POST /todos"],
        },
        "artifact_rag_context": {"apis": [{"endpoint": "GET /todos"}]},
    })

    artifact = result["uiux_artifact"]
    assert artifact["status"] == "ready_for_frontend"
    assert artifact["screens"]
    assert artifact["user_flows"]
    assert artifact["component_tree"]
    assert artifact["frontend_handoff"]["routes"]
    assert "GET /todos" in artifact["frontend_handoff"]["api_client_needs"]
    assert artifact["screens"][0]["requirement_ids"] == ["REQ_TODO_001"]
    assert artifact["screens"][0]["acceptance_criteria"] == ["User can create todos"]


def test_uiux_agent_traces_sa_data_and_components() -> None:
    result = develop_uiux_agent_node({
        "uiux_task_spec": {
            "requirement_ids": ["REQ_TODO_001"],
            "target_components": ["TodoListScreen"],
            "acceptance_criteria": ["User can view todos"],
        },
        "artifact_rag_context": {
            "apis": [{"endpoint": "GET /todos"}],
            "tables": [{"table_name": "todos", "columns": [{"name": "title"}, {"name": "completed"}]}],
            "components": [{"component_name": "TodoList"}],
        },
    })

    artifact = result["uiux_artifact"]
    assert "todos.title" in artifact["screens"][0]["data_dependencies"]
    assert "todos.completed" in artifact["frontend_handoff"]["data_contracts"]
    assert artifact["component_tree"][0]["source_component"] == "TodoList"


def test_uiux_qa_requires_structured_frontend_handoff() -> None:
    result = develop_uiux_qa_agent_node({
        "uiux_result": {
            "status": "draft",
            "domain": "uiux",
            "requirement_ids": ["REQ_1"],
            "proposed_changes": ["one", "two"],
            "files": ["uiux:screen"],
            "test_plan": [],
        },
        "uiux_artifact": {
            "status": "draft",
            "screens": [],
            "user_flows": [],
            "component_tree": [],
            "frontend_handoff": {},
        },
        "uiux_task_spec": {},
    })["uiux_qa_result"]

    assert result["status"] == "rework"
    assert any("screens" in finding for finding in result["findings"])
    assert any("frontend routes" in fix.lower() for fix in result["fixes_required"])


def test_uiux_qa_enforces_policy_and_approved_stack_handoff() -> None:
    result = develop_uiux_qa_agent_node({
        "uiux_result": {
            "status": "draft",
            "domain": "uiux",
            "requirement_ids": ["REQ_1"],
            "proposed_changes": ["Define screen", "Define flow"],
            "files": ["uiux:screen"],
            "test_plan": ["Screen meets requirement."],
            "policy_enforcement": {"status": "failed", "findings": ["UI/UX placeholder policy failed."]},
        },
        "uiux_artifact": {
            "status": "draft",
            "screens": [{
                "id": "screen_1",
                "name": "Projects",
                "purpose": "Show projects",
                "route": "/projects",
                "states": ["loading", "error"],
                "requirement_ids": ["REQ_1"],
                "acceptance_criteria": ["Screen meets requirement."],
            }],
            "user_flows": [{"id": "flow_1", "name": "View", "requirement_ids": ["REQ_1"]}],
            "component_tree": [{"name": "ProjectsScreen", "source_component": "ProjectsScreen"}],
            "empty_states": ["No projects"],
            "error_states": ["Cannot load projects"],
            "accessibility_requirements": ["Keyboard navigation"],
            "frontend_handoff": {"routes": ["/projects"], "api_client_needs": ["GET /projects"]},
        },
        "uiux_task_spec": {
            "acceptance_criteria": ["Screen meets requirement."],
            "approved_stack": {"packages": ["design-tokens"]},
            "generation_policy": {"no_dummy_code": True},
        },
    })["uiux_qa_result"]

    assert result["status"] == "rework"
    assert any("approved_stack" in finding for finding in result["findings"])
    assert any("placeholder policy" in finding.lower() for finding in result["findings"])


def test_frontend_agent_uses_uiux_artifact_and_sa_contracts() -> None:
    state = {
        "frontend_task_spec": {
            "requirement_ids": ["REQ_TODO_001"],
            "target_components": ["TodoListScreen"],
        },
        "uiux_artifact": {
            "screens": [
                {
                    "name": "TodoListScreen",
                    "route": "/todo-list-screen",
                    "states": ["default", "loading", "empty", "error"],
                    "api_dependencies": ["GET /todos"],
                    "data_dependencies": ["todos.title"],
                }
            ],
            "frontend_handoff": {
                "routes": ["/todo-list-screen"],
                "api_client_needs": ["GET /todos", "POST /todos"],
                "data_contracts": ["todos.title", "todos.completed"],
                "state_management_notes": ["Use explicit loading/error states."],
            },
        },
        "apis": [{"endpoint": "GET /todos"}],
        "tables": [{"table_name": "todos", "columns": [{"name": "title"}]}],
        "backend_codegen_result": {"output_dir": "generated", "verification_adapter": "node"},
    }

    result = develop_frontend_agent_node(state)["frontend_result"]
    plan = result["frontend_plan"]
    assert plan["routes"] == ["/todo-list-screen"]
    assert "POST /todos" in plan["api_client_needs"]
    assert "todos.completed" in plan["data_contracts"]
    assert plan["screen_bindings"][0]["screen"] == "TodoListScreen"


def test_frontend_qa_requires_handoff_based_plan() -> None:
    result = develop_frontend_qa_agent_node({
        "frontend_result": {
            "status": "draft",
            "domain": "frontend",
            "requirement_ids": ["REQ_1"],
            "proposed_changes": ["one", "two"],
            "files": ["frontend:screen"],
            "test_plan": [],
            "frontend_plan": {},
        },
        "frontend_task_spec": {},
    })["frontend_qa_result"]

    assert result["status"] == "rework"
    assert any("routes" in finding for finding in result["findings"])
    assert any("api client" in finding.lower() for finding in result["findings"])


def test_backend_qa_static_review_blocks_generated_code_outside_sa_contract(tmp_path: Path) -> None:
    output_dir = tmp_path / "backend_generated"
    src_dir = output_dir / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "routes.ts").write_text(
        "router.get('/api/projects', handler);\nrouter.post('/api/debug', handler);\n",
        encoding="utf-8",
    )
    (output_dir / "package.json").write_text(
        '{"dependencies":{"express":"^4.0.0","mongoose":"^8.0.0"},"devDependencies":{"typescript":"^5.0.0"}}',
        encoding="utf-8",
    )

    result = develop_backend_qa_agent_node({
        "apis": [{"endpoint": "GET /api/projects"}],
        "tables": [{"table_name": "projects"}],
        "components": [{"name": "ProjectService"}],
        "backend_task_spec": {
            "requirement_ids": ["REQ_1"],
            "acceptance_criteria": ["Project list is available."],
            "approved_stack": {"packages": ["express"]},
        },
        "backend_result": {
            "domain": "backend",
            "requirement_ids": ["REQ_1"],
            "files": ["api:GET /api/projects"],
            "proposed_changes": ["Implement projects API", "Persist projects"],
            "test_plan": ["Project list is available."],
            "approved_stack": {"packages": ["express"]},
        },
        "backend_codegen_result": {
            "status": "generated",
            "output_dir": str(output_dir),
            "files": [{"path": str(src_dir / "routes.ts")}],
            "approved_stack": {"packages": ["express"]},
        },
    })["backend_qa_result"]

    assert result["status"] == "rework"
    assert result["static_code_review"]["mode"] == "static_only"
    assert result["static_code_review"]["run_and_see"] is False
    assert any("absent from SA_BUNDLE" in finding for finding in result["findings"])
    assert any("outside approved_stack" in finding for finding in result["findings"])


def test_frontend_qa_static_review_blocks_generated_code_outside_sa_contract(tmp_path: Path) -> None:
    output_dir = tmp_path / "frontend_generated"
    src_dir = output_dir / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "client.tsx").write_text(
        """
        import axios from 'axios';
        export const load = () => axios.get('/api/debug');
        export function App() { return <div>success</div>; }
        """,
        encoding="utf-8",
    )
    (output_dir / "package.json").write_text(
        '{"dependencies":{"react":"^18.0.0","axios":"^1.0.0","zustand":"^4.0.0"},"devDependencies":{"vite":"^5.0.0","typescript":"^5.0.0"}}',
        encoding="utf-8",
    )

    result = develop_frontend_qa_agent_node({
        "apis": [{"endpoint": "GET /api/projects"}],
        "frontend_task_spec": {
            "requirement_ids": ["REQ_1"],
            "acceptance_criteria": ["Project list is visible."],
            "approved_stack": {"packages": ["react", "axios"]},
        },
        "frontend_result": {
            "domain": "frontend",
            "requirement_ids": ["REQ_1"],
            "files": ["frontend:Projects"],
            "proposed_changes": ["Implement projects screen", "Bind projects API"],
            "test_plan": ["Project list is visible."],
            "approved_stack": {"packages": ["react", "axios"]},
            "frontend_plan": {
                "routes": ["/projects"],
                "api_client_needs": ["GET /api/projects"],
                "screen_bindings": [{"route": "/projects", "states": ["loading", "error", "empty", "success"]}],
            },
        },
        "frontend_codegen_result": {
            "status": "generated",
            "output_dir": str(output_dir),
            "files": [{"path": str(src_dir / "client.tsx")}],
            "approved_stack": {"packages": ["react", "axios"]},
        },
    })["frontend_qa_result"]

    assert result["status"] == "rework"
    assert result["static_code_review"]["mode"] == "static_only"
    assert result["static_code_review"]["run_and_see"] is False
    assert any("absent from SA_BUNDLE" in finding for finding in result["findings"])
    assert any("outside approved_stack" in finding for finding in result["findings"])


def test_domain_qa_prefers_dev_task_contracts_for_static_review(tmp_path: Path) -> None:
    output_dir = tmp_path / "backend_generated"
    src_dir = output_dir / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "routes.ts").write_text("router.get('/api/state-contract', handler);\n", encoding="utf-8")

    result = develop_backend_qa_agent_node({
        "apis": [{"endpoint": "GET /api/state-contract"}],
        "backend_task_spec": {
            "requirement_ids": ["REQ_1"],
            "dev_task": {
                "task_info": {"task_id": "task_REQ_1_BACKEND_01", "target_agent": "BackendAgent"},
                "context": {
                    "target_api_specs": [{"endpoint": "GET /api/dev-task-contract"}],
                    "target_table_specs": [],
                    "component_specs": [],
                    "approved_stack": {"packages": []},
                },
                "constraints": {"no_dummy_code": True},
            },
        },
        "backend_result": {
            "domain": "backend",
            "requirement_ids": ["REQ_1"],
            "files": ["api:GET /api/dev-task-contract"],
            "proposed_changes": ["Implement API", "Verify contract"],
            "test_plan": [],
        },
        "backend_codegen_result": {
            "status": "generated",
            "output_dir": str(output_dir),
            "files": [{"path": str(src_dir / "routes.ts")}],
        },
    })["backend_qa_result"]

    assert result["status"] == "rework"
    assert any("GET /api/dev-task-contract" in finding for finding in result["findings"])


def test_global_fe_sync_checks_handoff_routes_against_frontend_plan() -> None:
    result = develop_global_fe_sync_gate_node({
        "uiux_result": {"files": ["uiux:TodoListScreen"]},
        "uiux_artifact": {"frontend_handoff": {"routes": ["/todos", "/todo-detail"]}},
        "frontend_result": {
            "files": ["frontend:TodoListScreen"],
            "frontend_plan": {"routes": ["/todos"]},
        },
    })["global_fe_sync_result"]

    assert result["status"] == "rework_frontend" # 불일치로 인한 재작업 지시 확인
    assert "todo-detail" in result["sync_actions"][0]


def test_global_fe_sync_checks_generated_frontend_code_against_uiux_handoff(tmp_path: Path) -> None:
    frontend_dir = tmp_path / "frontend_generated"
    src_dir = frontend_dir / "src"
    src_dir.mkdir(parents=True)
    app_file = src_dir / "App.tsx"
    app_file.write_text(
        "export default function App() { return <main><a href='/todos'>Todos</a><span>loading</span></main>; }\n",
        encoding="utf-8",
    )

    result = develop_global_fe_sync_gate_node({
        "uiux_result": {"files": ["uiux:TodoListScreen"]},
        "uiux_artifact": {
            "frontend_handoff": {
                "routes": ["/todos", "/todo-detail"],
                "api_client_needs": ["GET /todos", "POST /messages"],
            },
            "screens": [{"name": "TodoListScreen", "route": "/todos", "states": ["loading", "error", "empty"]}],
        },
        "frontend_result": {
            "files": ["frontend:TodoListScreen"],
            "frontend_plan": {"routes": ["/todos", "/todo-detail"]},
        },
        "frontend_codegen_result": {
            "status": "generated",
            "output_dir": str(frontend_dir),
            "files": [{"path": str(app_file)}],
        },
    })["global_fe_sync_result"]

    assert result["status"] == "rework_frontend"
    assert result["code_sync"]["checked"] is True
    assert any("/todo-detail" in action for action in result["sync_actions"])
    assert any("/messages" in action for action in result["sync_actions"])
    assert any("error" in action and "empty" in action for action in result["sync_actions"])


def test_frontend_codegen_generates_react_vite_scaffold(tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")
    frontend_result = develop_frontend_agent_node({
        "frontend_task_spec": {"requirement_ids": ["REQ_1"], "target_components": ["TodoListScreen"]},
        "uiux_artifact": {
            "screens": [{"name": "TodoListScreen", "route": "/todos", "states": ["default", "loading", "error"]}],
            "frontend_handoff": {"routes": ["/todos"], "api_client_needs": ["GET /todos"]},
        },
        "apis": [{"endpoint": "GET /todos"}],
    })["frontend_result"]

    result = develop_frontend_codegen_node({
        "source_dir": str(target_repo),
        "enable_frontend_codegen": True,
        "frontend_codegen_language": "typescript",
        "frontend_codegen_framework": "react-vite",
        "frontend_codegen_mode": "template",
        "frontend_result": frontend_result,
        "uiux_artifact": {
            "screens": [{"name": "TodoListScreen", "route": "/todos", "states": ["default", "loading", "error"]}],
            "frontend_handoff": {"routes": ["/todos"], "api_client_needs": ["GET /todos"]},
        },
    })["frontend_codegen_result"]

    generated_dir = target_repo / "frontend" / "generated" / "navigator_dev" / "typescript_react_vite"
    assert result["status"] == "generated"
    assert result["support_level"] == "official"
    assert result["verification_adapter"] == "node"
    assert (generated_dir / "package.json").is_file()
    assert (generated_dir / "design-tokens.json").is_file()
    assert (generated_dir / "fsm.generated.json").is_file()
    assert (generated_dir / "openapi.generated.json").is_file()
    assert (generated_dir / "src" / "App.tsx").is_file()
    assert (generated_dir / "src" / "api" / "client.ts").is_file()
    assert (generated_dir / "src" / "api" / "hooks.ts").is_file()
    assert (generated_dir / "src" / "state" / "uiMachine.ts").is_file()
    assert (generated_dir / "src" / "styles" / "tokens.css").is_file()
    assert (generated_dir / "tests" / "App.test.tsx").is_file()
    assert (generated_dir / "tests" / "setup.ts").is_file()
    assert result["task_instruction"]["domain"] == "frontend"
    assert result["sa_contract"]["api_client_needs"] == ["GET /todos"]
    assert result["generation_policy"]["no_dummy_code"] is True
    assert result["contract_enforcement"]["status"] == "passed"


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


def test_semantic_slicing_extracts_focused_context(tmp_path: Path) -> None:
    output_dir = tmp_path / "generated"
    source = output_dir / "src" / "service.ts"
    source.parent.mkdir(parents=True)
    source.write_text("\n".join(f"const value{index} = {index};" for index in range(1, 121)), encoding="utf-8")
    verification = {
        "checks": [{
            "name": "typecheck",
            "stderr_tail": "src/service.ts(75,10): error TS2304: Cannot find name 'missing'.",
        }]
    }

    slices = _semantic_slices(output_dir, verification)
    assert slices[0]["path"] == "src/service.ts"
    assert slices[0]["line"] == 75
    assert slices[0]["end_line"] - slices[0]["start_line"] + 1 <= 50


def test_frontend_codegen_llm_mode_normalizes_manifests_and_tests(monkeypatch, tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")

    import pipeline.domain.dev.nodes.frontend_codegen as frontend_codegen
    from pipeline.domain.dev.schemas import FrontendCodegenOutput, GeneratedCodeFile

    called = {}

    def fake_call_structured(**kwargs):
        called["user_msg"] = kwargs["user_msg"]
        parsed = FrontendCodegenOutput(
            thinking="frontend",
            language="typescript",
            framework="react-vite",
            files=[
                GeneratedCodeFile(
                    path="package.json",
                    content='{"type":"module","scripts":{"test":"vitest"},"dependencies":{"react":"^18.0.0"},"devDependencies":{"vitest":"^1.0.0"}}',
                ),
                GeneratedCodeFile(
                    path="tsconfig.json",
                    content='{"compilerOptions":{"strict":true,"noUnusedLocals":true},"include":["src"]}',
                ),
                GeneratedCodeFile(
                    path="src/App.tsx",
                    content="export default function App() { return <h1>LLM App</h1>; }\n",
                ),
                GeneratedCodeFile(
                    path="src/App.test.tsx",
                    content="it('expects stale text', () => {});\n",
                ),
            ],
            test_command="npm test",
        )
        return SimpleNamespace(parsed=parsed)

    monkeypatch.setattr(frontend_codegen, "call_structured", fake_call_structured)

    result = develop_frontend_codegen_node({
        "source_dir": str(target_repo),
        "api_key": "test-key",
        "model": "test-model",
        "enable_frontend_codegen": True,
        "frontend_codegen_mode": "llm",
        "approved_stack": [{"domain": "Frontend", "package": "react", "status": "APPROVED"}],
        "frontend_task_spec": {"requirement_ids": ["REQ_1"], "target_components": ["Home"]},
        "frontend_result": {"frontend_plan": {"routes": ["/"], "api_client_needs": []}},
        "uiux_artifact": {"screens": [{"name": "Home", "route": "/", "states": ["default"]}]},
    })["frontend_codegen_result"]

    generated_dir = target_repo / "frontend" / "generated" / "navigator_dev" / "typescript_react_vite"
    assert result["generator"] == "llm"
    assert "react-router-dom" in (generated_dir / "package.json").read_text(encoding="utf-8")
    assert "noUnusedLocals" in (generated_dir / "tsconfig.json").read_text(encoding="utf-8")
    assert not (generated_dir / "src" / "App.test.tsx").exists()
    assert "renders generated frontend without crashing" in (
        generated_dir / "tests" / "App.test.tsx"
    ).read_text(encoding="utf-8")
    assert result["approved_stack"]["packages"] == ["react"]
    assert result["task_instruction"]["requirement_ids"] == ["REQ_1"]
    assert result["contract_enforcement"]["status"] == "passed"
    assert '"approved_stack"' in called["user_msg"]
    assert '"generation_policy"' in called["user_msg"]
    assert '"dev_task"' in called["user_msg"]


def test_frontend_codegen_llm_mode_rejects_placeholder_policy_violation(monkeypatch, tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")

    import pipeline.domain.dev.nodes.frontend_codegen as frontend_codegen
    from pipeline.domain.dev.schemas import FrontendCodegenOutput, GeneratedCodeFile

    def fake_call_structured(**kwargs):
        parsed = FrontendCodegenOutput(
            thinking="placeholder",
            language="typescript",
            framework="react-vite",
            files=[
                GeneratedCodeFile(
                    path="src/App.tsx",
                    content="export default function App() { return <div>TODO placeholder</div>; }\n",
                ),
            ],
        )
        return SimpleNamespace(parsed=parsed)

    monkeypatch.setattr(frontend_codegen, "call_structured", fake_call_structured)

    result = develop_frontend_codegen_node({
        "source_dir": str(target_repo),
        "api_key": "test-key",
        "model": "test-model",
        "enable_frontend_codegen": True,
        "frontend_codegen_mode": "llm",
        "frontend_result": {"frontend_plan": {"routes": ["/"], "api_client_needs": []}},
        "uiux_artifact": {"screens": [{"name": "Home", "route": "/", "states": ["default"]}]},
    })["frontend_codegen_result"]

    assert result["status"] == "error"
    assert result["contract_enforcement"]["status"] == "failed"
    assert any("placeholder" in finding.lower() for finding in result["contract_enforcement"]["findings"])


def test_frontend_codegen_llm_mode_refuses_blank_fallback(monkeypatch, tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")

    import pipeline.domain.dev.nodes.frontend_codegen as frontend_codegen
    from pipeline.domain.dev.schemas import FrontendCodegenOutput, GeneratedCodeFile

    def fake_call_structured(**kwargs):
        parsed = FrontendCodegenOutput(
            thinking="blank",
            language="typescript",
            framework="react-vite",
            files=[GeneratedCodeFile(path="src/App.tsx", content="")],
        )
        return SimpleNamespace(parsed=parsed)

    monkeypatch.setattr(frontend_codegen, "call_structured", fake_call_structured)

    result = develop_frontend_codegen_node({
        "source_dir": str(target_repo),
        "api_key": "test-key",
        "model": "test-model",
        "enable_frontend_codegen": True,
        "frontend_codegen_mode": "llm",
        "frontend_result": {"frontend_plan": {"routes": ["/"], "api_client_needs": []}},
        "uiux_artifact": {"screens": [{"name": "Home", "route": "/", "states": ["default"]}]},
    })["frontend_codegen_result"]

    assert result["status"] == "error"
    assert result["generator"] == "llm"
    assert "blank required files" in result["reason"]


def test_frontend_codegen_llm_mode_ignores_optional_blank_files(monkeypatch, tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")

    import pipeline.domain.dev.nodes.frontend_codegen as frontend_codegen
    from pipeline.domain.dev.schemas import FrontendCodegenOutput, GeneratedCodeFile

    def fake_call_structured(**kwargs):
        parsed = FrontendCodegenOutput(
            thinking="optional",
            language="typescript",
            framework="react-vite",
            files=[
                GeneratedCodeFile(path="src/App.tsx", content="export default function App() { return <h1>LLM App</h1>; }\n"),
                GeneratedCodeFile(path="src/empty.css", content=""),
            ],
        )
        return SimpleNamespace(parsed=parsed)

    monkeypatch.setattr(frontend_codegen, "call_structured", fake_call_structured)

    result = develop_frontend_codegen_node({
        "source_dir": str(target_repo),
        "api_key": "test-key",
        "model": "test-model",
        "enable_frontend_codegen": True,
        "frontend_codegen_mode": "llm",
        "frontend_result": {"frontend_plan": {"routes": ["/"], "api_client_needs": []}},
        "uiux_artifact": {"screens": [{"name": "Home", "route": "/", "states": ["default"]}]},
    })["frontend_codegen_result"]

    generated_dir = target_repo / "frontend" / "generated" / "navigator_dev" / "typescript_react_vite"
    assert result["status"] == "generated"
    assert not (generated_dir / "src" / "empty.css").exists()
    assert any("blank file entries" in note for note in result["notes"])


def test_frontend_codegen_verifier_skips_without_node_modules(tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")
    codegen = develop_frontend_codegen_node({
        "source_dir": str(target_repo),
        "enable_frontend_codegen": True,
        "frontend_codegen_mode": "template",
        "frontend_result": {"frontend_plan": {"routes": ["/"], "api_client_needs": []}},
        "uiux_artifact": {"screens": [{"name": "Home", "route": "/", "states": ["default"]}]},
    })["frontend_codegen_result"]

    result = develop_frontend_codegen_verifier_node({"frontend_codegen_result": codegen})["frontend_codegen_verification"]

    assert result["status"] == "skipped"
    assert result["skipped_reason"] == "node_modules not found"


def test_frontend_codegen_routes_failed_result_through_repair_loop() -> None:
    assert _route_frontend_codegen_verification({
        "frontend_codegen_result": {"status": "error"},
        "frontend_codegen_verification": {"status": "skipped"},
    }) == "block"
    assert _route_frontend_codegen_verification({"frontend_codegen_verification": {"status": "failed"}}) == "repair"
    assert _route_frontend_codegen_verification({"frontend_codegen_verification": {"status": "passed"}}) == "pass"
    assert _route_frontend_codegen_repair({"frontend_codegen_repair_result": {"status": "repaired"}}) == "reverify"
    assert _route_frontend_codegen_repair({"frontend_codegen_repair_result": {"status": "error"}}) == "block"
    assert _route_frontend_codegen_reverification({"frontend_codegen_reverify_result": {"status": "failed"}}) == "block"
    assert _route_frontend_codegen_reverification({"frontend_codegen_reverify_result": {"status": "skipped"}}) == "pass"


def test_frontend_runtime_blocker_reports_codegen_error() -> None:
    result = develop_frontend_runtime_blocker_node({
        "frontend_codegen_result": {
            "status": "error",
            "reason": "LLM frontend codegen returned only blank files.",
        },
        "frontend_codegen_verification": {"status": "skipped", "failed_checks": []},
    })

    assert result["integration_qa_result"]["status"] == "blocked"
    assert "Frontend codegen failed" in result["integration_qa_result"]["findings"][0]


def test_frontend_codegen_repair_writes_generated_frontend_files(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "frontend"
    (output_dir / "src").mkdir(parents=True)
    (output_dir / "tests").mkdir(parents=True)
    (output_dir / "vite.config.ts").write_text(
        "export default { test: { environment: 'jsdom', globals: true } };\n",
        encoding="utf-8",
    )
    (output_dir / "src" / "api.ts").write_text(
        "export const base = import.meta.env.VITE_API_BASE_URL;\n",
        encoding="utf-8",
    )

    import pipeline.domain.dev.nodes.frontend_codegen_verifier as verifier
    from pipeline.domain.dev.schemas import BackendCodegenRepairOutput, GeneratedCodeFile

    def fake_call_structured(**kwargs):
        parsed = BackendCodegenRepairOutput(
            thinking="프론트수정",
            summary="Registered Vitest setup and Vite env types.",
            files=[
                GeneratedCodeFile(
                    path="vite.config.ts",
                    content=(
                        "export default { test: { environment: 'jsdom', globals: true, "
                        "setupFiles: './tests/setup.ts' } };\n"
                    ),
                ),
                GeneratedCodeFile(
                    path="src/vite-env.d.ts",
                    content="/// <reference types=\"vite/client\" />\n",
                ),
            ],
        )
        return SimpleNamespace(parsed=parsed)

    monkeypatch.setattr(verifier, "call_structured", fake_call_structured)

    result = develop_frontend_codegen_repair_node({
        "api_key": "",
        "model": "test-model",
        "frontend_codegen_result": {
            "status": "generated",
            "language": "typescript",
            "framework": "react-vite",
            "output_dir": str(output_dir),
        },
        "frontend_codegen_verification": {
            "status": "failed",
            "failed_checks": ["test", "typecheck"],
            "checks": [
                {"name": "test", "status": "failed", "stderr_tail": "Invalid Chai property: toBeInTheDocument"},
                {"name": "typecheck", "status": "failed", "stderr_tail": "Property 'env' does not exist on type 'ImportMeta'"},
            ],
        },
    })["frontend_codegen_repair_result"]

    assert result["status"] == "repaired"
    assert "setupFiles" in (output_dir / "vite.config.ts").read_text(encoding="utf-8")
    assert (output_dir / "src" / "vite-env.d.ts").read_text(encoding="utf-8").strip() == '/// <reference types="vite/client" />'


def test_repair_context_extracts_failed_typescript_file_paths() -> None:
    verification = {
        "checks": [
            {
                "name": "typecheck",
                "stdout_tail": "src/api/client.ts(1,22): error TS2693: 'ImportMeta' only refers to a type.",
                "stderr_tail": "",
            }
        ]
    }

    assert _extract_failed_file_paths(verification) == ["src/api/client.ts"]


def test_branch_pr_orchestrator_uses_source_dir(tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")
    outside_repo = _init_git_repo(tmp_path / "outside")

    state = {
        **_base_state(target_repo),
        "develop_main_plan": {
            "branch_strategy": {
                "base_branch": "develop",
                "domain_branches": [{"domain": "backend", "branch": "feature/login-backend"}],
            }
        },
        "backend_domain_gate_result": {"status": "pass"},
        "frontend_domain_gate_result": {"status": "pass"},
        "uiux_domain_gate_result": {"status": "pass"},
        "global_fe_sync_result": {"status": "pass"},
        "integration_qa_result": {"status": "pass"}, # 통합 QA 통과 전제
    }

    previous_cwd = Path.cwd()
    try:
        # The orchestrator must operate on source_dir, not the process cwd.
        import os

        os.chdir(outside_repo)
        result = develop_branch_pr_orchestrator_node(state)["branch_pr_result"]
    finally:
        os.chdir(previous_cwd)

    branches = subprocess.run(
        ["git", "branch", "--list", "feature/login-backend"],
        cwd=target_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    outside_branches = subprocess.run(
        ["git", "branch", "--list", "feature/login-backend"],
        cwd=outside_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert "feature/login-backend" in branches
    assert "feature/login-backend" not in outside_branches
    assert result["merge_ready"] is True
    assert Path(result["pr_drafts"][0]["draft_path"]).is_file()


def test_backend_codegen_writes_generated_backend_scaffold(tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")
    result = develop_backend_codegen_node({
        **_base_state(target_repo),
        "enable_backend_codegen": True,
        "backend_codegen_mode": "template",
    })["backend_codegen_result"]

    generated_dir = target_repo / "backend" / "generated" / "navigator_dev" / "python_fastapi"
    package_dir = generated_dir / "navigator_dev"
    assert result["status"] == "generated"
    assert result["language"] == "python"
    assert result["framework"] == "fastapi"
    assert result["generator"] == "template"
    assert (package_dir / "router.py").is_file()
    assert (package_dir / "schemas.py").is_file()
    assert (package_dir / "service.py").is_file()
    py_compile.compile(package_dir / "router.py", doraise=True)
    py_compile.compile(package_dir / "schemas.py", doraise=True)
    py_compile.compile(package_dir / "service.py", doraise=True)
    assert "POST /api/auth/login" in (package_dir / "README.md").read_text(encoding="utf-8")


def test_backend_codegen_supports_typescript_express_target(tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")
    result = develop_backend_codegen_node({
        **_base_state(target_repo),
        "enable_backend_codegen": True,
        "backend_codegen_language": "typescript",
        "backend_codegen_framework": "express",
        "backend_codegen_mode": "template",
    })["backend_codegen_result"]

    generated_dir = target_repo / "backend" / "generated" / "navigator_dev" / "typescript_express"
    assert result["status"] == "generated"
    assert result["language"] == "typescript"
    assert result["framework"] == "express"
    assert result["support_level"] == "official"
    assert result["verification_adapter"] == "node"
    assert (generated_dir / "src" / "routes.ts").is_file()
    assert (generated_dir / "src" / "service.ts").is_file()
    assert (generated_dir / "tests" / "generated-backend.test.ts").is_file()
    assert result["sa_contract"]["apis"][0]["endpoint"] == "POST /api/auth/login"
    assert result["task_instruction"]["domain"] == "backend"
    assert result["contract_enforcement"]["status"] == "passed"
    assert "express" in (generated_dir / "package.json").read_text(encoding="utf-8")


def test_backend_codegen_prefers_contract_handoff_and_approved_stack(tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")
    result = develop_backend_codegen_node({
        **_base_state(target_repo),
        "enable_backend_codegen": True,
        "backend_codegen_language": "typescript",
        "backend_codegen_framework": "express",
        "backend_codegen_mode": "template",
        "pm_bundle": {
            "data": {
                "tech_stacks": [
                    {"feature_id": "FEAT_MSG", "domain": "Backend", "pkg": "express", "status": "APPROVED"},
                    {"feature_id": "FEAT_MSG", "domain": "Frontend", "pkg": "react", "status": "APPROVED"},
                ]
            }
        },
        "backend_task_spec": {
            "goal": "Implement messages API",
            "requirement_ids": ["FEAT_MSG"],
            "acceptance_criteria": ["Messages can be submitted."],
        },
        "backend_result": {
            "contract_handoff": {
                "apis": [{"endpoint": "POST /messages", "request": {"fields": ["senderName", "content"]}}],
                "tables": [{"table_name": "messages", "columns": [{"name": "senderName"}, {"name": "content"}]}],
                "components": [{"name": "MessageService"}],
                "topology_queue": [{"order": 1, "kind": "table", "name": "messages"}],
            }
        },
    })["backend_codegen_result"]

    generated_dir = target_repo / "backend" / "generated" / "navigator_dev" / "typescript_express"
    assert result["status"] == "generated"
    assert result["approved_stack"]["packages"] == ["express"]
    assert result["sa_contract"]["apis"][0]["endpoint"] == "POST /messages"
    assert result["task_instruction"]["requirement_ids"] == ["FEAT_MSG"]
    assert "POST /messages" in (generated_dir / "README.md").read_text(encoding="utf-8")


def test_backend_codegen_prefers_dev_task_contract_context(tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")
    result = develop_backend_codegen_node({
        **_base_state(target_repo),
        "enable_backend_codegen": True,
        "backend_codegen_language": "typescript",
        "backend_codegen_framework": "express",
        "backend_codegen_mode": "template",
        "backend_task_spec": {
            "requirement_ids": ["FEAT_DEV"],
            "dev_task": {
                "task_info": {"task_id": "task_FEAT_DEV_BACKEND_01", "target_agent": "BackendAgent", "feature_id": "FEAT_DEV"},
                "context": {
                    "approved_stack": {"packages": ["express"]},
                    "target_api_specs": [{"endpoint": "POST /dev-task-api"}],
                    "target_table_specs": [{"table_name": "dev_task_rows"}],
                    "component_specs": [{"name": "DevTaskService"}],
                },
                "constraints": {"no_dummy_code": True},
            },
        },
        "backend_result": {"contract_handoff": {"apis": [{"endpoint": "GET /legacy"}], "tables": []}},
    })["backend_codegen_result"]

    assert result["status"] == "generated"
    assert result["sa_contract"]["apis"][0]["endpoint"] == "POST /dev-task-api"
    assert result["approved_stack"]["packages"] == ["express"]
    assert result["task_instruction"]["dev_task"]["task_info"]["task_id"] == "task_FEAT_DEV_BACKEND_01"


def test_backend_codegen_refuses_missing_sa_api_contract(tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")
    result = develop_backend_codegen_node({
        **_base_state(target_repo),
        "apis": [],
        "previous_result": {},
        "sa_arch_bundle": {},
        "sa_artifacts": {},
        "backend_result": {"contract_handoff": {"apis": [], "tables": []}},
        "enable_backend_codegen": True,
        "backend_codegen_mode": "template",
    })["backend_codegen_result"]

    assert result["status"] == "error"
    assert "refuses to invent APIs" in result["reason"]


def test_backend_codegen_supports_java_spring_boot_target(tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")
    result = develop_backend_codegen_node({
        **_base_state(target_repo),
        "enable_backend_codegen": True,
        "backend_codegen_language": "java",
        "backend_codegen_framework": "spring-boot",
        "backend_codegen_mode": "template",
    })["backend_codegen_result"]

    generated_dir = target_repo / "backend" / "generated" / "navigator_dev" / "java_spring_boot"
    assert result["status"] == "generated"
    assert result["language"] == "java"
    assert result["framework"] == "spring-boot"
    assert result["support_level"] == "official"
    assert result["verification_adapter"] == "java"
    assert result["test_command"] == "mvn test"
    assert (generated_dir / "pom.xml").is_file()
    assert (generated_dir / "src" / "main" / "java" / "com" / "navigator" / "generated" / "GeneratedApplication.java").is_file()
    assert (generated_dir / "src" / "test" / "java" / "com" / "navigator" / "generated" / "GeneratedControllerTest.java").is_file()


def test_backend_codegen_marks_unknown_target_as_experimental(tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")
    result = develop_backend_codegen_node({
        **_base_state(target_repo),
        "enable_backend_codegen": True,
        "backend_codegen_language": "go",
        "backend_codegen_framework": "gin",
        "backend_codegen_mode": "template",
    })["backend_codegen_result"]

    assert result["support_level"] == "experimental"
    assert result["verification_adapter"] == "unknown"


def test_backend_codegen_uses_llm_when_api_key_is_present(monkeypatch, tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")

    import pipeline.domain.dev.nodes.backend_codegen as backend_codegen
    from pipeline.domain.dev.schemas import BackendCodegenOutput, GeneratedCodeFile

    def fake_call_structured(**kwargs):
        parsed = BackendCodegenOutput(
            thinking="코드생성",
            language="typescript",
            framework="express",
            files=[
                GeneratedCodeFile(
                    path="src/custom.ts",
                    content="export const generated = 'POST /api/auth/login';\n",
                    purpose="custom generated file",
                )
            ],
            test_command="npm test",
            notes=["llm path used"],
        )
        return SimpleNamespace(parsed=parsed)

    monkeypatch.setattr(backend_codegen, "call_structured", fake_call_structured)

    result = develop_backend_codegen_node({
        **_base_state(target_repo),
        "api_key": "test-key",
        "model": "test-model",
        "enable_backend_codegen": True,
        "backend_codegen_language": "typescript",
        "backend_codegen_framework": "express",
    })["backend_codegen_result"]

    generated_dir = target_repo / "backend" / "generated" / "navigator_dev" / "typescript_express"
    assert result["generator"] == "llm"
    assert result["support_level"] == "official"
    assert result["verification_adapter"] == "node"
    assert result["test_command"] == "npm test"
    assert (generated_dir / "src" / "custom.ts").read_text(encoding="utf-8") == "export const generated = 'POST /api/auth/login';\n"


def test_backend_codegen_llm_mode_uses_env_fallback_with_empty_api_key(monkeypatch, tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")

    import pipeline.domain.dev.nodes.backend_codegen as backend_codegen
    from pipeline.domain.dev.schemas import BackendCodegenOutput, GeneratedCodeFile

    called = {}

    def fake_call_structured(**kwargs):
        called["api_key"] = kwargs["api_key"]
        parsed = BackendCodegenOutput(
            thinking="환경키",
            language="typescript",
            framework="express",
            files=[GeneratedCodeFile(path="src/env-fallback.ts", content="export const envFallback = 'POST /api/auth/login';\n")],
        )
        return SimpleNamespace(parsed=parsed)

    monkeypatch.setattr(backend_codegen, "call_structured", fake_call_structured)

    result = develop_backend_codegen_node({
        **_base_state(target_repo),
        "api_key": "",
        "model": "test-model",
        "enable_backend_codegen": True,
        "backend_codegen_language": "typescript",
        "backend_codegen_framework": "express",
        "backend_codegen_mode": "llm",
    })["backend_codegen_result"]

    generated_file = (
        target_repo
        / "backend"
        / "generated"
        / "navigator_dev"
        / "typescript_express"
        / "src"
        / "env-fallback.ts"
    )
    assert called["api_key"] == ""
    assert result["generator"] == "llm"
    assert generated_file.is_file()


def test_backend_codegen_llm_mode_refuses_blank_fallback(monkeypatch, tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")

    import pipeline.domain.dev.nodes.backend_codegen as backend_codegen
    from pipeline.domain.dev.schemas import BackendCodegenOutput, GeneratedCodeFile

    def fake_call_structured(**kwargs):
        parsed = BackendCodegenOutput(
            thinking="blank",
            language="typescript",
            framework="express",
            files=[GeneratedCodeFile(path="src/index.ts", content="")],
        )
        return SimpleNamespace(parsed=parsed)

    monkeypatch.setattr(backend_codegen, "call_structured", fake_call_structured)

    result = develop_backend_codegen_node({
        **_base_state(target_repo),
        "api_key": "test-key",
        "model": "test-model",
        "enable_backend_codegen": True,
        "backend_codegen_language": "typescript",
        "backend_codegen_framework": "express",
        "backend_codegen_mode": "llm",
    })["backend_codegen_result"]

    assert result["status"] == "error"
    assert result["generator"] == "llm"
    assert "blank files" in result["reason"]


def test_backend_codegen_verifier_skips_node_target_without_dependencies(tmp_path: Path) -> None:
    output_dir = tmp_path / "generated"
    output_dir.mkdir()
    (output_dir / "package.json").write_text(
        '{"scripts":{"test":"jest"},"devDependencies":{"jest":"^29.0.0"}}',
        encoding="utf-8",
    )

    result = develop_backend_codegen_verifier_node({
        "backend_codegen_result": {
            "status": "generated",
            "language": "typescript",
            "framework": "express",
            "output_dir": str(output_dir),
        }
    })["backend_codegen_verification"]

    assert result["status"] == "skipped"
    assert result["skipped_reason"] == "node_modules not found"
    assert result["dependency_install_plan"][0]["command"] == "npm install"
    assert result["dependency_install_plan"][0]["requires_user_approval"] is True


def test_backend_codegen_verifier_installs_dependencies_when_enabled(tmp_path: Path, monkeypatch) -> None:
    import pipeline.domain.dev.nodes.backend_codegen_verifier as verifier

    output_dir = tmp_path / "generated"
    output_dir.mkdir()
    (output_dir / "package.json").write_text('{"scripts":{}}', encoding="utf-8")

    def fake_install(path: Path):
        (path / "node_modules").mkdir()
        return verifier.BackendCodegenVerificationCheck(
            name="dependency_install",
            status="passed",
            command=["npm", "install"],
            returncode=0,
        )

    monkeypatch.setattr(verifier, "_install_node_dependencies", fake_install)

    result = develop_backend_codegen_verifier_node({
        "enable_dependency_install": True,
        "backend_codegen_result": {
            "status": "generated",
            "language": "typescript",
            "framework": "express",
            "output_dir": str(output_dir),
        },
    })["backend_codegen_verification"]

    assert result["dependency_install_plan"][0]["command"] == "npm install"
    assert result["dependency_install_result"]["status"] == "passed"


def test_backend_codegen_verifier_reinstalls_when_manifest_is_newer(tmp_path: Path, monkeypatch) -> None:
    import os
    import pipeline.domain.dev.nodes.backend_codegen_verifier as verifier

    output_dir = tmp_path / "generated"
    output_dir.mkdir()
    node_modules = output_dir / "node_modules"
    node_modules.mkdir()
    package_json = output_dir / "package.json"
    package_json.write_text('{"scripts":{}}', encoding="utf-8")

    old = package_json.stat().st_mtime - 10
    os.utime(node_modules, (old, old))

    called = {"install": False}

    def fake_install(path: Path):
        called["install"] = True
        return verifier.BackendCodegenVerificationCheck(
            name="dependency_install",
            status="passed",
            command=["npm", "install"],
            returncode=0,
        )

    monkeypatch.setattr(verifier, "_install_node_dependencies", fake_install)

    result = develop_backend_codegen_verifier_node({
        "enable_dependency_install": True,
        "backend_codegen_result": {
            "status": "generated",
            "language": "typescript",
            "framework": "express",
            "output_dir": str(output_dir),
        },
    })["backend_codegen_verification"]

    assert called["install"] is True
    assert result["dependency_install_result"]["status"] == "passed"


def test_backend_codegen_verifier_detects_node_target_from_package_json(tmp_path: Path) -> None:
    output_dir = tmp_path / "generated"
    output_dir.mkdir()
    (output_dir / "package.json").write_text('{"scripts":{"test":"node test.js"}}', encoding="utf-8")

    result = develop_backend_codegen_verifier_node({
        "backend_codegen_result": {
            "status": "generated",
            "language": "",
            "framework": "",
            "output_dir": str(output_dir),
        }
    })["backend_codegen_verification"]

    assert result["status"] == "skipped"
    assert result["skipped_reason"] == "node_modules not found"


def test_frontend_codegen_reverifier_reuses_verifier_with_context(tmp_path: Path) -> None:
    output_dir = tmp_path / "frontend"
    output_dir.mkdir()
    (output_dir / "package.json").write_text('{"scripts":{"test":"vitest"},"devDependencies":{"vitest":"^1.0.0"}}', encoding="utf-8")

    result = develop_frontend_codegen_reverifier_node({
        "frontend_codegen_result": {
            "status": "generated",
            "output_dir": str(output_dir),
        }
    })

    assert result["frontend_codegen_reverify_result"]["status"] == "skipped"
    assert result["frontend_codegen_verification"]["skipped_reason"] == "node_modules not found"


def test_backend_codegen_verifier_runs_python_compile(tmp_path: Path) -> None:
    output_dir = tmp_path / "generated"
    package_dir = output_dir / "navigator_dev"
    package_dir.mkdir(parents=True)
    (package_dir / "service.py").write_text("VALUE = 1\n", encoding="utf-8")

    result = develop_backend_codegen_verifier_node({
        "backend_codegen_result": {
            "status": "generated",
            "language": "python",
            "framework": "fastapi",
            "output_dir": str(output_dir),
        }
    })["backend_codegen_verification"]

    assert result["status"] == "passed"
    assert result["checks"][0]["name"] == "py_compile"


def test_backend_codegen_verifier_supports_java_adapter_without_build_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "generated"
    output_dir.mkdir()

    result = develop_backend_codegen_verifier_node({
        "backend_codegen_result": {
            "status": "generated",
            "language": "java",
            "framework": "spring-boot",
            "output_dir": str(output_dir),
        }
    })["backend_codegen_verification"]

    assert result["status"] == "skipped"
    assert "Java" in result["skipped_reason"]


def test_backend_codegen_verifier_supports_c_family_adapter_without_build_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "generated"
    output_dir.mkdir()

    result = develop_backend_codegen_verifier_node({
        "backend_codegen_result": {
            "status": "generated",
            "language": "c",
            "framework": "",
            "output_dir": str(output_dir),
        }
    })["backend_codegen_verification"]

    assert result["status"] == "skipped"
    assert "C/C++" in result["skipped_reason"]


def test_backend_codegen_verification_routes_failed_result_to_block() -> None:
    assert _route_backend_codegen_verification({"backend_codegen_verification": {"status": "failed"}}) == "repair"
    assert _route_backend_codegen_verification({"backend_codegen_verification": {"status": "passed"}}) == "pass"
    assert _route_backend_codegen_verification({"backend_codegen_verification": {"status": "skipped"}}) == "pass"


def test_static_qa_recheck_routes_before_runtime_verification() -> None:
    assert _route_backend_static_qa_recheck({"backend_qa_result": {"status": "pass"}}) == "pass"
    assert _route_backend_static_qa_recheck({
        "backend_qa_result": {"status": "rework"},
        "backend_static_qa_recheck_count": 1,
    }) == "rework"
    assert _route_backend_static_qa_recheck({
        "backend_qa_result": {"status": "rework"},
        "backend_static_qa_recheck_count": 2,
    }) == "block"
    assert _route_frontend_static_qa_recheck({"frontend_qa_result": {"status": "pass"}}) == "pass"
    assert _route_frontend_static_qa_recheck({
        "frontend_qa_result": {"status": "rework"},
        "frontend_static_qa_recheck_count": 1,
    }) == "rework"
    assert _route_frontend_static_qa_recheck({
        "frontend_qa_result": {"status": "rework"},
        "frontend_static_qa_recheck_count": 2,
    }) == "block"


def test_backend_codegen_repair_routes_to_reverify_or_block() -> None:
    assert _route_backend_codegen_repair({"backend_codegen_repair_result": {"status": "repaired"}}) == "reverify"
    assert _route_backend_codegen_repair({"backend_codegen_repair_result": {"status": "no_changes"}}) == "reverify"
    assert _route_backend_codegen_repair({"backend_codegen_repair_result": {"status": "error"}}) == "block"
    assert _route_backend_codegen_reverification({"backend_codegen_reverify_result": {"status": "failed"}}) == "block"
    assert _route_backend_codegen_reverification({"backend_codegen_reverify_result": {"status": "passed"}}) == "pass"


def test_backend_codegen_repair_writes_only_generated_files(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "generated"
    (output_dir / "src").mkdir(parents=True)
    (output_dir / "src" / "app.ts").write_text("export const broken = true;\n", encoding="utf-8")

    import pipeline.domain.dev.nodes.backend_codegen_verifier as verifier
    from pipeline.domain.dev.schemas import BackendCodegenRepairOutput, GeneratedCodeFile

    def fake_call_structured(**kwargs):
        parsed = BackendCodegenRepairOutput(
            thinking="수정",
            summary="Fixed app export",
            files=[
                GeneratedCodeFile(
                    path="src/app.ts",
                    content="export const fixed = true;\n",
                )
            ],
        )
        return SimpleNamespace(parsed=parsed)

    monkeypatch.setattr(verifier, "call_structured", fake_call_structured)

    result = develop_backend_codegen_repair_node({
        "api_key": "",
        "model": "test-model",
        "backend_codegen_result": {
            "status": "generated",
            "language": "typescript",
            "framework": "express",
            "output_dir": str(output_dir),
        },
        "backend_codegen_verification": {
            "status": "failed",
            "failed_checks": ["typecheck"],
            "checks": [{"name": "typecheck", "status": "failed", "stderr_tail": "compile error"}],
        },
    })["backend_codegen_repair_result"]

    assert result["status"] == "repaired"
    assert (output_dir / "src" / "app.ts").read_text(encoding="utf-8") == "export const fixed = true;\n"


def test_backend_runtime_blocker_stops_downstream_work() -> None:
    result = develop_backend_runtime_blocker_node({
        "backend_codegen_verification": {
            "status": "failed",
            "failed_checks": ["test"],
            "checks": [
                {
                    "name": "test",
                    "status": "failed",
                    "stderr_tail": "Expected 200, received 500",
                }
            ],
        }
    })

    assert result["develop_next_action"] == "blocked_backend_runtime_qa"
    assert result["frontend_result"]["status"] == "skipped"
    assert result["integration_qa_result"]["status"] == "blocked"
    assert result["integration_qa_result"]["rework_targets"] == ["backend"]
    assert result["branch_pr_result"]["merge_ready"] is False

# --- 통합 및 시스템 테스트: 전체 파이프라인 흐름 검증 ---

def test_develop_pipeline_fallback_end_to_end(monkeypatch, tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")

    import pipeline.domain.dev.nodes.main_agent as main_agent
    import pipeline.domain.dev.nodes.embedding as embedding

    monkeypatch.setattr(
        main_agent,
        "_load_project_rag_context",
        lambda goal, source_session_id, requirements, components: {
            "session_id": source_session_id,
            "query": goal,
            "hits": 0,
            "chunks": [],
        },
    )
    monkeypatch.setattr(
        main_agent,
        "_load_artifact_rag_context",
        lambda source_session_id: {
            "session_id": source_session_id,
            "artifact_count": 0,
            "artifacts": [],
        },
    )
    monkeypatch.setattr(
        embedding,
        "upsert_pm_artifact",
        lambda **kwargs: kwargs["chunk_id"],
    )

    result = execute_pipeline(
        get_develop_pipeline(),
        {
            **_base_state(target_repo),
            "enable_backend_codegen": True,
            "enable_frontend_codegen": True,
            "backend_codegen_mode": "template",
            "frontend_codegen_mode": "template",
            # 각 검사 단계에서 'Pass' 판정을 받기 위한 상태 데이터 주입
            "uiux_result": {"status": "success"},
            "uiux_artifact": {"status": "ready_for_frontend"},
            "uiux_qa_result": {"status": "pass"},
            "uiux_domain_gate_result": {"status": "pass"},
            "backend_result": {"status": "success"},
            "backend_codegen_result": {"status": "generated", "output_dir": str(tmp_path / "be")},
            "backend_qa_result": {"status": "pass"},
            "backend_domain_gate_result": {"status": "pass"},
            "backend_codegen_verification": {"status": "passed"},
            "frontend_result": {"status": "success"},
            "frontend_codegen_result": {"status": "generated", "output_dir": str(tmp_path / "fe")},
            "frontend_qa_result": {"status": "pass"},
            "frontend_domain_gate_result": {"status": "pass"},
            "frontend_codegen_verification": {"status": "passed"},
            "global_fe_sync_result": {"status": "pass"},
            "fullstack_runtime_verification": {"status": "passed"},
            "integration_qa_result": {"status": "pass"},
        },
        "develop_plan",
    )
    assert result.success, result.error
    data = result.data
    assert data["pipeline_type"] == "develop_plan"
    assert data["develop_overview"]["goal"]
    assert data["develop_overview"]["branch_pr_status"] == "ready"
    assert data["branch_pr_result"]["merge_ready"] is True
    assert data["embedding_result"]["status"] == "persisted"
