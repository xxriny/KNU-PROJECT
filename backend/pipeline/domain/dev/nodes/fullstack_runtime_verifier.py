from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.core.node_base import NodeContext, pipeline_node


@dataclass(frozen=True)
class ApiProbe:
    method: str
    path: str


def _cmd_name(name: str) -> str:
    return f"{name}.cmd" if os.name == "nt" else name


def _selected_domains(ctx: NodeContext) -> set[str]:
    plan = ctx.sget("develop_main_plan", {}) or {}
    return {str(domain).lower() for domain in (plan.get("selected_domains") or ["uiux", "backend", "frontend"])}


def _package_path(output_dir: Path) -> Path | None:
    for name in ("package.json", "package.generated.json"):
        path = output_dir / name
        if path.is_file():
            return path
    return None


def _load_package(output_dir: Path) -> dict[str, Any]:
    path = _package_path(output_dir)
    if not path:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _has_node_modules(output_dir: Path) -> bool:
    return (output_dir / "node_modules").is_dir()


def _npm_runnable_package_path(output_dir: Path) -> Path | None:
    path = output_dir / "package.json"
    return path if path.is_file() else None


def _run_dependency_install(output_dir: Path) -> dict[str, Any]:
    started_at = time.time()
    command = [_cmd_name("npm"), "install"]
    try:
        completed = subprocess.run(
            command,
            cwd=output_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            check=False,
        )
    except FileNotFoundError as exc:
        return {
            "status": "failed",
            "command": command,
            "cwd": str(output_dir),
            "reason": f"Command not found: {exc.filename}",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "failed",
            "command": command,
            "cwd": str(output_dir),
            "reason": "npm install timed out.",
            "stdout_tail": (exc.stdout or "")[-1200:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-1200:] if isinstance(exc.stderr, str) else "",
        }

    return {
        "status": "passed" if completed.returncode == 0 else "failed",
        "command": command,
        "cwd": str(output_dir),
        "returncode": completed.returncode,
        "duration_seconds": round(time.time() - started_at, 2),
        "stdout_tail": (completed.stdout or "")[-1200:],
        "stderr_tail": (completed.stderr or "")[-1200:],
    }


def _extract_api_probes(ctx: NodeContext) -> list[ApiProbe]:
    probes: list[ApiProbe] = []
    for api in ctx.sget("apis", []) or []:
        endpoint = str(api.get("endpoint") or api.get("ep") or "").strip()
        match = re.match(r"^(GET|POST|PUT|PATCH|DELETE)\s+(.+)$", endpoint, re.I)
        if not match:
            continue
        path = match.group(2).strip()
        if not path.startswith("/"):
            path = f"/{path}"
        probes.append(ApiProbe(method=match.group(1).upper(), path=path))
    return probes


def _payload_for(method: str) -> dict[str, Any] | None:
    if method == "GET":
        return None
    return {"payload": {"runtime_smoke": True}, "runtime_smoke": True}


def _http_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> tuple[bool, str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            body = response.read().decode("utf-8", errors="replace")
            parsed: Any = json.loads(body) if body else {}
            return 200 <= response.status < 500, "", parsed
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return False, f"HTTP {exc.code}: {body[-600:]}", None
    except Exception as exc:  # noqa: BLE001 - verifier reports concrete runtime failure.
        return False, str(exc), None


def _http_text(url: str) -> tuple[bool, str, str]:
    try:
        with urllib.request.urlopen(url, timeout=4) as response:
            body = response.read().decode("utf-8", errors="replace")
            return 200 <= response.status < 500, "", body
    except Exception as exc:  # noqa: BLE001 - verifier reports concrete runtime failure.
        return False, str(exc), ""


def _wait_for_text(url: str, *, timeout_seconds: int = 25) -> tuple[bool, str, str]:
    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        ok, error, body = _http_text(url)
        if ok:
            return True, "", body
        last_error = error
        time.sleep(0.5)
    return False, last_error or f"Timed out waiting for {url}", ""


def _wait_for_backend(base_url: str, probes: list[ApiProbe], *, timeout_seconds: int = 25) -> tuple[bool, str, dict[str, Any]]:
    candidates: list[ApiProbe] = [ApiProbe("GET", "/"), ApiProbe("GET", "/health")]
    for probe in probes[:3]:
        candidates.append(probe)
        if not probe.path.startswith("/generated/"):
            candidates.append(ApiProbe(probe.method, f"/generated{probe.path}"))

    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        for probe in candidates:
            ok, error, parsed = _http_json(
                f"{base_url}{probe.path}",
                method=probe.method,
                payload=_payload_for(probe.method),
            )
            if ok:
                return True, "", {"method": probe.method, "path": probe.path, "response": parsed}
            last_error = error
        time.sleep(0.5)
    return False, last_error or f"Timed out waiting for {base_url}", {}


def _terminate(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def _exit_reason(name: str, process: subprocess.Popen[str] | None) -> str:
    if process is None or process.poll() is None:
        return ""
    try:
        stdout, stderr = process.communicate(timeout=1)
    except subprocess.TimeoutExpired:
        return f"{name} exited early with code {process.returncode}"
    details = (stderr or stdout or "").strip()
    return f"{name} exited early with code {process.returncode}: {details[-1200:]}"


def _start_backend(output_dir: Path, port: int) -> tuple[subprocess.Popen[str] | None, str]:
    # 1. Node/Express 체크
    if _npm_runnable_package_path(output_dir):
        package = _load_package(output_dir)
        scripts = package.get("scripts") or {}
        if "start" in scripts:
            command = [_cmd_name("npm"), "start"]
        elif "dev" in scripts:
            command = [_cmd_name("npm"), "run", "dev"]
        else:
            return None, "No backend package start/dev script was found."

        return subprocess.Popen(
            command,
            cwd=output_dir,
            env={**os.environ, "PORT": str(port), "HOST": "127.0.0.1"},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        ), ""

    # 2. Python/FastAPI 체크
    if (output_dir / "navigator_dev" / "app.py").is_file():
        # 시스템 파이썬 또는 가상환경 파이썬 사용
        python_cmd = os.environ.get("PYTHON_EXECUTABLE", "python")
        command = [python_cmd, "-m", "uvicorn", "navigator_dev.app:app", "--host", "127.0.0.1", "--port", str(port)]
        
        return subprocess.Popen(
            command,
            cwd=output_dir,
            env={**os.environ},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        ), ""

    return None, "No supported backend runtime descriptor was found (package.json or app.py)."


def _start_frontend(output_dir: Path, port: int, backend_url: str) -> tuple[subprocess.Popen[str] | None, str]:
    if not _npm_runnable_package_path(output_dir):
        return None, "Generated frontend has no package.json runtime descriptor."

    package = _load_package(output_dir)
    scripts = package.get("scripts") or {}
    if "dev" in scripts:
        command = [_cmd_name("npm"), "run", "dev", "--", "--host", "127.0.0.1", "--port", str(port), "--strictPort"]
    elif "start" in scripts:
        command = [_cmd_name("npm"), "start"]
    else:
        return None, "No frontend package dev/start script was found."

    return subprocess.Popen(
        command,
        cwd=output_dir,
        env={**os.environ, "PORT": str(port), "HOST": "127.0.0.1", "VITE_API_BASE_URL": backend_url},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    ), ""


def _preflight(backend_dir: Path, frontend_dir: Path) -> list[str]:
    findings: list[str] = []
    if not backend_dir.is_dir():
        findings.append(f"Generated backend output_dir does not exist: {backend_dir}")
    if not frontend_dir.is_dir():
        findings.append(f"Generated frontend output_dir does not exist: {frontend_dir}")
    
    # Backend descriptor 체크 (Node or Python)
    has_be_desc = _package_path(backend_dir) or (backend_dir / "navigator_dev" / "app.py").is_file()
    if backend_dir.is_dir() and not has_be_desc:
        findings.append("Generated backend has no package.json or app.py runtime descriptor.")
    
    if frontend_dir.is_dir() and not _package_path(frontend_dir):
        findings.append("Generated frontend has no package.json/package.generated.json runtime descriptor.")
    
    if (backend_dir / "package.generated.json").is_file() and not (backend_dir / "package.json").is_file():
        findings.append("Generated backend has package.generated.json but no package.json; runtime verifier cannot run npm scripts.")
    
    if _npm_runnable_package_path(backend_dir) and not _has_node_modules(backend_dir):
        findings.append("Generated backend node_modules is missing; runtime cannot be started.")
    
    if _npm_runnable_package_path(frontend_dir) and not _has_node_modules(frontend_dir):
        findings.append("Generated frontend node_modules is missing; runtime cannot be started.")
    
    return findings


def _dependency_install_plan(*, backend_dir: Path, frontend_dir: Path, findings: list[str]) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    if any("backend node_modules is missing" in item for item in findings):
        plan.append({
            "target": "backend",
            "manager": "npm",
            "command": "npm install",
            "cwd": str(backend_dir),
            "reason": "Generated backend node_modules is missing.",
            "requires_user_approval": True,
        })
    if any("frontend node_modules is missing" in item for item in findings):
        plan.append({
            "target": "frontend",
            "manager": "npm",
            "command": "npm install",
            "cwd": str(frontend_dir),
            "reason": "Generated frontend node_modules is missing.",
            "requires_user_approval": True,
        })
    return plan


def _dependency_rework_targets(findings: list[str]) -> list[str]:
    targets = []
    for item in findings:
        lowered = item.lower()
        if "backend" in lowered and "backend" not in targets:
            targets.append("backend")
        if "frontend" in lowered and "frontend" not in targets:
            targets.append("frontend")
    return targets or ["backend", "frontend"]


def _install_missing_dependencies_if_enabled(
    *,
    ctx: NodeContext,
    backend_dir: Path,
    frontend_dir: Path,
    findings: list[str],
) -> tuple[list[str], list[dict[str, Any]]]:
    install_results: list[dict[str, Any]] = []
    if not bool(ctx.sget("enable_dependency_install", False)):
        return findings, install_results

    remaining = list(findings)
    if any("backend node_modules is missing" in item for item in findings):
        result = _run_dependency_install(backend_dir)
        result["target"] = "backend"
        install_results.append(result)
        if result.get("status") == "passed" and _has_node_modules(backend_dir):
            remaining = [item for item in remaining if "backend node_modules is missing" not in item]
    if any("frontend node_modules is missing" in item for item in findings):
        result = _run_dependency_install(frontend_dir)
        result["target"] = "frontend"
        install_results.append(result)
        if result.get("status") == "passed" and _has_node_modules(frontend_dir):
            remaining = [item for item in remaining if "frontend node_modules is missing" not in item]

    for result in install_results:
        if result.get("status") != "passed":
            target = result.get("target", "dependency")
            remaining.append(f"Generated {target} dependency install failed: {result.get('reason') or result.get('stderr_tail') or result.get('stdout_tail')}")
    return remaining, install_results


@pipeline_node("develop_fullstack_runtime_verifier")
def develop_fullstack_runtime_verifier_node(ctx: NodeContext) -> dict:
    selected = _selected_domains(ctx)
    if not {"backend", "frontend"}.issubset(selected):
        return {
            "fullstack_runtime_verification": {
                "status": "skipped",
                "reason": "Backend and frontend were not both selected.",
                "checks": [],
            },
            "_thinking": "fullstack-runtime-skipped",
        }

    backend_codegen = ctx.sget("backend_codegen_result", {}) or {}
    frontend_codegen = ctx.sget("frontend_codegen_result", {}) or {}
    if backend_codegen.get("status") != "generated" or frontend_codegen.get("status") != "generated":
        return {
            "fullstack_runtime_verification": {
                "status": "skipped",
                "reason": "Generated backend and frontend outputs are not both present.",
                "checks": [],
            },
            "_thinking": "fullstack-runtime-missing",
        }

    backend_dir = Path(str(backend_codegen.get("output_dir") or "")).resolve()
    frontend_dir = Path(str(frontend_codegen.get("output_dir") or "")).resolve()
    findings = _preflight(backend_dir, frontend_dir)
    initial_findings = list(findings)
    checks: list[dict[str, Any]] = []
    if findings:
        install_plan = _dependency_install_plan(backend_dir=backend_dir, frontend_dir=frontend_dir, findings=findings)
        findings, install_results = _install_missing_dependencies_if_enabled(
            ctx=ctx,
            backend_dir=backend_dir,
            frontend_dir=frontend_dir,
            findings=findings,
        )
        for result in install_results:
            checks.append({
                "name": f"{result.get('target', 'dependency')}_dependency_install",
                "status": result.get("status", "failed"),
                "command": result.get("command", []),
                "returncode": result.get("returncode"),
                "duration_seconds": result.get("duration_seconds"),
                "stdout_tail": result.get("stdout_tail", ""),
                "stderr_tail": result.get("stderr_tail", ""),
                "reason": result.get("reason", ""),
            })
        if not findings:
            install_plan = []

        only_dependency_findings = install_plan and len(install_plan) == len(findings)
        if initial_findings and install_plan and not bool(ctx.sget("enable_dependency_install", False)) and only_dependency_findings:
            return {
                "fullstack_runtime_verification": {
                    "status": "skipped",
                    "reason": "Generated dependencies are not installed.",
                    "checks": checks,
                    "findings": findings,
                    "dependency_install_plan": install_plan,
                    "next_actions": [
                        "Review dependency_install_plan and rerun develop with enable_dependency_install=true if approved.",
                    ],
                },
                "_thinking": "runtime-dependency-install-required",
            }
        if findings:
            return {
                "fullstack_runtime_verification": {
                    "status": "failed",
                    "reason": "Generated fullstack runtime could not be started.",
                    "checks": checks,
                    "findings": findings,
                    "dependency_install_plan": install_plan,
                    "rework_targets": _dependency_rework_targets(findings),
                    "next_actions": [
                        "Install dependencies in generated backend/frontend output directories.",
                        "Ensure generated packages expose start/dev scripts for runtime verification.",
                    ],
                },
                "_thinking": "runtime-preflight-failed",
            }

    backend_port = int(os.environ.get("NAVIGATOR_SMOKE_BACKEND_PORT", "3000"))
    frontend_port = int(os.environ.get("NAVIGATOR_SMOKE_FRONTEND_PORT", "5173"))
    backend_url = f"http://127.0.0.1:{backend_port}"
    frontend_url = f"http://127.0.0.1:{frontend_port}"
    probes = _extract_api_probes(ctx)
    backend_process: subprocess.Popen[str] | None = None
    frontend_process: subprocess.Popen[str] | None = None

    try:
        backend_process, reason = _start_backend(backend_dir, backend_port)
        if reason:
            findings.append(reason)
            checks.append({"name": "backend_start_command", "status": "failed"})
            return {
                "fullstack_runtime_verification": {
                "status": "failed",
                "reason": "Generated backend has no runnable start command.",
                "checks": checks,
                "findings": findings,
                "rework_targets": ["backend"],
            },
            "_thinking": "backend-runtime-command",
        }

        ok, reason, backend_probe = _wait_for_backend(backend_url, probes)
        checks.append({"name": "backend_http", "status": "passed" if ok else "failed", "url": backend_url, "probe": backend_probe})
        if not ok:
            findings.append(reason or _exit_reason("backend", backend_process) or "Backend did not respond.")

        if not findings:
            frontend_process, reason = _start_frontend(frontend_dir, frontend_port, backend_url)
            if reason:
                findings.append(reason)
                checks.append({"name": "frontend_start_command", "status": "failed"})
            else:
                ok, reason, body = _wait_for_text(frontend_url)
                checks.append({"name": "frontend_http", "status": "passed" if ok else "failed", "url": frontend_url})
                if not ok:
                    findings.append(reason or _exit_reason("frontend", frontend_process) or "Frontend did not respond.")
                elif "<html" not in body.lower() and "root" not in body.lower():
                    findings.append("Frontend responded, but the response did not look like the generated app shell.")
                    checks[-1]["status"] = "failed"

        if not findings:
            api_client = frontend_dir / "src" / "api" / "client.ts"
            if probes and api_client.is_file():
                text = api_client.read_text(encoding="utf-8", errors="replace")
                configured = "VITE_API_BASE_URL" in text or "API_BASE_URL" in text
                missing_endpoint_paths = [
                    probe.path for probe in probes
                    if probe.path not in text and f"/generated{probe.path}" not in text
                ]
                checks.append({
                    "name": "frontend_api_base_configuration",
                    "status": "passed" if configured and not missing_endpoint_paths else "failed",
                    "expected_backend_url": backend_url,
                    "missing_endpoint_paths": missing_endpoint_paths,
                })
                if not configured:
                    findings.append("Frontend API client does not expose an API base URL configuration for backend integration.")
                if missing_endpoint_paths:
                    findings.append(f"Frontend API client does not reference generated backend API paths: {missing_endpoint_paths}")
            elif probes:
                findings.append("Frontend API client file was not found, so backend integration cannot be verified.")
                checks.append({"name": "frontend_api_client", "status": "failed"})
            else:
                checks.append({"name": "frontend_backend_contract", "status": "skipped", "reason": "No API probes were available."})

        return {
            "fullstack_runtime_verification": {
                "status": "failed" if findings else "passed",
                "reason": "Fullstack runtime verification failed." if findings else "Backend and frontend runtime checks passed.",
                "checks": checks,
                "findings": findings,
                "backend_url": backend_url,
                "frontend_url": frontend_url,
                "rework_targets": _dependency_rework_targets(findings) if findings else [],
            },
            "_thinking": "runtime-http-integration",
        }
    except FileNotFoundError as exc:
        return {
            "fullstack_runtime_verification": {
                "status": "failed",
                "reason": "Runtime command was not available.",
                "checks": checks,
                "findings": [f"Command not found: {exc.filename}"],
                "rework_targets": ["backend", "frontend"],
            },
            "_thinking": "runtime-tool-missing",
        }
    except Exception as exc:  # noqa: BLE001 - verifier must report unexpected runtime failures.
        return {
            "fullstack_runtime_verification": {
                "status": "failed",
                "reason": "Unexpected fullstack runtime verification failure.",
                "checks": checks,
                "findings": [str(exc)],
                "rework_targets": ["backend", "frontend"],
            },
            "_thinking": "runtime-exception",
        }
    finally:
        _terminate(frontend_process)
        _terminate(backend_process)
