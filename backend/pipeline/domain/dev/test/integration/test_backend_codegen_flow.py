from __future__ import annotations

from pipeline.domain.dev.test.fixtures import *


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


def test_backend_codegen_verification_routes_failed_and_unverified_results() -> None:
    assert _route_backend_codegen_verification({"backend_codegen_verification": {"status": "failed"}}) == "repair"
    assert _route_backend_codegen_verification({"backend_codegen_verification": {"status": "passed"}}) == "pass"
    assert _route_backend_codegen_verification({"backend_codegen_verification": {"status": "skipped"}}) == "block"
    assert _route_backend_codegen_verification({
        "backend_codegen_verification": {"status": "skipped"},
        "enable_backend_codegen": False,
    }) == "pass"


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
