from __future__ import annotations

from pathlib import Path

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.core.utils import call_structured
from pipeline.domain.dev.nodes.backend_codegen_verifier import (
    _extract_failed_file_paths,
    _read_repair_context,
    _node_checks,
    _safe_relative_path,
    _write_if_changed,
)
from pipeline.domain.dev.schemas import BackendCodegenRepairOutput, BackendCodegenVerificationResult


FRONTEND_REPAIR_SYSTEM_PROMPT = """# Role: Frontend generated code repair agent
Repair only the generated frontend files so runtime verification can pass.

Rules:
- Return structured JSON only.
- Modify only files under the provided output_dir.
- Return relative file paths only.
- Do not use absolute paths or .. segments.
- Do not touch .env, secrets, credentials, or unrelated project files.
- Keep the existing language/framework and generated scaffold intent.
- Fix test/typecheck/runtime failures based on verification output.
- For Vite/Vitest, ensure setupFiles registers test setup when jest-dom matchers are used.
- For Vite TypeScript, ensure ImportMeta.env is typed, usually with src/vite-env.d.ts.
- thinking must be Korean keywords only, max 5 words.
"""

LEGACY_FRONTEND_REPAIR_SYSTEM_PROMPT = FRONTEND_REPAIR_SYSTEM_PROMPT
FRONTEND_REPAIR_SYSTEM_PROMPT = """
당신은 '프론트엔드 런타임 QA 수정자'입니다. Vitest/TypeScript/Vite 실패 로그를 분석하여 generated 프론트엔드 코드만 수정하십시오.

[1. 실패 로그 기반 수정 (MANDATORY)]
- verification.failed_checks와 stdout_tail/stderr_tail/reason을 최우선 근거로 삼으십시오.
- 실패 로그에 파일 경로가 있으면 그 파일을 최우선으로 수정하십시오.
- user message의 priority_files에 포함된 파일은 반드시 먼저 검토하고, 원인이 맞으면 returned files에 포함하십시오.
- UIUX handoff route, api_client_needs, screen_bindings 계약을 깨지 마십시오.
- 테스트를 삭제하거나 의미 없는 assertion으로 바꾸지 마십시오.
- 실패와 무관한 리팩터링, 디자인 변경, 기능 추가를 금지합니다.

[2. 수정 범위 (ZERO-TOLERANCE)]
- output_dir 밖의 파일을 수정하지 마십시오.
- 상대 경로만 반환하고 절대 경로와 '..'를 금지합니다.
- .env, secret, credential, 원본 프로젝트 파일을 수정하지 마십시오.
- 파일 전체 content를 반환하십시오. patch 조각만 반환하지 마십시오.

[3. React/Vite/Vitest 필수 수정 규칙]
- toBeInTheDocument 등 jest-dom matcher를 쓰면 tests/setup.ts와 vite.config.ts setupFiles를 연결하십시오.
- ImportMeta.env를 쓰면 src/vite-env.d.ts에 vite/client reference를 추가하십시오.
- 테스트 환경은 jsdom이어야 합니다.
- App 테스트는 실제 렌더링되는 접근 가능한 heading/text를 기준으로 검증하십시오.

[4. 출력 규격(JSON)]
{
  "thinking": "한국어 핵심어 5개 이내",
  "summary": "수정 요약",
  "files": [{"path": "relative/path", "content": "file content", "purpose": "수정 이유"}],
  "notes": ["주의사항"]
}
"""


def _ensure_frontend_smoke_route(output_dir: Path) -> None:
    app_path = output_dir / "src" / "App.tsx"
    try:
        content = app_path.read_text(encoding="utf-8")
    except OSError:
        return
    if "<Routes" not in content or "path='/'" in content or 'path="/"' in content:
        return
    smoke_route = "<Route path='/' element={<main><h1>Generated App Flow</h1></main>} />"
    updated = content.replace("<Routes>", f"<Routes>{smoke_route}", 1)
    if updated != content:
        app_path.write_text(updated, encoding="utf-8")


@pipeline_node("develop_frontend_codegen_verifier")
def develop_frontend_codegen_verifier_node(ctx: NodeContext) -> dict:
    codegen = ctx.sget("frontend_codegen_result", {}) or {}
    if codegen.get("status") != "generated":
        result = BackendCodegenVerificationResult(
            status="skipped",
            skipped_reason=f"frontend_codegen_result status is {codegen.get('status') or 'missing'}",
        )
        return {"frontend_codegen_verification": result.model_dump(), "_thinking": "frontend-verify-skipped"}

    output_dir = Path(str(codegen.get("output_dir") or "")).resolve()
    if not output_dir.is_dir():
        result = BackendCodegenVerificationResult(
            status="failed",
            output_dir=str(output_dir),
            failed_checks=["output_dir"],
            next_actions=["Regenerate frontend code because output_dir does not exist."],
        )
        return {"frontend_codegen_verification": result.model_dump(), "_thinking": "frontend-verify-failed"}

    _ensure_frontend_smoke_route(output_dir)
    result = _node_checks(
        output_dir,
        enable_dependency_install=bool(ctx.sget("enable_dependency_install", False)),
    )
    return {
        "frontend_codegen_verification": result.model_dump(),
        "_thinking": f"frontend-verify-{result.status}",
    }


@pipeline_node("develop_frontend_codegen_repair")
def develop_frontend_codegen_repair_node(ctx: NodeContext) -> dict:
    codegen = ctx.sget("frontend_codegen_result", {}) or {}
    verification = ctx.sget("frontend_codegen_verification", {}) or {}
    if verification.get("status") != "failed":
        return {
            "frontend_codegen_repair_result": {
                "status": "skipped",
                "reason": f"verification status is {verification.get('status') or 'missing'}",
                "files": [],
            },
            "_thinking": "frontend-repair-skipped",
        }

    output_dir = Path(str(codegen.get("output_dir") or "")).resolve()
    if not output_dir.is_dir():
        return {
            "frontend_codegen_repair_result": {
                "status": "error",
                "reason": f"Invalid output_dir: {output_dir}",
                "files": [],
            },
            "_thinking": "frontend-repair-invalid-dir",
        }

    try:
        import json

        priority_files = _extract_failed_file_paths(verification)
        user_msg = json.dumps(
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
        res = call_structured(
            api_key=ctx.api_key,
            model=ctx.model,
            schema=BackendCodegenRepairOutput,
            system_prompt=FRONTEND_REPAIR_SYSTEM_PROMPT,
            user_msg=user_msg,
            max_retries=2,
            temperature=0.1,
            compress_prompt=False,
        )
        writes = []
        for item in res.parsed.files:
            writes.append(_write_if_changed(output_dir / _safe_relative_path(item.path), item.content))
        return {
            "frontend_codegen_repair_result": {
                "status": "repaired" if writes else "no_changes",
                "summary": res.parsed.summary,
                "files": writes,
                "notes": res.parsed.notes,
            },
            "_thinking": res.parsed.thinking or "frontend-repair",
        }
    except Exception as exc:
        return {
            "frontend_codegen_repair_result": {
                "status": "error",
                "reason": str(exc),
                "files": [],
            },
            "_thinking": "frontend-repair-error",
        }


@pipeline_node("develop_frontend_codegen_reverifier")
def develop_frontend_codegen_reverifier_node(ctx: NodeContext) -> dict:
    verification = develop_frontend_codegen_verifier_node.__wrapped__(ctx)["frontend_codegen_verification"]
    return {
        "frontend_codegen_reverify_result": verification,
        "frontend_codegen_verification": verification,
        "_thinking": f"frontend-reverify-{verification.get('status')}",
    }


@pipeline_node("develop_frontend_runtime_blocker")
def develop_frontend_runtime_blocker_node(ctx: NodeContext) -> dict:
    codegen = ctx.sget("frontend_codegen_result", {}) or {}
    verification = (
        ctx.sget("frontend_codegen_reverify_result", {})
        or ctx.sget("frontend_codegen_verification", {})
        or {}
    )
    failed_checks = verification.get("failed_checks") or []
    findings = []
    for check in verification.get("checks") or []:
        if check.get("status") == "failed":
            findings.append(
                f"{check.get('name')}: {check.get('reason') or check.get('stderr_tail') or check.get('stdout_tail') or 'failed'}"
            )
    if not findings and failed_checks:
        findings = [f"Frontend runtime check failed: {name}" for name in failed_checks]
    if codegen.get("status") == "error":
        findings.insert(0, f"Frontend codegen failed: {codegen.get('reason') or 'unknown error'}")

    return {
        "global_fe_sync_result": {
            "status": "blocked",
            "reason": "Frontend generated code failed runtime verification.",
            "shared_components": [],
            "sync_actions": findings,
        },
        "integration_qa_result": {
            "status": "blocked",
            "reason": "Frontend generated code failed runtime verification.",
            "findings": findings,
            "rework_targets": ["frontend"],
        },
        "branch_pr_result": {
            "status": "blocked",
            "merge_ready": False,
            "readiness_checks": [
                {
                    "name": "frontend_runtime_verification",
                    "status": "failed",
                    "details": failed_checks,
                }
            ],
        },
        "develop_next_action": "blocked_frontend_runtime_qa",
        "_thinking": "frontend-runtime-blocked",
    }
