from __future__ import annotations

from pipeline.domain.dev.test.fixtures import *


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
