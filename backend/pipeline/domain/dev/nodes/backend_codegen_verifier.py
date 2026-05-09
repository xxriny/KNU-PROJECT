from __future__ import annotations

import json
import os
import py_compile
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.core.utils import call_structured
from pipeline.domain.dev.schemas import (
    BackendCodegenRepairOutput,
    BackendCodegenVerificationCheck,
    BackendCodegenVerificationResult,
)


TAIL_LIMIT = 4000
MAX_REPAIR_FILES = 30
MAX_REPAIR_CHARS = 120_000


REPAIR_SYSTEM_PROMPT = """# Role: Backend generated code repair agent
Repair only the generated backend files so runtime verification can pass.

Rules:
- Return structured JSON only.
- Modify only files under the provided output_dir.
- Return relative file paths only.
- Do not use absolute paths or .. segments.
- Do not touch .env, secrets, credentials, or unrelated project files.
- Keep the existing language/framework and generated scaffold intent.
- Fix test/typecheck/runtime failures based on verification output.
- For TypeScript Express tests, app construction must be separate from server startup.
- thinking must be Korean keywords only, max 5 words.
"""

LEGACY_REPAIR_SYSTEM_PROMPT = REPAIR_SYSTEM_PROMPT
REPAIR_SYSTEM_PROMPT = """
당신은 '백엔드 런타임 QA 수정자'입니다. 검증 실패 로그를 분석하여 generated 백엔드 코드만 수정하십시오.

[1. 실패 로그 기반 수정 (MANDATORY)]
- verification.failed_checks와 각 check의 stdout_tail/stderr_tail/reason을 최우선 근거로 삼으십시오.
- 실패와 무관한 리팩터링, 스타일 변경, 기능 추가를 금지합니다.
- 테스트를 삭제하거나 기대값을 낮춰 통과시키지 마십시오.
- 생성 코드의 실제 버그를 수정하되, 테스트가 명백히 생성 동작과 모순될 때만 테스트를 고치십시오.

[2. 수정 범위 (ZERO-TOLERANCE)]
- output_dir 밖의 파일을 수정하지 마십시오.
- 상대 경로만 반환하고 절대 경로와 '..'를 금지합니다.
- .env, secret, credential, 원본 프로젝트 파일을 수정하지 마십시오.
- 파일 전체 content를 반환하십시오. patch 조각만 반환하지 마십시오.

[3. 스택별 수정 규칙]
- TypeScript Express는 src/app.ts와 src/index.ts 역할을 분리해야 합니다.
- 테스트는 app import 방식이어야 하며 listen side effect를 만들면 안 됩니다.
- Python/FastAPI는 import path가 generated package 기준으로 실행 가능해야 합니다.
- Java/Spring은 Maven test 구조와 package 경로가 일치해야 합니다.

[4. 출력 규격(JSON)]
{
  "thinking": "한국어 핵심어 5개 이내",
  "summary": "수정 요약",
  "files": [{"path": "relative/path", "content": "file content", "purpose": "수정 이유"}],
  "notes": ["주의사항"]
}
"""


def _tail(text: str) -> str:
    return (text or "")[-TAIL_LIMIT:]


def _cmd_name(name: str) -> str:
    return f"{name}.cmd" if os.name == "nt" else name


def _run_check(name: str, command: list[str], cwd: Path, timeout: int = 120) -> BackendCodegenVerificationCheck:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        return BackendCodegenVerificationCheck(
            name=name,
            status="skipped",
            command=command,
            reason=f"Command not found: {exc.filename}",
        )
    except subprocess.TimeoutExpired as exc:
        return BackendCodegenVerificationCheck(
            name=name,
            status="failed",
            command=command,
            stdout_tail=_tail(exc.stdout or ""),
            stderr_tail=_tail(exc.stderr or ""),
            reason=f"Timed out after {timeout}s",
        )

    return BackendCodegenVerificationCheck(
        name=name,
        status="passed" if completed.returncode == 0 else "failed",
        command=command,
        returncode=completed.returncode,
        stdout_tail=_tail(completed.stdout),
        stderr_tail=_tail(completed.stderr),
    )


def _install_node_dependencies(output_dir: Path) -> BackendCodegenVerificationCheck:
    return _run_check("dependency_install", [_cmd_name("npm"), "install"], output_dir, timeout=300)


def _has_node_modules(output_dir: Path) -> bool:
    return (output_dir / "node_modules").is_dir()


def _node_modules_stale(output_dir: Path) -> bool:
    node_modules = output_dir / "node_modules"
    if not node_modules.is_dir():
        return True

    try:
        installed_at = node_modules.stat().st_mtime
    except OSError:
        return True

    for name in ("package.json", "package.generated.json", "package-lock.json"):
        manifest = output_dir / name
        if manifest.is_file():
            try:
                if manifest.stat().st_mtime > installed_at:
                    return True
            except OSError:
                return True
    return False


def _package_json(output_dir: Path) -> dict[str, Any]:
    for name in ("package.json", "package.generated.json"):
        path = output_dir / name
        if path.is_file():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {}
    return {}


def _result_from_checks(
    *,
    output_dir: Path,
    checks: list[BackendCodegenVerificationCheck],
    skipped_reason: str = "",
    next_actions: list[str] | None = None,
    dependency_install_plan: list[dict[str, Any]] | None = None,
    dependency_install_result: dict[str, Any] | None = None,
) -> BackendCodegenVerificationResult:
    if not checks:
        return BackendCodegenVerificationResult(
            status="skipped",
            output_dir=str(output_dir),
            skipped_reason=skipped_reason or "No verification checks were selected",
            next_actions=next_actions or [],
            dependency_install_plan=dependency_install_plan or [],
            dependency_install_result=dependency_install_result or {},
        )

    failed = [check.name for check in checks if check.status == "failed"]
    skipped = [check.name for check in checks if check.status == "skipped"]
    status = "failed" if failed else ("skipped" if len(skipped) == len(checks) else "passed")
    actions = list(next_actions or [])
    if failed:
        actions.append("Inspect failed check output and regenerate or patch generated code.")
    if skipped:
        actions.append("Install missing tools or dependencies and rerun verification.")

    return BackendCodegenVerificationResult(
        status=status,
        output_dir=str(output_dir),
        checks=checks,
        failed_checks=failed,
        next_actions=actions,
        dependency_install_plan=dependency_install_plan or [],
        dependency_install_result=dependency_install_result or {},
    )


def _node_dependency_install_plan(output_dir: Path) -> list[dict[str, Any]]:
    package = output_dir / "package.json"
    if not package.is_file():
        package = output_dir / "package.generated.json"
    return [{
        "manager": "npm",
        "command": "npm install",
        "cwd": str(output_dir),
        "manifest": str(package) if package.is_file() else "",
        "reason": "node_modules not found",
        "requires_user_approval": True,
    }]


def _node_checks(output_dir: Path, *, enable_dependency_install: bool = False) -> BackendCodegenVerificationResult:
    package = _package_json(output_dir)
    if not package:
        return BackendCodegenVerificationResult(
            status="skipped",
            output_dir=str(output_dir),
            skipped_reason="package.json or package.generated.json not found",
            next_actions=["Add package.json with test/typecheck scripts before automated verification."],
        )

    install_plan: list[dict[str, Any]] = []
    install_result: dict[str, Any] = {}

    should_install = not _has_node_modules(output_dir) or (
        enable_dependency_install and _node_modules_stale(output_dir)
    )

    if should_install:
        install_plan = _node_dependency_install_plan(output_dir)
        if enable_dependency_install:
            install_check = _install_node_dependencies(output_dir)
            install_result = install_check.model_dump()
            if install_check.status != "passed":
                return BackendCodegenVerificationResult(
                    status="failed",
                    output_dir=str(output_dir),
                    checks=[install_check],
                    failed_checks=["dependency_install"],
                    skipped_reason="",
                    next_actions=["Inspect npm install output, then rerun verification."],
                    dependency_install_plan=install_plan,
                    dependency_install_result=install_result,
                )
        else:
            return BackendCodegenVerificationResult(
                status="skipped",
                output_dir=str(output_dir),
                skipped_reason="node_modules not found",
                next_actions=["Review dependency_install_plan and rerun with enable_dependency_install=true if approved."],
                dependency_install_plan=install_plan,
            )

    if not _has_node_modules(output_dir):
        return BackendCodegenVerificationResult(
            status="skipped",
            output_dir=str(output_dir),
            skipped_reason="node_modules not found",
            next_actions=["npm install finished but node_modules was still not found."],
            dependency_install_plan=_node_dependency_install_plan(output_dir),
            dependency_install_result=install_result,
        )

    checks: list[BackendCodegenVerificationCheck] = []
    scripts = package.get("scripts") or {}

    if (output_dir / "tsconfig.json").is_file():
        checks.append(_run_check("typecheck", [_cmd_name("npx"), "tsc", "--noEmit"], output_dir))

    dev_deps = package.get("devDependencies") or {}
    deps = package.get("dependencies") or {}
    all_deps = {**deps, **dev_deps}
    if "jest" in all_deps:
        checks.append(_run_check("test", [_cmd_name("npx"), "jest", "--detectOpenHandles", "--runInBand"], output_dir))
    elif "vitest" in all_deps:
        checks.append(_run_check("test", [_cmd_name("npx"), "vitest", "run"], output_dir))
    elif "test" in scripts:
        checks.append(_run_check("test", [_cmd_name("npm"), "test"], output_dir))

    return _result_from_checks(
        output_dir=output_dir,
        checks=checks,
        skipped_reason="No supported Node verification command found",
        next_actions=["Add a test script or supported Jest/Vitest dependency."] if not checks else [],
        dependency_install_plan=install_plan,
        dependency_install_result=install_result,
    )


def _python_checks(output_dir: Path) -> BackendCodegenVerificationResult:
    checks: list[BackendCodegenVerificationCheck] = []
    python_files = [path for path in output_dir.rglob("*.py") if "__pycache__" not in path.parts]
    compile_errors: list[str] = []
    for path in python_files:
        try:
            py_compile.compile(path, doraise=True)
        except py_compile.PyCompileError as exc:
            compile_errors.append(f"{path}: {exc.msg}")

    checks.append(
        BackendCodegenVerificationCheck(
            name="py_compile",
            status="failed" if compile_errors else "passed",
            stderr_tail=_tail("\n".join(compile_errors)),
        )
    )

    tests_dir = output_dir / "tests"
    if tests_dir.is_dir():
        checks.append(_run_check("pytest", [sys.executable, "-m", "pytest", "tests", "-q"], output_dir))

    failed = [check.name for check in checks if check.status == "failed"]
    return BackendCodegenVerificationResult(
        status="failed" if failed else "passed",
        output_dir=str(output_dir),
        checks=checks,
        failed_checks=failed,
        next_actions=["Inspect failed check output and patch generated code."] if failed else [],
    )


def _java_checks(output_dir: Path) -> BackendCodegenVerificationResult:
    if (output_dir / "pom.xml").is_file():
        return _result_from_checks(
            output_dir=output_dir,
            checks=[_run_check("maven_test", [_cmd_name("mvn"), "test"], output_dir, timeout=240)],
        )

    gradlew = output_dir / ("gradlew.bat" if os.name == "nt" else "gradlew")
    if gradlew.is_file():
        command = [str(gradlew), "test"] if os.name != "nt" else [str(gradlew), "test"]
        return _result_from_checks(
            output_dir=output_dir,
            checks=[_run_check("gradle_wrapper_test", command, output_dir, timeout=240)],
        )

    if (output_dir / "build.gradle").is_file() or (output_dir / "build.gradle.kts").is_file():
        return _result_from_checks(
            output_dir=output_dir,
            checks=[_run_check("gradle_test", [_cmd_name("gradle"), "test"], output_dir, timeout=240)],
        )

    java_files = [str(path) for path in output_dir.rglob("*.java")]
    if java_files:
        return _result_from_checks(
            output_dir=output_dir,
            checks=[_run_check("javac", [_cmd_name("javac"), *java_files], output_dir, timeout=120)],
        )

    return BackendCodegenVerificationResult(
        status="skipped",
        output_dir=str(output_dir),
        skipped_reason="No Java build file or .java files found",
        next_actions=["Generate pom.xml, build.gradle, or Java source files before verification."],
    )


def _c_family_checks(output_dir: Path) -> BackendCodegenVerificationResult:
    if (output_dir / "CMakeLists.txt").is_file():
        build_dir = output_dir / "build"
        configure = _run_check("cmake_configure", [_cmd_name("cmake"), "-S", str(output_dir), "-B", str(build_dir)], output_dir, timeout=120)
        checks = [configure]
        if configure.status == "passed":
            checks.append(_run_check("cmake_build", [_cmd_name("cmake"), "--build", str(build_dir)], output_dir, timeout=240))
            if (build_dir / "CTestTestfile.cmake").is_file():
                checks.append(_run_check("ctest", [_cmd_name("ctest"), "--test-dir", str(build_dir), "--output-on-failure"], output_dir, timeout=240))
        return _result_from_checks(output_dir=output_dir, checks=checks)

    if (output_dir / "Makefile").is_file() or (output_dir / "makefile").is_file():
        checks = [_run_check("make", [_cmd_name("make")], output_dir, timeout=240)]
        if checks[0].status == "passed":
            checks.append(_run_check("make_test", [_cmd_name("make"), "test"], output_dir, timeout=240))
        return _result_from_checks(output_dir=output_dir, checks=checks)

    c_files = [str(path) for path in output_dir.rglob("*.c")]
    cpp_files = [str(path) for path in output_dir.rglob("*.cpp")]
    cc_files = [str(path) for path in output_dir.rglob("*.cc")]
    source_files = c_files + cpp_files + cc_files
    if source_files:
        compiler = "gcc" if c_files and not (cpp_files or cc_files) else "g++"
        return _result_from_checks(
            output_dir=output_dir,
            checks=[_run_check("compile", [_cmd_name(compiler), *source_files, "-o", str(output_dir / "generated_app")], output_dir, timeout=120)],
        )

    return BackendCodegenVerificationResult(
        status="skipped",
        output_dir=str(output_dir),
        skipped_reason="No C/C++ build file or source files found",
        next_actions=["Generate CMakeLists.txt, Makefile, or C/C++ source files before verification."],
    )


def _select_verifier(language: str, framework: str, output_dir: Path):
    lang = language.lower()
    fw = framework.lower()
    if lang in {"typescript", "ts", "javascript", "js", "node"} or fw in {"express", "expressjs", "nestjs", "fastify"}:
        return _node_checks
    if lang == "python" or fw in {"fastapi", "flask", "django"}:
        return _python_checks
    if lang in {"java", "kotlin"} or fw in {"spring", "springboot", "spring-boot"}:
        return _java_checks
    if lang in {"c", "cpp", "c++", "cc"} or fw in {"cmake", "make"}:
        return _c_family_checks

    if _package_json(output_dir):
        return _node_checks
    if (output_dir / "pom.xml").is_file() or (output_dir / "build.gradle").is_file() or list(output_dir.rglob("*.java")):
        return _java_checks
    if (output_dir / "CMakeLists.txt").is_file() or (output_dir / "Makefile").is_file() or list(output_dir.rglob("*.c")) or list(output_dir.rglob("*.cpp")):
        return _c_family_checks
    if list(output_dir.rglob("*.py")):
        return _python_checks
    return None


def _safe_relative_path(path: str) -> Path:
    raw = Path(path.replace("\\", "/"))
    if raw.is_absolute() or ".." in raw.parts:
        raise ValueError(f"Unsafe generated path: {path}")
    return raw


def _write_if_changed(path: Path, content: str) -> dict[str, str]:
    previous = path.read_text(encoding="utf-8") if path.exists() else None
    if previous == content:
        return {"path": str(path), "status": "unchanged"}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"path": str(path), "status": "updated" if previous is not None else "created"}


def _extract_failed_file_paths(verification: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    pattern = re.compile(r"((?:[A-Za-z0-9_. -]+[\\/])*[A-Za-z0-9_. -]+\.(?:ts|tsx|js|jsx|py|java|c|cc|cpp|h|hpp|json|css|html))\(\d+,\d+\)")
    for check in verification.get("checks") or []:
        text = "\n".join(
            str(check.get(key) or "")
            for key in ("stdout_tail", "stderr_tail", "reason")
        )
        for match in pattern.finditer(text):
            normalized = match.group(1).replace("\\", "/").lstrip("./")
            if normalized not in candidates:
                candidates.append(normalized)
    return candidates


def _read_repair_context(output_dir: Path, priority_paths: list[str] | None = None) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    total_chars = 0
    ignored_dirs = {"node_modules", "dist", "build", "coverage", "__pycache__"}
    ignored_suffixes = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".lock"}

    def append_file(path: Path) -> None:
        nonlocal total_chars
        if not path.is_file():
            return
        if any(part in ignored_dirs for part in path.parts):
            return
        if path.suffix.lower() in ignored_suffixes:
            return
        try:
            relative = path.relative_to(output_dir).as_posix()
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return
        if any(item["path"] == relative for item in files):
            return
        next_total = total_chars + len(content)
        if len(files) >= MAX_REPAIR_FILES or next_total > MAX_REPAIR_CHARS:
            return
        files.append({"path": relative, "content": content})
        total_chars = next_total

    for relative in priority_paths or []:
        try:
            append_file(output_dir / _safe_relative_path(relative))
        except ValueError:
            continue

    for path in sorted(output_dir.rglob("*")):
        if len(files) >= MAX_REPAIR_FILES or total_chars > MAX_REPAIR_CHARS:
            break
        append_file(path)
    return files


def _repair_user_message(*, codegen: dict[str, Any], verification: dict[str, Any], output_dir: Path) -> str:
    priority_files = _extract_failed_file_paths(verification)
    return json.dumps(
        {
            "language": codegen.get("language"),
            "framework": codegen.get("framework"),
            "output_dir": str(output_dir),
            "test_command": codegen.get("test_command"),
            "verification": verification,
            "priority_files": priority_files,
            "repair_instruction": "Modify the files named in priority_files first. If a failed check references a file path, include that file in the returned files unless another returned file fully explains and fixes the failure.",
            "files": _read_repair_context(output_dir, priority_files),
        },
        ensure_ascii=False,
    )


def _verification_for_block(ctx: NodeContext) -> dict:
    return (
        ctx.sget("backend_codegen_reverify_result", {})
        or ctx.sget("backend_codegen_verification", {})
        or {}
    )


@pipeline_node("develop_backend_codegen_verifier")
def develop_backend_codegen_verifier_node(ctx: NodeContext) -> dict:
    codegen = ctx.sget("backend_codegen_result", {}) or {}
    if codegen.get("status") != "generated":
        result = BackendCodegenVerificationResult(
            status="skipped",
            skipped_reason=f"backend_codegen_result status is {codegen.get('status') or 'missing'}",
        )
        return {"backend_codegen_verification": result.model_dump(), "_thinking": "verify-skipped"}

    output_dir = Path(str(codegen.get("output_dir") or "")).resolve()
    if not output_dir.is_dir():
        result = BackendCodegenVerificationResult(
            status="failed",
            output_dir=str(output_dir),
            failed_checks=["output_dir"],
            next_actions=["Regenerate backend code because output_dir does not exist."],
        )
        return {"backend_codegen_verification": result.model_dump(), "_thinking": "verify-failed"}

    language = str(codegen.get("language") or "").lower()
    framework = str(codegen.get("framework") or "").lower()
    verifier = _select_verifier(language, framework, output_dir)
    if verifier:
        result = verifier(output_dir, enable_dependency_install=bool(ctx.sget("enable_dependency_install", False))) if verifier is _node_checks else verifier(output_dir)
    else:
        result = BackendCodegenVerificationResult(
            status="skipped",
            output_dir=str(output_dir),
            skipped_reason=f"Unsupported verification target: {language}/{framework}",
            next_actions=["Add a verifier adapter for this language/framework."],
        )

    return {
        "backend_codegen_verification": result.model_dump(),
        "_thinking": f"codegen-verify-{result.status}",
    }


@pipeline_node("develop_backend_codegen_repair")
def develop_backend_codegen_repair_node(ctx: NodeContext) -> dict:
    codegen = ctx.sget("backend_codegen_result", {}) or {}
    verification = ctx.sget("backend_codegen_verification", {}) or {}
    if verification.get("status") != "failed":
        return {
            "backend_codegen_repair_result": {
                "status": "skipped",
                "reason": f"verification status is {verification.get('status') or 'missing'}",
                "files": [],
            },
            "_thinking": "repair-skipped",
        }

    output_dir = Path(str(codegen.get("output_dir") or "")).resolve()
    if not output_dir.is_dir():
        return {
            "backend_codegen_repair_result": {
                "status": "error",
                "reason": f"Invalid output_dir: {output_dir}",
                "files": [],
            },
            "_thinking": "repair-invalid-dir",
        }

    try:
        res = call_structured(
            api_key=ctx.api_key,
            model=ctx.model,
            schema=BackendCodegenRepairOutput,
            system_prompt=REPAIR_SYSTEM_PROMPT,
            user_msg=_repair_user_message(codegen=codegen, verification=verification, output_dir=output_dir),
            max_retries=2,
            temperature=0.1,
            compress_prompt=False,
        )
        writes = []
        for item in res.parsed.files:
            writes.append(_write_if_changed(output_dir / _safe_relative_path(item.path), item.content))
        return {
            "backend_codegen_repair_result": {
                "status": "repaired" if writes else "no_changes",
                "summary": res.parsed.summary,
                "files": writes,
                "notes": res.parsed.notes,
            },
            "_thinking": res.parsed.thinking or "backend-repair",
        }
    except Exception as exc:
        return {
            "backend_codegen_repair_result": {
                "status": "error",
                "reason": str(exc),
                "files": [],
            },
            "_thinking": "repair-error",
        }


@pipeline_node("develop_backend_codegen_reverifier")
def develop_backend_codegen_reverifier_node(ctx: NodeContext) -> dict:
    verification = develop_backend_codegen_verifier_node.__wrapped__(ctx)["backend_codegen_verification"]
    return {
        "backend_codegen_reverify_result": verification,
        "backend_codegen_verification": verification,
        "_thinking": f"codegen-reverify-{verification.get('status')}",
    }


@pipeline_node("develop_backend_runtime_blocker")
def develop_backend_runtime_blocker_node(ctx: NodeContext) -> dict:
    codegen = ctx.sget("backend_codegen_result", {}) or {}
    verification = _verification_for_block(ctx)
    failed_checks = verification.get("failed_checks") or []
    findings = []
    for check in verification.get("checks") or []:
        if check.get("status") == "failed":
            findings.append(
                f"{check.get('name')}: {check.get('reason') or check.get('stderr_tail') or check.get('stdout_tail') or 'failed'}"
            )

    if not findings and failed_checks:
        findings = [f"Backend runtime check failed: {name}" for name in failed_checks]
    if codegen.get("status") == "error":
        findings.insert(0, f"Backend codegen failed: {codegen.get('reason') or 'unknown error'}")

    return {
        "frontend_result": {
            "status": "skipped",
            "domain": "frontend",
            "summary": "Skipped because backend generated code failed runtime verification.",
            "files": [],
            "test_plan": [],
        },
        "frontend_qa_result": {
            "status": "skipped",
            "domain": "frontend",
            "findings": ["Frontend generation skipped until backend runtime verification passes."],
            "fixes_required": [],
        },
        "frontend_domain_gate_result": {
            "status": "skipped",
            "domain": "frontend",
            "reason": "Skipped because backend runtime verification failed.",
            "blocking_findings": [],
        },
        "global_fe_sync_result": {
            "status": "blocked",
            "reason": "Backend runtime verification failed before frontend synchronization.",
            "shared_components": [],
            "sync_actions": [],
        },
        "integration_qa_result": {
            "status": "blocked",
            "reason": "Backend generated code failed runtime verification.",
            "findings": findings,
            "rework_targets": ["backend"],
        },
        "branch_pr_result": {
            "status": "blocked",
            "merge_ready": False,
            "readiness_checks": [
                {
                    "name": "backend_runtime_verification",
                    "status": "failed",
                    "details": failed_checks,
                }
            ],
        },
        "develop_next_action": "blocked_backend_runtime_qa",
        "_thinking": "runtime-qa-blocked",
    }
