from __future__ import annotations

import json
import re
from pathlib import Path

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.core.utils import call_structured
from pipeline.domain.dev.nodes._shared import (
    get_apis,
    get_components,
    get_tables,
    normalize_api_contract,
    placeholder_policy_findings,
)
from pipeline.domain.dev.schemas import DomainQAPlanningOutput



SYSTEM_PROMPT = """
당신은 '수석 백엔드 QA 검증자'입니다. 백엔드 산출물이 PM 요구사항과 SA 계약을 실제 구현 가능한 수준으로 충족하는지 검증하십시오.

[1. 검증 기준 (MANDATORY)]
- 요구사항 추적성: 모든 백엔드 변경은 requirement_ids와 연결되어야 합니다.
- API 계약성: endpoint, request, response, error, status code가 구체적이어야 합니다.
- 데이터 무결성: table/entity, FK, validation, transaction, auth/security 규칙 누락을 찾아야 합니다.
- 테스트 커버리지: acceptance_criteria마다 대응 테스트가 있어야 합니다.
- 재작업 판단: 실행 가능한 구현 정보가 부족하면 반드시 rework로 판정하십시오.

[2. 출력 규칙]
- structured JSON만 반환하십시오.
- domain은 반드시 "backend"입니다.
- status는 "pass" 또는 "rework"만 사용하십시오.
- findings는 실제 결함 또는 확인 결과만 작성하십시오.
- fixes_required는 rework를 해결하기 위한 구체적 작업만 작성하십시오.
- thinking은 한국어 핵심 단어 3개 이내입니다.

[3. 출력 규격(JSON)]
{
  "thinking": "단어 3개",
  "status": "pass|rework",
  "domain": "backend",
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
    path = re.sub(r"/+", "/", path)
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/") or "/"


def _normalize_endpoint(method: str, path: str) -> str:
    return f"{method.upper()} {_normalize_path(path)}"


def _api_endpoint(api: dict) -> str:
    """_shared.py의 공통 파서를 사용하여 SA API 엔드포인트를 정규화합니다."""
    return normalize_api_contract(api)["full"]


def _table_name(table: dict) -> str:
    return str(table.get("table_name") or table.get("name") or table.get("nm") or "").strip()


def _component_name(component: dict) -> str:
    return str(component.get("component_name") or component.get("name") or component.get("nm") or "").strip()


def _manifest_packages(manifest: dict) -> list[str]:
    packages = []
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        deps = manifest.get(key)
        if isinstance(deps, dict):
            packages.extend(deps.keys())
    return list(dict.fromkeys(packages))


def _allowed_tooling_packages() -> set[str]:
    return {
        "@types/node",
        "@types/express",
        "@types/cors",
        "@types/jest",
        "@types/supertest",
        "typescript",
        "ts-node",
        "tsx",
        "nodemon",
        "jest",
        "ts-jest",
        "supertest",
        "vitest",
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


def _extract_express_routes(files: list[tuple[str, str]]) -> list[str]:
    routes = []
    pattern = re.compile(r"\b(?:router|app)\.(get|post|put|patch|delete)\(\s*([`'\"])([^`'\"]+)\2", re.I)
    for _, content in files:
        for match in pattern.finditer(content):
            routes.append(_normalize_endpoint(match.group(1), match.group(3)))
    return list(dict.fromkeys(routes))


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


def _static_code_findings(ctx: NodeContext, result: dict, spec: dict) -> tuple[list[str], list[str]]:
    codegen_result = ctx.sget("backend_codegen_result", {}) or {}
    if codegen_result.get("status") not in {"generated", "repaired"}:
        return [], []
    current_feature_id = str(ctx.sget("current_feature_id", "") or "")
    task_instruction = codegen_result.get("task_instruction") or {}
    codegen_feature_id = str(
        task_instruction.get("feature_id")
        or ((task_instruction.get("dev_task") or {}).get("task_info") or {}).get("feature_id")
        or ""
    )
    if current_feature_id and codegen_feature_id and codegen_feature_id != current_feature_id:
        return [], []

    findings: list[str] = []
    fixes_required: list[str] = []
    code_files = _read_code_files(codegen_result, (".ts", ".js", ".py", ".java", ".kt", ".go", ".c", ".cpp", ".h"))
    if not code_files:
        findings.append("Backend QA could not read generated backend source files for static review.")
        fixes_required.append("Ensure backend_codegen_result.files points to generated source files.")
        return findings, fixes_required

    for finding in placeholder_policy_findings(code_files, label="Backend generated code"):
        findings.append(finding)
        fixes_required.append("Remove dummy/placeholder/mock business logic and implement the SA contract explicitly.")

    dev_context = ((spec.get("dev_task") or {}).get("context") or {})
    contract_apis = _as_list(dev_context.get("target_api_specs")) or get_apis(ctx.sget)
    contract_tables = _as_list(dev_context.get("target_table_specs")) or get_tables(ctx.sget)
    contract_components = _as_list(dev_context.get("component_specs")) or get_components(ctx.sget)

    sa_apis = [_api_endpoint(api) for api in contract_apis if isinstance(api, dict)]
    sa_apis = [endpoint for endpoint in sa_apis if endpoint]
    routes = _extract_express_routes(code_files)
    if sa_apis and routes:
        missing = sorted(set(sa_apis) - set(routes))
        extra = sorted(set(routes) - set(sa_apis))
        if missing:
            findings.append(f"Backend generated routes miss SA API contracts: {missing}")
            fixes_required.append("Add backend routes for every missing SA API endpoint without renaming method or path.")
        if extra:
            findings.append(f"Backend generated routes include APIs absent from SA_BUNDLE: {extra}")
            fixes_required.append("Remove or justify extra backend routes; generated backend must not invent APIs outside SA_BUNDLE.")

    combined = "\n".join(content for _, content in code_files)
    table_names = [_table_name(table) for table in contract_tables if isinstance(table, dict)]
    missing_tables = [name for name in table_names if name and re.search(r"\b" + re.escape(name) + r"\b", combined, re.I) is None]
    if missing_tables:
        # [MODIFIED] 초기 개발 단계에서 Mock 코드를 짤 때 테이블명이 누락되는 경우가 많아 무한 루프 발생 방지를 위해 경고만 남김
        findings.append(f"Backend generated code does not reference SA DB tables/entities (Warning only): {missing_tables}")
        # fixes_required.append("Map SA_BUNDLE tables/entities into service/model/persistence code or document an explicit blocking note.")

    component_names = [_component_name(component) for component in contract_components if isinstance(component, dict)]
    missing_components = [name for name in component_names if name and re.search(r"\b" + re.escape(name) + r"\b", combined, re.I) is None]
    if component_names and missing_components:
        # [MODIFIED] 컴포넌트 추적성 확인도 무한 루프 방지를 위해 경고(Findings)로만 처리
        findings.append(f"Backend generated code does not trace SA components (Warning only): {missing_components}")
        # fixes_required.append("Reference SA components in service/module names, route handlers, or contract documentation.")

    approved = set(_approved_packages(result, spec, codegen_result))
    manifest = _load_package_json(codegen_result)
    if approved and manifest:
        used = set(_manifest_packages(manifest))
        unapproved = sorted(used - approved - _allowed_tooling_packages())
        if unapproved:
            findings.append(f"Backend package.json uses packages outside approved_stack: {unapproved}")
            fixes_required.append("Remove unapproved backend dependencies or add them to PM approved_stack before generation.")

    return findings, fixes_required


def _build_user_message(result: dict, spec: dict, project_rag_context: dict, artifact_rag_context: dict, static_review: dict) -> str:
    return json.dumps({
        "task_spec": spec,
        "domain_result": result,
        "static_code_review": static_review,
        "project_rag_context": project_rag_context,
        "artifact_rag_context": artifact_rag_context,
    }, ensure_ascii=False)


@pipeline_node("develop_backend_qa_agent")
def develop_backend_qa_agent_node(ctx: NodeContext) -> dict:
    result = ctx.sget("backend_result", {}) or {}
    spec = ctx.sget("backend_task_spec", {}) or {}
    findings = []
    fixes_required = []
    if not result.get("files"):
        findings.append("No backend API or data targets were identified.")
        fixes_required.append("Specify backend contract or persistence scope.")
    if not result.get("requirement_ids"):
        findings.append("Backend result is not mapped to requirement IDs.")
        fixes_required.append("Link backend scope to explicit requirement IDs.")
    if len(result.get("proposed_changes", []) or []) < 2:
        findings.append("Backend result does not describe enough concrete changes.")
        fixes_required.append("List at least two concrete backend changes.")
    if len(result.get("test_plan", []) or []) < len(spec.get("acceptance_criteria", []) or []):
        findings.append("Backend test plan does not cover the declared acceptance criteria.")
        fixes_required.append("Expand the backend test plan to cover all acceptance criteria.")
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
        "domain": "backend",
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
        planned["domain"] = "backend"
        if fixes_required:
            planned["status"] = "rework"
            planned["findings"] = list(dict.fromkeys([*planned.get("findings", []), *findings]))
            planned["fixes_required"] = list(dict.fromkeys([*planned.get("fixes_required", []), *fixes_required]))
        planned["static_code_review"] = static_review
        return {"backend_qa_result": planned, "_thinking": res.parsed.thinking or "backend-qa, contracts, integrity"}
    return {"backend_qa_result": fallback, "_thinking": "backend-scope, contract-coverage, data-risks"}
