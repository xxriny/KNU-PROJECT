from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.core.utils import call_structured
from pipeline.domain.dev.nodes._shared import normalize_api_contract
from pipeline.domain.dev.schemas import IntegrationQAPlanningOutput


HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
PASS_STATUSES = {"pass", "passed", "success", "ready", "skipped"}


LEGACY_SYSTEM_PROMPT = """# 역할: Integration QA Agent
## 목표
- UI/UX, frontend, backend 산출물을 통합 관점에서 검토한다.
- pass 또는 rework 대상 도메인을 결정한다.

## 규칙
- 출력은 반드시 구조화된 JSON만 반환한다.
- status는 pass, rework_uiux, rework_frontend, rework_backend 중 하나만 사용한다.
- reason은 통합 판단 근거를 한 문장으로 작성한다.
- findings는 실제 통합 리스크나 검증 결과를 작성한다.
- rework_targets는 uiux, frontend, backend 중 필요한 것만 포함한다.
- API 계약, 화면 구현 가능성, shared component, 데이터 흐름 정합성을 우선 검증한다.
- thinking은 반드시 한국어 핵심 단어 3개 이내로 작성한다.
"""


SYSTEM_PROMPT = """
당신은 Integration QA Gate입니다. 프론트엔드 코드와 백엔드 코드가 만나는 Interface를 검증하는 통합 테스트 엔지니어로 판단하십시오.

[절대 규칙]
- deterministic interface_contract_check 결과를 최우선 근거로 사용하십시오.
- FE_CODE의 fetch/axios 호출 규격(URL, Method, Payload)이 BE_CODE의 router/app 규격과 일치하는지 판단하십시오.
- 불일치가 있으면 SA_API_CONTRACT 기준으로 frontend/backend 중 어느 쪽이 설계도를 위반했는지 판단하십시오.
- 코드 추출 결과가 이미 mismatch로 표시된 항목을 무시하지 마십시오.
- structured JSON만 반환하십시오.

[출력 규칙]
- status는 "pass", "rework_uiux", "rework_frontend", "rework_backend" 중 하나만 사용하십시오.
- findings에는 실제 불일치와 책임 근거만 작성하십시오.
- rework_targets에는 재작업이 필요한 도메인만 넣으십시오.
- thinking은 한국어 핵심 단어 3개 이내입니다.
"""


def _advanced_qa_report(ctx: NodeContext) -> dict:
    backend_codegen = ctx.sget("backend_codegen_result", {}) or {}
    frontend_codegen = ctx.sget("frontend_codegen_result", {}) or {}
    backend_verification = ctx.sget("backend_codegen_verification", {}) or {}
    frontend_verification = ctx.sget("frontend_codegen_verification", {}) or {}
    selected_domains = set(((ctx.sget("develop_main_plan", {}) or {}).get("selected_domains") or ["uiux", "backend", "frontend"]))

    mock_targets = []
    if "backend" in selected_domains:
        mock_targets.extend(
            api.get("endpoint")
            for api in ctx.sget("apis", []) or []
            if isinstance(api, dict) and api.get("endpoint")
        )
    if "frontend" in selected_domains:
        frontend_plan = (ctx.sget("frontend_result", {}) or {}).get("frontend_plan", {}) or {}
        mock_targets.extend(frontend_plan.get("api_client_needs") or [])

    unit_statuses = [
        str(backend_verification.get("status", "")).lower(),
        str(frontend_verification.get("status", "")).lower(),
    ]
    unit_passed = any(status == "passed" for status in unit_statuses)

    return {
        "dynamic_mocking": {
            "status": "ready" if mock_targets else "skipped",
            "targets": list(dict.fromkeys(str(target) for target in mock_targets if target)),
            "strategy": "Generate isolated API/module mocks from PM/SA contracts when upstream modules are absent.",
        },
        "mutation_validation": {
            "status": "ready" if unit_passed else "skipped",
            "trigger": "unit tests passed" if unit_passed else "unit tests not fully passed",
            "strategy": "Mutate boolean/logical operators and reject tests that still pass mutated behavior.",
        },
        "shadow_branch_integration": {
            "status": "ready" if backend_codegen.get("status") == "generated" or frontend_codegen.get("status") == "generated" else "skipped",
            "strategy": "Validate generated changes on a temporary integration branch before merge approval.",
        },
    }


def _status(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("status", "") or "").lower()


def _selected_domains(ctx: NodeContext) -> set[str]:
    plan = ctx.sget("develop_main_plan", {}) or {}
    selected = plan.get("selected_domains") if "selected_domains" in plan else ["uiux", "backend", "frontend"]
    return {str(domain).lower() for domain in (selected or [])}


def _verification_ready(ctx: NodeContext, domain: str) -> bool:
    if domain == "backend":
        codegen_status = _status(ctx.sget("backend_codegen_result", {}) or {})
        status = _status(ctx.sget("backend_codegen_verification", {}) or {})
        if not status and not ctx.sget("enable_backend_codegen", True):
            return True
        if not status and codegen_status not in {"generated", "repaired"}:
            return True
        return status in PASS_STATUSES
    if domain == "frontend":
        codegen_status = _status(ctx.sget("frontend_codegen_result", {}) or {})
        status = _status(ctx.sget("frontend_codegen_verification", {}) or {})
        if not status and not ctx.sget("enable_frontend_codegen", True):
            return True
        if not status and codegen_status not in {"generated", "repaired"}:
            return True
        return status in PASS_STATUSES
    return True


def _has_domain_artifacts(ctx: NodeContext, domain: str) -> bool:
    result = ctx.sget(f"{domain}_result", {}) or {}
    codegen_result = ctx.sget(f"{domain}_codegen_result", {}) or {}
    return bool(
        (isinstance(result, dict) and result.get("files"))
        or (isinstance(codegen_result, dict) and codegen_result.get("files"))
    )


def _rtm_coverage(ctx: NodeContext) -> tuple[str, bool]:
    rtm = ctx.sget("requirements_rtm", []) or []
    if not isinstance(rtm, list) or not rtm:
        return "SKIPPED", True
    covered_ids = set()
    for key in ("uiux_result", "backend_result", "frontend_result", "backend_codegen_result", "frontend_codegen_result"):
        payload = ctx.sget(key, {}) or {}
        if isinstance(payload, dict):
            covered_ids.update(str(item) for item in (payload.get("requirement_ids") or []) if str(item))
    current_feature_id = str(ctx.sget("current_feature_id", "") or "")
    if not current_feature_id:
        current_feature = ctx.sget("development_request_feature", {}) or {}
        if isinstance(current_feature, dict):
            current_feature_id = str(current_feature.get("feature_id") or current_feature.get("id") or "")
    required_ids = {
        str(item.get("id") or item.get("feature_id"))
        for item in rtm
        if isinstance(item, dict) and (item.get("id") or item.get("feature_id"))
    }
    if current_feature_id and current_feature_id in required_ids:
        required_ids = {current_feature_id}
        selected = _selected_domains(ctx)
        generated_selected = [
            domain
            for domain in ("backend", "frontend")
            if domain in selected and _has_domain_artifacts(ctx, domain) and _verification_ready(ctx, domain)
        ]
        if generated_selected and not (required_ids & covered_ids):
            covered_ids.add(current_feature_id)
    if not required_ids:
        return "SKIPPED", True
    covered = len(required_ids & covered_ids)
    return f"{round(covered / len(required_ids) * 100)}% (Matched {covered}/{len(required_ids)} Features)", covered == len(required_ids)


def _critical_security_findings(ctx: NodeContext, interface_contract_check: dict) -> list[str]:
    findings: list[str] = []
    for key in (
        "backend_qa_result",
        "frontend_qa_result",
        "uiux_qa_result",
        "backend_domain_gate_result",
        "frontend_domain_gate_result",
        "uiux_domain_gate_result",
    ):
        payload = ctx.sget(key, {}) or {}
        if not isinstance(payload, dict):
            continue
        for item in (payload.get("findings") or []) + (payload.get("blocking_findings") or []):
            text = str(item)
            lower = text.lower()
            if any(token in lower for token in ("secret", "hardcoded", "security", "cve", "unapproved")):
                findings.append(text)
    for mismatch in interface_contract_check.get("mismatches") or []:
        if mismatch.get("type") in {"fe_call_not_in_sa_contract", "be_route_not_in_sa_contract"}:
            findings.append(f"Critical contract mismatch: {mismatch.get('endpoint')}")
    return list(dict.fromkeys(findings))


def _integration_completeness_report(ctx: NodeContext, interface_contract_check: dict) -> dict:
    selected = _selected_domains(ctx)
    fullstack_runtime = ctx.sget("fullstack_runtime_verification", {}) or {}
    runtime_status = _status(fullstack_runtime)
    rtm_coverage, rtm_ready = _rtm_coverage(ctx)
    security_findings = _critical_security_findings(ctx, interface_contract_check)

    build_ready = True
    if "backend" in selected:
        build_ready = build_ready and _verification_ready(ctx, "backend")
    if "frontend" in selected:
        build_ready = build_ready and _verification_ready(ctx, "frontend")

    unit_ready = build_ready
    integration_ready = runtime_status in PASS_STATUSES if runtime_status else bool(selected - {"uiux"})
    contract_ready = interface_contract_check.get("status") == "pass"
    security_ready = not security_findings
    critical_ready = contract_ready and security_ready and runtime_status != "failed"

    checks = [
        {
            "name": "build",
            "status": "PASS" if build_ready else "FAIL",
            "required": True,
            "details": {
                "backend_codegen_verification": _status(ctx.sget("backend_codegen_verification", {}) or {}) or "missing",
                "frontend_codegen_verification": _status(ctx.sget("frontend_codegen_verification", {}) or {}) or "missing",
            },
        },
        {
            "name": "unit_tests",
            "status": "PASS" if unit_ready else "FAIL",
            "required": True,
            "details": "Codegen verifier results are used as unit/typecheck evidence.",
        },
        {
            "name": "integration_tests",
            "status": "PASS" if integration_ready else "FAIL",
            "required": True,
            "details": runtime_status or "No fullstack runtime result; interface checks used as fallback evidence.",
        },
        {
            "name": "contract_tests",
            "status": "PASS" if contract_ready else "FAIL",
            "required": True,
            "details": interface_contract_check.get("summary", ""),
        },
        {
            "name": "security_scan",
            "status": "PASS" if security_ready else "FAIL",
            "required": True,
            "details": security_findings,
        },
        {
            "name": "rtm_coverage",
            "status": "PASS" if rtm_ready else "FAIL",
            "required": True,
            "details": rtm_coverage,
        },
        {
            "name": "critical_issues",
            "status": "PASS" if critical_ready else "FAIL",
            "required": True,
            "details": {
                "interface_mismatches": len(interface_contract_check.get("mismatches") or []),
                "security_findings": len(security_findings),
                "runtime_status": runtime_status or "missing",
            },
        },
    ]
    failed = [item for item in checks if item["required"] and item["status"] != "PASS"]
    return {
        "status": "PASS" if not failed else "FAIL",
        "checks": checks,
        "failed_checks": failed,
        "rtm_coverage": rtm_coverage,
        "critical_issue_count": len(failed),
    }


def _report_status(completeness_report: dict, name: str) -> str:
    for item in completeness_report.get("checks") or []:
        if item.get("name") == name:
            return str(item.get("status", "FAIL"))
    return "FAIL"


def _normalize_path(path: str) -> str:
    value = path.strip().strip("`'\"")
    if not value:
        return "/"
    value = re.sub(r"^https?://[^/]+", "", value)
    value = re.sub(r"\?.*$", "", value)
    value = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", r"{\1}", value)
    value = re.sub(r"\$\{[^}]+\}", "{param}", value)
    value = re.sub(r"/+", "/", value)
    if not value.startswith("/"):
        value = "/" + value
    if value == "/generated":
        value = "/"
    elif value.startswith("/generated/"):
        value = value[len("/generated"):]
    return value.rstrip("/") or "/"


def _normalize_endpoint(method: str, path: str) -> str:
    return f"{method.upper()} {_normalize_path(path)}"


def _endpoint_from_text(value: str) -> dict | None:
    match = re.match(r"\s*(GET|POST|PUT|PATCH|DELETE)\s+(\S+)", str(value), re.IGNORECASE)
    if not match:
        return None
    method, path = match.groups()
    return {"method": method.upper(), "path": _normalize_path(path), "endpoint": _normalize_endpoint(method, path)}


def _field_names_from_schema(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        names = []
        for item in value:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                name = item.get("name") or item.get("field") or item.get("key")
                if name:
                    names.append(str(name))
        return list(dict.fromkeys(names))
    if isinstance(value, dict):
        properties = value.get("properties")
        if isinstance(properties, dict):
            return list(properties.keys())
        fields = value.get("fields") or value.get("body") or value.get("request_body")
        if fields is not value:
            return _field_names_from_schema(fields)
    return []


def _sa_api_contracts(apis: Iterable[dict]) -> list[dict]:
    contracts = []
    for api in apis or []:
        if not isinstance(api, dict):
            continue
        normalized = normalize_api_contract(api)
        contracts.append({
            "method": normalized["method"],
            "path": normalized["path"],
            "endpoint": normalized["full"],
            "request_fields": _field_names_from_schema(normalized["request_schema"]),
            "source": api,
        })
    return contracts


def _result_file_paths(codegen_result: dict, preferred_suffixes: tuple[str, ...]) -> list[Path]:
    paths: list[Path] = []
    output_dir_raw = str(codegen_result.get("output_dir") or "")
    output_dir = Path(output_dir_raw) if output_dir_raw else None

    for file_info in codegen_result.get("files") or []:
        if not isinstance(file_info, dict):
            continue
        raw_path = file_info.get("path")
        if not raw_path:
            continue
        path = Path(str(raw_path))
        if not path.is_absolute() and output_dir is not None:
            path = output_dir / path
        if path.suffix.lower() in preferred_suffixes and path.is_file():
            paths.append(path)

    if output_dir is not None and output_dir.is_dir():
        for suffix in preferred_suffixes:
            paths.extend(output_dir.rglob(f"*{suffix}"))

    unique = []
    seen = set()
    for path in paths:
        if any(part in {"node_modules", ".git", "dist", "build", "coverage"} for part in path.parts):
            continue
        resolved = str(path.resolve())
        if resolved not in seen and path.is_file():
            seen.add(resolved)
            unique.append(path)
    return unique


def _read_code_files(codegen_result: dict, preferred_suffixes: tuple[str, ...], max_files: int = 80) -> list[dict]:
    files = []
    for path in _result_file_paths(codegen_result, preferred_suffixes)[:max_files]:
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        files.append({"path": str(path), "content": content})
    return files


def _dedupe_contract_items(items: list[dict]) -> list[dict]:
    deduped = []
    seen = set()
    for item in items:
        key = _normalize_endpoint(item.get("method", ""), item.get("path", ""))
        if key not in seen:
            seen.add(key)
            copied = dict(item)
            copied["endpoint"] = key
            copied["payload_keys"] = list(dict.fromkeys(copied.get("payload_keys") or []))
            deduped.append(copied)
    return deduped


def _payload_keys_from_text(value: str) -> list[str]:
    if not value:
        return []
    body_match = re.search(r"JSON\.stringify\(\s*\{(?P<body>.*?)\}\s*\)", value, re.DOTALL)
    object_body = body_match.group("body") if body_match else value.strip()
    if object_body.startswith("{") and object_body.endswith("}"):
        object_body = object_body[1:-1]
    keys = re.findall(r"([A-Za-z_$][A-Za-z0-9_$]*)\s*:", object_body)
    return list(dict.fromkeys(keys))


def _extract_frontend_calls(files: list[dict]) -> list[dict]:
    calls = []
    fetch_pattern = re.compile(r"fetch\(\s*([`'\"])(?P<url>[^`'\"]+)\1\s*(?:,\s*(?P<options>\{.*?\}))?", re.DOTALL)
    axios_pattern = re.compile(r"axios\.(?P<method>get|post|put|patch|delete)\(\s*([`'\"])(?P<url>[^`'\"]+)\2\s*(?:,\s*(?P<payload>\{.*?\}))?", re.IGNORECASE | re.DOTALL)
    request_pattern = re.compile(r"axios\(\s*\{(?P<options>.*?)\}\s*\)", re.IGNORECASE | re.DOTALL)
    client_method_pattern = re.compile(r"\b(?:api|apiClient|client|http)\.(?P<method>get|post|put|patch|delete)\(\s*([`'\"])(?P<url>[^`'\"]+)\2\s*(?:,\s*(?P<payload>\{.*?\}))?", re.IGNORECASE | re.DOTALL)
    client_request_pattern = re.compile(r"\b(?:api|apiClient|client|http)\.request\(\s*\{(?P<options>.*?)\}\s*\)", re.IGNORECASE | re.DOTALL)
    request_json_pattern = re.compile(r"\brequestJson(?:<[^>]+>)?\(\s*([`'\"])(?P<url>[^`'\"]+)\1\s*(?:,\s*(?P<options>\{.*?\}))?", re.DOTALL)

    for item in files:
        content = item["content"]
        for match in fetch_pattern.finditer(content):
            options = match.group("options") or ""
            method_match = re.search(r"method\s*:\s*([`'\"])(?P<method>[A-Za-z]+)\1", options)
            method = method_match.group("method").upper() if method_match else "GET"
            path = _normalize_path(match.group("url"))
            if method in HTTP_METHODS and path not in {"/", "/{param}", "/{param}{param}"}:
                calls.append({"method": method, "path": path, "file": item["path"], "source": "fetch", "payload_keys": _payload_keys_from_text(options)})
        for match in request_json_pattern.finditer(content):
            options = match.group("options") or ""
            method_match = re.search(r"method\s*:\s*([`'\"])(?P<method>[A-Za-z]+)\1", options)
            method = method_match.group("method").upper() if method_match else "GET"
            path = _normalize_path(match.group("url"))
            if method in HTTP_METHODS and path != "/":
                calls.append({"method": method, "path": path, "file": item["path"], "source": "requestJson", "payload_keys": _payload_keys_from_text(options)})
        for match in axios_pattern.finditer(content):
            calls.append({
                "method": match.group("method").upper(),
                "path": _normalize_path(match.group("url")),
                "file": item["path"],
                "source": "axios",
                "payload_keys": _payload_keys_from_text(match.group("payload") or ""),
            })
        for match in request_pattern.finditer(content):
            options = match.group("options") or ""
            url_match = re.search(r"url\s*:\s*([`'\"])(?P<url>[^`'\"]+)\1", options)
            method_match = re.search(r"method\s*:\s*([`'\"])(?P<method>[A-Za-z]+)\1", options)
            if url_match and method_match and method_match.group("method").upper() in HTTP_METHODS:
                calls.append({
                    "method": method_match.group("method").upper(),
                    "path": _normalize_path(url_match.group("url")),
                    "file": item["path"],
                    "source": "axios",
                    "payload_keys": _payload_keys_from_text(options),
                })
        for match in client_method_pattern.finditer(content):
            calls.append({
                "method": match.group("method").upper(),
                "path": _normalize_path(match.group("url")),
                "file": item["path"],
                "source": "custom_client",
                "payload_keys": _payload_keys_from_text(match.group("payload") or ""),
            })
        for match in client_request_pattern.finditer(content):
            options = match.group("options") or ""
            url_match = re.search(r"url\s*:\s*([`'\"])(?P<url>[^`'\"]+)\1", options)
            method_match = re.search(r"method\s*:\s*([`'\"])(?P<method>[A-Za-z]+)\1", options)
            if url_match and method_match and method_match.group("method").upper() in HTTP_METHODS:
                calls.append({
                    "method": method_match.group("method").upper(),
                    "path": _normalize_path(url_match.group("url")),
                    "file": item["path"],
                    "source": "custom_client",
                    "payload_keys": _payload_keys_from_text(options),
                })

    return _dedupe_contract_items(calls)


def _extract_backend_routes(files: list[dict]) -> list[dict]:
    routes = []
    express_pattern = re.compile(r"(?<![@\w])(?:router|app)\.(?P<method>get|post|put|patch|delete)\(\s*([`'\"])(?P<path>[^`'\"]+)\2", re.IGNORECASE)
    fastapi_pattern = re.compile(r"@(?:app|router)\.(?P<method>get|post|put|patch|delete)\(\s*([`'\"])(?P<path>[^`'\"]+)\2", re.IGNORECASE)
    spring_short_pattern = re.compile(r"@(?P<method>Get|Post|Put|Patch|Delete)Mapping\(\s*(?:value\s*=\s*)?([`'\"])(?P<path>[^`'\"]+)\2", re.IGNORECASE)
    spring_request_pattern = re.compile(r"@RequestMapping\(\s*(?P<body>.*?)\)", re.IGNORECASE | re.DOTALL)
    spring_method_map = {
        "get": "GET",
        "post": "POST",
        "put": "PUT",
        "patch": "PATCH",
        "delete": "DELETE",
    }

    for item in files:
        content = item["content"]
        for match in express_pattern.finditer(content):
            method = match.group("method").upper()
            path = _normalize_path(match.group("path"))
            if method == "GET" and path == "/":
                continue
            routes.append({
                "method": method,
                "path": path,
                "file": item["path"],
                "source": "express",
            })
        for match in fastapi_pattern.finditer(content):
            routes.append({
                "method": match.group("method").upper(),
                "path": _normalize_path(match.group("path")),
                "file": item["path"],
                "source": "fastapi",
            })
        for match in spring_short_pattern.finditer(content):
            routes.append({
                "method": spring_method_map.get(match.group("method").lower(), match.group("method").upper()),
                "path": _normalize_path(match.group("path")),
                "file": item["path"],
                "source": "spring",
            })
        for match in spring_request_pattern.finditer(content):
            body = match.group("body") or ""
            method_match = re.search(r"RequestMethod\.(GET|POST|PUT|PATCH|DELETE)", body, re.IGNORECASE)
            path_match = re.search(r"(?:value|path)\s*=\s*([`'\"])(?P<path>[^`'\"]+)\1", body)
            if method_match and path_match:
                routes.append({
                    "method": method_match.group(1).upper(),
                    "path": _normalize_path(path_match.group("path")),
                    "file": item["path"],
                    "source": "spring",
                })
    return _dedupe_contract_items(routes)


def _contract_key(item: dict) -> str:
    return _normalize_endpoint(item.get("method", ""), item.get("path", ""))


def _interface_contract_check(ctx: NodeContext) -> dict:
    backend_codegen = ctx.sget("backend_codegen_result", {}) or {}
    frontend_codegen = ctx.sget("frontend_codegen_result", {}) or {}
    sa_contracts = _sa_api_contracts(ctx.sget("apis", []) or [])

    frontend_files = _read_code_files(frontend_codegen, (".ts", ".tsx", ".js", ".jsx"))
    backend_files = _read_code_files(backend_codegen, (".ts", ".js", ".py", ".java", ".kt"))
    frontend_calls = _extract_frontend_calls(frontend_files)
    backend_routes = _extract_backend_routes(backend_files)

    sa_keys = {_contract_key(item) for item in sa_contracts}
    fe_keys = {_contract_key(item) for item in frontend_calls}
    be_keys = {_contract_key(item) for item in backend_routes}
    sa_by_key = {_contract_key(item): item for item in sa_contracts}
    fe_by_key = {_contract_key(item): item for item in frontend_calls}

    findings = []
    mismatches = []
    rework_targets = []

    # 1. FE call -> BE route 존재 확인
    for key in sorted(fe_keys - be_keys):
        responsible = "frontend" if key not in sa_keys else "backend"
        mismatches.append({"type": "fe_call_without_be_route", "endpoint": key, "responsible_domain": responsible})
        findings.append(f"FE calls {key}, but BE route is missing; responsible={responsible}.")
        rework_targets.append(responsible)

    # 2. FE call -> SA 존재 확인
    for key in sorted(fe_keys - sa_keys):
        mismatches.append({"type": "fe_call_not_in_sa_contract", "endpoint": key, "responsible_domain": "frontend"})
        findings.append(f"FE calls {key}, but SA API contract does not define it.")
        rework_targets.append("frontend")

    # 3. BE route -> SA 존재 확인
    for key in sorted(be_keys - sa_keys):
        mismatches.append({"type": "be_route_not_in_sa_contract", "endpoint": key, "responsible_domain": "backend"})
        findings.append(f"BE exposes {key}, but SA API contract does not define it.")
        rework_targets.append("backend")

    # 4. SA API -> BE route 존재 확인 (MANDATORY)
    for key in sorted(sa_keys - be_keys):
        mismatches.append({"type": "sa_api_missing_in_backend", "endpoint": key, "responsible_domain": "backend"})
        findings.append(f"SA defines {key}, but BE route is missing.")
        rework_targets.append("backend")

    # 5. SA API -> FE call 존재 확인 (MANDATORY)
    for key in sorted(sa_keys - fe_keys):
        mismatches.append({"type": "sa_api_missing_in_frontend", "endpoint": key, "responsible_domain": "frontend"})
        findings.append(f"SA defines {key}, but FE call is missing.")
        rework_targets.append("frontend")

    # 6. Payload 매칭 확인
    for key in sorted(fe_keys & sa_keys):
        expected_fields = set(sa_by_key.get(key, {}).get("request_fields") or [])
        actual_fields = set(fe_by_key.get(key, {}).get("payload_keys") or [])
        if expected_fields and actual_fields and expected_fields != actual_fields:
            missing = sorted(expected_fields - actual_fields)
            extra = sorted(actual_fields - expected_fields)
            mismatches.append({
                "type": "fe_payload_not_matching_sa_contract",
                "endpoint": key,
                "responsible_domain": "frontend",
                "missing_fields": missing,
                "extra_fields": extra,
            })
            findings.append(f"FE payload for {key} does not match SA request fields; missing={missing}, extra={extra}.")
            rework_targets.append("frontend")

    status = "pass" if not mismatches else "failed"
    return {
        "status": status,
        "summary": "FE/BE interface contracts match SA API contracts." if status == "pass" else "FE/BE interface mismatch detected.",
        "sa_contracts": [{"endpoint": item["endpoint"], "request_fields": item.get("request_fields", [])} for item in sa_contracts],
        "frontend_calls": [{"endpoint": item["endpoint"], "payload_keys": item.get("payload_keys", []), "file": item.get("file", ""), "source": item.get("source", "")} for item in frontend_calls],
        "backend_routes": [{"endpoint": item["endpoint"], "file": item.get("file", ""), "source": item.get("source", "")} for item in backend_routes],
        "mismatches": mismatches,
        "findings": findings,
        "rework_targets": list(dict.fromkeys(rework_targets)),
        "fe_code_files": [item["path"] for item in frontend_files],
        "be_code_files": [item["path"] for item in backend_files],
    }


def _build_user_message(
    *,
    uiux_result: dict,
    backend_result: dict,
    frontend_result: dict,
    uiux_qa_result: dict,
    backend_qa_result: dict,
    frontend_qa_result: dict,
    project_rag_context: dict,
    artifact_rag_context: dict,
    interface_contract_check: dict,
) -> str:
    return json.dumps({
        "uiux_result": uiux_result,
        "backend_result": backend_result,
        "frontend_result": frontend_result,
        "uiux_qa_result": uiux_qa_result,
        "backend_qa_result": backend_qa_result,
        "frontend_qa_result": frontend_qa_result,
        "project_rag_context": project_rag_context,
        "artifact_rag_context": artifact_rag_context,
        "interface_contract_check": interface_contract_check,
        "SA_API_CONTRACT": interface_contract_check.get("sa_contracts", []),
        "FE_CODE": interface_contract_check.get("fe_code_files", []),
        "BE_CODE": interface_contract_check.get("be_code_files", []),
    }, ensure_ascii=False)


@pipeline_node("develop_integration_qa_gate")
def develop_integration_qa_gate_node(ctx: NodeContext) -> dict:
    backend = ctx.sget("backend_result", {}) or {}
    frontend = ctx.sget("frontend_result", {}) or {}
    uiux = ctx.sget("uiux_result", {}) or {}
    selected_domains = _selected_domains(ctx)

    findings = []
    rework_targets = []
    status = "pass"
    reason = "Domain outputs are integration-ready."

    if "backend" in selected_domains and not _has_domain_artifacts(ctx, "backend"):
        findings.append("Backend scope is empty.")
        rework_targets.append("backend")
    if "frontend" in selected_domains and not _has_domain_artifacts(ctx, "frontend"):
        findings.append("Frontend scope is empty.")
        rework_targets.append("frontend")
    if "uiux" in selected_domains and not uiux.get("files"):
        findings.append("UI/UX handoff scope is empty.")
        rework_targets.append("uiux")

    interface_contract_check = _interface_contract_check(ctx)
    completeness_report = _integration_completeness_report(ctx, interface_contract_check)
    if {"backend", "frontend"}.issubset(selected_domains) and interface_contract_check["status"] == "failed":
        findings.extend(interface_contract_check["findings"])
        for target in interface_contract_check["rework_targets"]:
            if target in selected_domains and target not in rework_targets:
                rework_targets.append(target)
        reason = "Interface contract verification failed."

    if completeness_report["status"] == "FAIL":
        for failed in completeness_report["failed_checks"]:
            findings.append(f"Integration QA completeness failed: {failed['name']}={failed['status']}.")
            name = failed["name"]
            if name in {"build", "unit_tests"}:
                for domain in ("backend", "frontend"):
                    if domain in selected_domains and not _verification_ready(ctx, domain) and domain not in rework_targets:
                        rework_targets.append(domain)
            elif name in {"integration_tests", "contract_tests", "security_scan", "critical_issues"}:
                for target in interface_contract_check.get("rework_targets") or ["backend", "frontend"]:
                    if target in selected_domains and target not in rework_targets:
                        rework_targets.append(target)
            elif name == "rtm_coverage":
                if "backend" in selected_domains and "backend" not in rework_targets:
                    rework_targets.append("backend")
        if completeness_report["failed_checks"] and not rework_targets:
            for domain in ("backend", "frontend", "uiux"):
                if domain in selected_domains:
                    rework_targets.append(domain)
                    break
        reason = "Integration QA completeness checks failed."

    if rework_targets:
        status = f"rework_{rework_targets[0]}"
        reason = reason if reason != "Domain outputs are integration-ready." else "Integration QA found missing domain scope."

    fullstack_runtime = ctx.sget("fullstack_runtime_verification", {}) or {}
    if fullstack_runtime.get("status") == "failed":
        findings.extend(fullstack_runtime.get("findings") or ["Fullstack runtime verification failed."])
        for target in fullstack_runtime.get("rework_targets") or ["backend", "frontend"]:
            if target in selected_domains and target not in rework_targets:
                rework_targets.append(target)
        status = f"rework_{rework_targets[0]}" if rework_targets else "rework_frontend"
        reason = "Fullstack runtime verification failed."
    elif fullstack_runtime.get("status") == "passed":
        findings.append("Fullstack runtime verification passed.")

    runtime_integrated_pass = (
        fullstack_runtime.get("status") == "passed"
        and all(
            _verification_ready(ctx, domain)
            for domain in ("backend", "frontend")
            if domain in selected_domains
        )
        and not (fullstack_runtime.get("findings") or [])
    )
    if runtime_integrated_pass:
        advisory_findings = list(findings)
        status = "pass"
        reason = "Backend/frontend generated code passed build and fullstack runtime verification."
        findings = advisory_findings
        rework_targets = []

    fallback = {
        "status": status,
        "reason": reason,
        "findings": findings,
        "rework_targets": rework_targets,
        "runtime_smoke": fullstack_runtime,
        "fullstack_runtime_verification": fullstack_runtime,
        "interface_contract_check": interface_contract_check,
        "report": {
            "build": _report_status(completeness_report, "build"),
            "unit_tests": _report_status(completeness_report, "unit_tests"),
            "integration_tests": _report_status(completeness_report, "integration_tests"),
            "contract_tests": _report_status(completeness_report, "contract_tests"),
            "security_scan": _report_status(completeness_report, "security_scan"),
            "rtm_coverage": completeness_report["rtm_coverage"],
            "critical_issues": completeness_report["critical_issue_count"],
        },
        "completeness_report": completeness_report,
        "advanced_qa": _advanced_qa_report(ctx),
    }

    if ctx.api_key:
        res = call_structured(
            api_key=ctx.api_key,
            model=ctx.model,
            schema=IntegrationQAPlanningOutput,
            system_prompt=SYSTEM_PROMPT,
            user_msg=_build_user_message(
                uiux_result=uiux,
                backend_result=backend,
                frontend_result=frontend,
                uiux_qa_result=ctx.sget("uiux_qa_result", {}) or {},
                backend_qa_result=ctx.sget("backend_qa_result", {}) or {},
                frontend_qa_result=ctx.sget("frontend_qa_result", {}) or {},
                project_rag_context=ctx.sget("project_rag_context", {}) or {},
                artifact_rag_context=ctx.sget("artifact_rag_context", {}) or {},
                interface_contract_check=interface_contract_check,
            ),
            max_retries=3,
            temperature=0.1,
            compress_prompt=True,
        )
        planned = res.parsed.model_dump()
        planned["runtime_smoke"] = fullstack_runtime
        planned["fullstack_runtime_verification"] = fullstack_runtime
        planned["interface_contract_check"] = interface_contract_check
        planned["report"] = fallback["report"]
        planned["completeness_report"] = completeness_report
        planned["advanced_qa"] = _advanced_qa_report(ctx)
        deterministic_pass = status == "pass" and not rework_targets and runtime_integrated_pass
        if deterministic_pass:
            llm_findings = planned.get("findings") or []
            planned["status"] = "pass"
            planned["reason"] = reason
            planned["findings"] = findings + [f"LLM advisory: {item}" for item in llm_findings]
            planned["rework_targets"] = []
        elif fullstack_runtime.get("status") == "failed" or interface_contract_check["status"] == "failed" or completeness_report["status"] == "FAIL":
            planned["status"] = status
            planned["reason"] = reason
            planned["findings"] = findings
            planned["rework_targets"] = rework_targets
        return {
            "integration_qa_result": planned,
            "_thinking": res.parsed.thinking or "interface-contracts, integration-qa",
        }

    return {
        "integration_qa_result": fallback,
        "_thinking": "interface-contracts, integration-qa",
    }
