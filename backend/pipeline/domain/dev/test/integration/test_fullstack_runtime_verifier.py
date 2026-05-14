from __future__ import annotations

from pipeline.domain.dev.test.fixtures import *


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
