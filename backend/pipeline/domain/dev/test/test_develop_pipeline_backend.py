from __future__ import annotations

import subprocess
import py_compile
from types import SimpleNamespace
from pathlib import Path

from orchestration.executor import execute_pipeline
from pipeline.domain.dev.nodes.backend_codegen import develop_backend_codegen_node
from pipeline.domain.dev.nodes.backend_codegen_verifier import (
    _extract_failed_file_paths,
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
from pipeline.orchestration.aux_graphs import (
    _route_backend_codegen_repair,
    _route_backend_codegen_reverification,
    _route_backend_codegen_verification,
    _route_frontend_codegen_repair,
    _route_frontend_codegen_reverification,
    _route_frontend_codegen_verification,
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
    assert (generated_dir / "src" / "App.tsx").is_file()
    assert (generated_dir / "src" / "api" / "client.ts").is_file()
    assert (generated_dir / "tests" / "App.test.tsx").is_file()
    assert (generated_dir / "tests" / "setup.ts").is_file()


def test_frontend_codegen_llm_mode_normalizes_manifests_and_tests(monkeypatch, tmp_path: Path) -> None:
    target_repo = _init_git_repo(tmp_path / "target")

    import pipeline.domain.dev.nodes.frontend_codegen as frontend_codegen
    from pipeline.domain.dev.schemas import FrontendCodegenOutput, GeneratedCodeFile

    def fake_call_structured(**kwargs):
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
    assert "express" in (generated_dir / "package.generated.json").read_text(encoding="utf-8")


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
                    content="export const generated = true;\n",
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
    assert (generated_dir / "src" / "custom.ts").read_text(encoding="utf-8") == "export const generated = true;\n"


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
            files=[GeneratedCodeFile(path="src/env-fallback.ts", content="export const envFallback = true;\n")],
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
        _base_state(target_repo),
        "develop_plan",
    )

    assert result.success, result.error
    data = result.data
    assert data["pipeline_type"] == "develop_plan"
    assert data["develop_overview"]["goal"]
    assert data["develop_overview"]["branch_pr_status"] == "ready"
    assert data["branch_pr_result"]["merge_ready"] is True
    assert data["embedding_result"]["status"] == "persisted"
