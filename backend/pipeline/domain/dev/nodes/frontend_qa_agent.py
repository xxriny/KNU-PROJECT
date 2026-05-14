from __future__ import annotations

import json
import re
from pathlib import Path

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.core.utils import call_structured
from pipeline.domain.dev.nodes._shared import get_apis, placeholder_policy_findings
from pipeline.domain.dev.schemas import DomainQAPlanningOutput


SYSTEM_PROMPT = """# 역할: Frontend QA Agent
## 목표
- frontend agent 산출물을 검토하고 pass 또는 rework를 결정한다.

## 규칙
- 출력은 반드시 구조화된 JSON만 반환한다.
- domain은 반드시 frontend로 설정한다.
- status는 pass 또는 rework만 사용한다.
- UI 구현 가능성, 상태 흐름, backend 연동 정합성을 우선 검토한다.
- findings는 실제 문제 또는 검토 결과를 작성한다.
- fixes_required는 재작업이 필요할 때 구체적으로 작성한다.
- thinking은 반드시 한국어 핵심 단어 3개 이내로 작성한다.
"""


LEGACY_SYSTEM_PROMPT = SYSTEM_PROMPT

SYSTEM_PROMPT = """
당신은 '수석 프론트엔드 QA 검증자'입니다. 프론트엔드 계획이 UIUX 핸드오프와 SA/API 계약을 실제 화면 구현으로 연결하는지 검증하십시오.

[1. 검증 기준 (MANDATORY)]
- 라우팅 정합성: UIUX routes가 frontend_plan.routes에 반영되어야 합니다.
- API 연동성: api_client_needs는 SA API endpoint와 request/response 계약을 참조해야 합니다.
- 상태 흐름: loading, error, empty, success, validation 상태가 구현 계획에 포함되어야 합니다.
- 화면 바인딩: screen_bindings는 route, state, API, data dependency를 가져야 합니다.
- 테스트 커버리지: acceptance_criteria와 주요 사용자 흐름별 테스트 계획이 필요합니다.

[2. 출력 규칙]
- structured JSON만 반환하십시오.
- domain은 반드시 "frontend"입니다.
- status는 "pass" 또는 "rework"만 사용하십시오.
- findings는 실제 결함 또는 확인 결과만 작성하십시오.
- fixes_required는 rework를 해결하기 위한 구체적 작업만 작성하십시오.
- thinking은 한국어 핵심 단어 3개 이내입니다.

[3. 출력 규격(JSON)]
{
  "thinking": "단어 3개",
  "status": "pass|rework",
  "domain": "frontend",
  "findings": ["검증 결과"],
  "fixes_required": ["필요 수정"]
}
"""


HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def _normalize_path(value: str) -> str:
    path = re.sub(r"^https?://[^/]+", "", str(value or "").strip().strip("`'\""))
    path = re.sub(r"\?.*$", "", path)
    path = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", r"{\1}", path)
    path = re.sub(r"\$\{[^}]+\}", "{param}", path)
    path = re.sub(r"/+", "/", path)
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/") or "/"


def _normalize_endpoint(method: str, path: str) -> str:
    return f"{method.upper()} {_normalize_path(path)}"


def _api_endpoint(api: dict) -> str:
    raw = str(api.get("endpoint") or api.get("ep") or "").strip()
    match = re.match(r"^(GET|POST|PUT|PATCH|DELETE)\s+(.+)$", raw, re.I)
    if match:
        return _normalize_endpoint(match.group(1), match.group(2))
    method = str(api.get("method") or "").upper()
    path = str(api.get("path") or api.get("route") or api.get("url") or "").strip()
    if method in HTTP_METHODS and path:
        return _normalize_endpoint(method, path)
    return ""


def _manifest_packages(manifest: dict) -> list[str]:
    packages = []
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        deps = manifest.get(key)
        if isinstance(deps, dict):
            packages.extend(deps.keys())
    return list(dict.fromkeys(packages))


def _allowed_tooling_packages() -> set[str]:
    return {
        "@vitejs/plugin-react",
        "@types/react",
        "@types/react-dom",
        "@testing-library/react",
        "@testing-library/jest-dom",
        "@testing-library/user-event",
        "typescript",
        "vite",
        "vitest",
        "jsdom",
        "eslint",
        "prettier",
    }


def _result_file_paths(codegen_result: dict, suffixes: tuple[str, ...]) -> list[Path]:
    output_dir_raw = str(codegen_result.get("output_dir") or "")
    output_dir = Path(output_dir_raw) if output_dir_raw else None
    paths: list[Path] = []
    for file_info in codegen_result.get("files") or []:
        if not isinstance(file_info, dict) or not file_info.get("path"):
            continue
        path = Path(str(file_info["path"]))
        if not path.is_absolute() and output_dir is not None:
            path = output_dir / path
        if path.suffix.lower() in suffixes and path.is_file():
            paths.append(path)
    if output_dir is not None and output_dir.is_dir():
        for suffix in suffixes:
            paths.extend(output_dir.rglob(f"*{suffix}"))
    unique = []
    seen = set()
    for path in paths:
        resolved = str(path.resolve())
        if resolved not in seen and path.is_file():
            seen.add(resolved)
            unique.append(path)
    return unique


def _read_code_files(codegen_result: dict, suffixes: tuple[str, ...]) -> list[tuple[str, str]]:
    files = []
    for path in _result_file_paths(codegen_result, suffixes):
        try:
            files.append((str(path), path.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            files.append((str(path), path.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue
    return files


def _load_package_json(codegen_result: dict) -> dict:
    output_dir = Path(str(codegen_result.get("output_dir") or ""))
    package_path = output_dir / "package.json"
    if not package_path.is_file():
        return {}
    try:
        return json.loads(package_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _approved_packages(result: dict, spec: dict, codegen_result: dict) -> list[str]:
    dev_context = ((spec.get("dev_task") or {}).get("context") or {})
    stack = (
        codegen_result.get("approved_stack")
        or result.get("approved_stack")
        or dev_context.get("approved_stack")
        or spec.get("approved_stack")
        or {}
    )
    packages = stack.get("packages") if isinstance(stack, dict) else []
    return [str(package) for package in _as_list(packages) if str(package).strip()]


def _extract_frontend_calls(files: list[tuple[str, str]]) -> list[str]:
    calls = []
    fetch_pattern = re.compile(r"fetch\(\s*([`'\"])(?P<url>[^`'\"]+)\1\s*(?:,\s*(?P<options>\{.*?\}))?", re.S)
    axios_pattern = re.compile(r"axios\.(?P<method>get|post|put|patch|delete)\(\s*([`'\"])(?P<url>[^`'\"]+)\2", re.I | re.S)
    for _, content in files:
        for match in fetch_pattern.finditer(content):
            options = match.group("options") or ""
            method_match = re.search(r"method\s*:\s*([`'\"])(?P<method>[A-Za-z]+)\1", options)
            method = method_match.group("method").upper() if method_match else "GET"
            if method in HTTP_METHODS:
                calls.append(_normalize_endpoint(method, match.group("url")))
        for match in axios_pattern.finditer(content):
            calls.append(_normalize_endpoint(match.group("method"), match.group("url")))
    return list(dict.fromkeys(calls))


def _static_code_findings(ctx: NodeContext, result: dict, spec: dict) -> tuple[list[str], list[str]]:
    codegen_result = ctx.sget("frontend_codegen_result", {}) or {}
    if codegen_result.get("status") not in {"generated", "repaired"}:
        return [], []

    findings: list[str] = []
    fixes_required: list[str] = []
    code_files = _read_code_files(codegen_result, (".ts", ".tsx", ".js", ".jsx"))
    if not code_files:
        findings.append("Frontend QA could not read generated frontend source files for static review.")
        fixes_required.append("Ensure frontend_codegen_result.files points to generated source files.")
        return findings, fixes_required

    for finding in placeholder_policy_findings(code_files, label="Frontend generated code"):
        findings.append(finding)
        fixes_required.append("Remove dummy/placeholder/mock business logic and bind UI state to real SA/API contracts.")

    dev_context = ((spec.get("dev_task") or {}).get("context") or {})
    contract_apis = _as_list(dev_context.get("target_api_specs")) or get_apis(ctx.sget)
    sa_apis = [_api_endpoint(api) for api in contract_apis if isinstance(api, dict)]
    sa_apis = [endpoint for endpoint in sa_apis if endpoint]
    calls = _extract_frontend_calls(code_files)
    if calls:
        extra = sorted(set(calls) - set(sa_apis)) if sa_apis else calls
        if extra:
            findings.append(f"Frontend generated code calls APIs absent from SA_BUNDLE: {extra}")
            fixes_required.append("Remove invented frontend API calls or align them exactly to SA_BUNDLE.apis.")
    elif sa_apis:
        findings.append("Frontend generated code does not call any SA API contracts.")
        fixes_required.append("Implement API client/service calls for required SA_BUNDLE.apis or mark the feature as UI-only with evidence.")

    combined = "\n".join(content for _, content in code_files)
    frontend_plan = result.get("frontend_plan") or {}
    required_routes = [str(route) for route in _as_list(frontend_plan.get("routes")) if str(route).strip()]
    missing_routes = [
        route for route in required_routes
        if re.search(r"['\"]" + re.escape(route) + r"['\"]", combined) is None
    ]
    if missing_routes:
        findings.append(f"Frontend generated code does not implement UI/UX routes: {missing_routes}")
        fixes_required.append("Add route declarations/screens for every UI/UX handoff route.")

    required_states = {"loading", "error", "empty"}
    missing_states = sorted(state for state in required_states if re.search(r"\b" + state + r"\b", combined, re.I) is None)
    if missing_states:
        findings.append(f"Frontend generated code misses required UI states: {missing_states}")
        fixes_required.append("Represent loading, error, and empty states in screen/component logic.")

    approved = set(_approved_packages(result, spec, codegen_result))
    manifest = _load_package_json(codegen_result)
    if approved and manifest:
        used = set(_manifest_packages(manifest))
        unapproved = sorted(used - approved - _allowed_tooling_packages())
        if unapproved:
            findings.append(f"Frontend package.json uses packages outside approved_stack: {unapproved}")
            fixes_required.append("Remove unapproved frontend dependencies or add them to PM approved_stack before generation.")

    return findings, fixes_required


def _build_user_message(result: dict, spec: dict, project_rag_context: dict, artifact_rag_context: dict, static_review: dict) -> str:
    return json.dumps({
        "task_spec": spec,
        "domain_result": result,
        "static_code_review": static_review,
        "project_rag_context": project_rag_context,
        "artifact_rag_context": artifact_rag_context,
    }, ensure_ascii=False)


@pipeline_node("develop_frontend_qa_agent")
def develop_frontend_qa_agent_node(ctx: NodeContext) -> dict:
    result = ctx.sget("frontend_result", {}) or {}
    spec = ctx.sget("frontend_task_spec", {}) or {}
    findings = []
    fixes_required = []
    if not result.get("files"):
        findings.append("No frontend targets were identified.")
        fixes_required.append("Specify components or screens for FE implementation.")
    if not result.get("requirement_ids"):
        findings.append("Frontend result is not mapped to requirement IDs.")
        fixes_required.append("Link frontend scope to explicit requirement IDs.")
    if len(result.get("proposed_changes", []) or []) < 2:
        findings.append("Frontend result does not describe enough concrete changes.")
        fixes_required.append("List at least two concrete frontend changes.")
    if len(result.get("test_plan", []) or []) < len(spec.get("acceptance_criteria", []) or []):
        findings.append("Frontend test plan does not cover the declared acceptance criteria.")
        fixes_required.append("Expand the frontend test plan to cover all acceptance criteria.")
    frontend_plan = result.get("frontend_plan") or {}
    if not frontend_plan.get("routes"):
        findings.append("Frontend plan does not include routes from UI/UX handoff.")
        fixes_required.append("Map UI/UX handoff routes into frontend_plan.routes.")
    if not frontend_plan.get("api_client_needs"):
        findings.append("Frontend plan does not include API client needs.")
        fixes_required.append("Map SA/backend API contracts into frontend_plan.api_client_needs.")
    if not frontend_plan.get("screen_bindings"):
        findings.append("Frontend plan does not bind screens to implementation state.")
        fixes_required.append("Add screen_bindings with route, states, API, and data dependencies.")
    static_findings, static_fixes = _static_code_findings(ctx, result, spec)
    findings.extend(static_findings)
    fixes_required.extend(static_fixes)
    static_review = {
        "mode": "static_only",
        "run_and_see": False,
        "findings": static_findings,
        "fixes_required": static_fixes,
    }
    fallback = {
        "status": "rework" if fixes_required else "pass",
        "domain": "frontend",
        "findings": findings,
        "fixes_required": fixes_required,
        "static_code_review": static_review,
    }
    if ctx.api_key:
        res = call_structured(
            api_key=ctx.api_key,
            model=ctx.model,
            schema=DomainQAPlanningOutput,
            system_prompt=SYSTEM_PROMPT,
            user_msg=_build_user_message(
                result,
                spec,
                ctx.sget("project_rag_context", {}) or {},
                ctx.sget("artifact_rag_context", {}) or {},
                static_review,
            ),
            max_retries=3,
            temperature=0.1,
            compress_prompt=True,
        )
        planned = res.parsed.model_dump()
        planned["domain"] = "frontend"
        if fixes_required:
            planned["status"] = "rework"
            planned["findings"] = list(dict.fromkeys([*planned.get("findings", []), *findings]))
            planned["fixes_required"] = list(dict.fromkeys([*planned.get("fixes_required", []), *fixes_required]))
        planned["static_code_review"] = static_review
        return {"frontend_qa_result": planned, "_thinking": res.parsed.thinking or "frontend-qa, state-flow, integration"}
    return {"frontend_qa_result": fallback, "_thinking": "frontend-scope, ui-sync, integration-readiness"}
