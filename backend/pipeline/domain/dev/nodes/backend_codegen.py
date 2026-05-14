from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.core.utils import call_structured
from pipeline.domain.dev.nodes._shared import (
    get_apis,
    get_components,
    get_goal,
    get_tables,
    normalize_api_contract,
    slugify,
)
from pipeline.domain.dev.schemas import BackendCodegenOutput


SYSTEM_PROMPT = """# Role: Backend code generation agent
Generate backend source files from PM/SA contracts and the user's target language/framework.

Rules:
- Return structured JSON only.
- Generate only files under the provided output_root.
- Do not overwrite unrelated project files.
- Prefer small, runnable scaffolds with tests.
- Use the requested language and framework exactly when provided.
- For TypeScript Express, separate app construction from server startup:
  put Express app/middleware/routes in src/app.ts, put app.listen only in src/index.ts,
  and make tests import src/app.ts so tests do not open a real server handle.
- Generated tests must match the generated API behavior; do not assert state changes that the test did not perform.
- If auth/login is present, include login-oriented service logic placeholders, request/response types, and test coverage.
- Keep generated code deterministic, readable, and free of secrets.
- Do not include markdown fences in file content.
- thinking must be Korean keywords only, max 5 words.
"""

LEGACY_SYSTEM_PROMPT = SYSTEM_PROMPT
SYSTEM_PROMPT = """
당신은 '수석 백엔드 코드 생성자'입니다. PM 요구사항과 SA API/DB 계약을 기준으로 실행 가능한 백엔드 scaffold를 생성하십시오.

[1. PM/SA 계약 준수 (MANDATORY)]
- requirement_id, API endpoint, DB table/field 등 계약을 임의로 바꾸지 마십시오.
- SA에 없는 API를 임의로 양산하지 마십시오. 필요한 경우 notes에 "계약 외 제안"으로만 남기십시오.
- API 필드명과 DB 컬럼명은 계약에 있는 이름을 우선 사용하십시오.
- 인증/권한/검증/차단 규칙은 API 동작 또는 테스트에 반드시 반영하십시오.
- approved_stack에 없는 runtime/framework/library를 임의로 선택하지 마십시오.
- task_instruction과 contract_handoff를 최우선 구현 지시로 사용하십시오.
- dummy, placeholder, mock business logic을 생성하지 마십시오. 구현이 불가능하면 blocking note를 반환하십시오.

[2. 생성 안전 규칙 (ZERO-TOLERANCE)]
- output_root 밖의 파일을 생성하거나 수정하지 마십시오.
- path는 상대 경로만 사용하고 절대 경로와 '..'를 금지합니다.
- .env, secret, API key, 하드코딩된 비밀값을 생성하지 마십시오.
- markdown fence를 content에 넣지 마십시오.
- 테스트는 생성 코드의 실제 동작과 모순되면 안 됩니다.

[3. 스택별 필수 규칙]
- TypeScript Express는 app 생성(src/app.ts)과 서버 실행(src/index.ts)을 분리하십시오.
- 테스트는 app을 import하고 실제 listen 서버를 열지 마십시오.
- Python FastAPI는 router/service/schema를 분리하고 pytest/TestClient로 검증 가능해야 합니다.
- Java Spring Boot는 Maven 기준 pom.xml, main/test package 구조를 갖춰야 합니다.

[4. 출력 규격(JSON)]
{
  "thinking": "한국어 핵심어 5개 이내",
  "language": "요청 언어",
  "framework": "요청 프레임워크",
  "files": [{"path": "relative/path", "content": "file content", "purpose": "용도"}],
  "test_command": "검증 명령",
  "notes": ["주의사항"]
}
"""


def _enabled(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").lower() in {"1", "true", "yes", "on"}


def _safe_name(value: str, fallback: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_]+", "_", value or "").strip("_").lower()
    return name or fallback


def _endpoint_parts(api: dict[str, Any], index: int) -> tuple[str, str, str]:
    normalized = normalize_api_contract(api)
    method = normalized["method"].lower()
    path = normalized["path"]
    stem = _safe_name(f"{method}_{path.replace('{', '').replace('}', '')}", f"endpoint_{index}")
    return method, path, stem


def _class_name(stem: str, suffix: str) -> str:
    return "".join(part.capitalize() for part in stem.split("_") if part) + suffix


def _target(ctx: NodeContext) -> tuple[str, str, str]:
    language = str(ctx.sget("backend_codegen_language", "") or "").strip().lower()
    framework = str(ctx.sget("backend_codegen_framework", "") or "").strip().lower()
    mode = str(ctx.sget("backend_codegen_mode", "llm") or "llm").strip().lower()
    if not language:
        language = "python"
    if not framework:
        framework = "fastapi" if language == "python" else "express"
    return language, framework, mode


def _target_dir_name(language: str, framework: str) -> str:
    return f"{_safe_name(language, 'python')}_{_safe_name(framework, 'fastapi')}"


def _target_policy(language: str, framework: str) -> dict[str, str]:
    lang = language.lower()
    fw = framework.lower()
    if lang in {"typescript", "ts", "javascript", "js"} and fw in {"express", "expressjs"}:
        return {
            "support_level": "official",
            "verification_adapter": "node",
            "target_key": "typescript_express",
        }
    if lang == "python" and fw == "fastapi":
        return {
            "support_level": "official",
            "verification_adapter": "python",
            "target_key": "python_fastapi",
        }
    if lang == "java" and fw in {"spring", "springboot", "spring-boot"}:
        return {
            "support_level": "official",
            "verification_adapter": "java",
            "target_key": "java_spring_boot",
        }
    if lang in {"c", "cpp", "c++", "cc"}:
        return {
            "support_level": "experimental",
            "verification_adapter": "c_family",
            "target_key": _target_dir_name(language, framework),
        }
    if lang in {"typescript", "ts", "javascript", "js", "node"}:
        adapter = "node"
    elif lang == "python":
        adapter = "python"
    elif lang in {"java", "kotlin"}:
        adapter = "java"
    else:
        adapter = "unknown"
    return {
        "support_level": "experimental",
        "verification_adapter": adapter,
        "target_key": _target_dir_name(language, framework),
    }


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _stack_item_domain(item: dict[str, Any]) -> str:
    return str(item.get("domain") or item.get("dom") or "").lower()


def _stack_item_package(item: dict[str, Any]) -> str:
    return str(item.get("pkg") or item.get("package") or item.get("package_name") or item.get("name") or "").strip()


def _approved_stack(ctx: NodeContext, *, language: str, framework: str) -> dict[str, Any]:
    spec = ctx.sget("backend_task_spec", {}) or {}
    dev_task = spec.get("dev_task") or {}
    dev_context = dev_task.get("context") or {}
    if isinstance(dev_context.get("approved_stack"), dict):
        stack = dict(dev_context["approved_stack"])
        stack.setdefault("language", language)
        stack.setdefault("framework", framework)
        stack.setdefault("source", "backend_task_spec.dev_task.context.approved_stack")
        return stack
    pm_bundle = ctx.sget("pm_bundle", {}) or {}
    pm_data = pm_bundle.get("data", {}) if isinstance(pm_bundle, dict) else {}
    stack_planner = ctx.sget("stack_planner_output", {}) or {}
    raw_items = (
        _as_list(ctx.sget("approved_stack", []))
        or _as_list(ctx.sget("tech_stacks", []))
        or _as_list(pm_data.get("tech_stacks"))
        or _as_list(pm_data.get("stacks"))
        or _as_list(stack_planner.get("m"))
        or _as_list(stack_planner.get("stack_mapping"))
    )
    approved_items = [
        item for item in raw_items
        if isinstance(item, dict) and str(item.get("status", "APPROVED")).upper() == "APPROVED"
    ]
    backend_items = [
        item for item in approved_items
        if _stack_item_domain(item) in {"backend", "be", "server", "api", ""}
    ]
    packages = [_stack_item_package(item) for item in backend_items if _stack_item_package(item)]
    return {
        "language": language,
        "framework": framework,
        "source": "pm_bundle.data.tech_stacks|stack_planner_output.stack_mapping",
        "items": backend_items,
        "packages": list(dict.fromkeys(packages)),
    }


def _contract_handoff(ctx: NodeContext) -> dict[str, Any]:
    backend_result = ctx.sget("backend_result", {}) or {}
    return backend_result.get("contract_handoff") or {}


def _sa_contract(ctx: NodeContext, handoff: dict[str, Any]) -> dict[str, Any]:
    spec = ctx.sget("backend_task_spec", {}) or {}
    dev_task = spec.get("dev_task") or {}
    dev_context = dev_task.get("context") or {}
    apis = _as_list(dev_context.get("target_api_specs")) or _as_list(handoff.get("apis")) or get_apis(ctx.sget)
    tables = _as_list(dev_context.get("target_table_specs")) or _as_list(handoff.get("tables")) or get_tables(ctx.sget)
    components = _as_list(dev_context.get("component_specs")) or _as_list(handoff.get("components")) or get_components(ctx.sget)
    return {
        "source": "backend_task_spec.dev_task.context|backend_result.contract_handoff|sa_arch_bundle.data|sa_output.data",
        "apis": [item for item in apis if isinstance(item, dict)],
        "tables": [item for item in tables if isinstance(item, dict)],
        "components": [item for item in components if isinstance(item, dict)],
    }


def _task_instruction(ctx: NodeContext, *, goal: str, handoff: dict[str, Any]) -> dict[str, Any]:
    spec = ctx.sget("backend_task_spec", {}) or {}
    dev_task = spec.get("dev_task") or {}
    dev_context = dev_task.get("context") or {}
    return {
        "dev_task": dev_task,
        "domain": "backend",
        "goal": spec.get("goal") or goal,
        "requirement_ids": _as_list(spec.get("requirement_ids")),
        "focus": _as_list(spec.get("focus")),
        "inputs": _as_list(spec.get("inputs")),
        "target_components": _as_list(spec.get("target_components")),
        "acceptance_criteria": _as_list(spec.get("acceptance_criteria")),
        "rework_instruction": dev_context.get("rework_instruction") or spec.get("rework_instruction") or handoff.get("rework_instruction") or {},
    }


def _write_if_changed(path: Path, content: str) -> dict[str, str]:
    previous = path.read_text(encoding="utf-8") if path.exists() else None
    if previous == content:
        return {"path": str(path), "status": "unchanged"}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {"path": str(path), "status": "updated" if previous is not None else "created"}


def _schema_code(apis: list[dict[str, Any]]) -> str:
    lines = [
        "from __future__ import annotations",
        "",
        "from typing import Any",
        "",
        "from pydantic import BaseModel, Field",
        "",
        "",
    ]
    for index, api in enumerate(apis or [{}], start=1):
        _, _, stem = _endpoint_parts(api, index)
        request_name = _class_name(stem, "Request")
        response_name = _class_name(stem, "Response")
        lines.extend([
            f"class {request_name}(BaseModel):",
            f"    \"\"\"Generated request schema for {api.get('endpoint') or api.get('ep') or stem}.\"\"\"",
            "    payload: dict[str, Any] = Field(default_factory=dict)",
            "",
            "",
            f"class {response_name}(BaseModel):",
            f"    \"\"\"Generated response schema for {api.get('endpoint') or api.get('ep') or stem}.\"\"\"",
            "    status: str = \"ok\"",
            "    data: dict[str, Any] = Field(default_factory=dict)",
            "",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def _service_code(goal: str, apis: list[dict[str, Any]], tables: list[dict[str, Any]]) -> str:
    return "\n".join([
        "from __future__ import annotations",
        "",
        "from typing import Any",
        "",
        "",
        "class GeneratedBackendService:",
        "    \"\"\"Generated service scaffold.\"\"\"",
        "",
        "    def __init__(self) -> None:",
        f"        self.goal = {goal!r}",
        f"        self.api_contracts = {json.dumps(apis, ensure_ascii=False, indent=8)}",
        f"        self.table_contracts = {json.dumps(tables, ensure_ascii=False, indent=8)}",
        "",
        "    async def execute(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:",
        "        return {",
        "            \"operation\": operation,",
        "            \"accepted\": True,",
        "            \"payload\": payload,",
        "        }",
        "",
        "",
        "service = GeneratedBackendService()",
        "",
    ])


def _router_code(apis: list[dict[str, Any]]) -> str:
    lines = [
        "from __future__ import annotations",
        "",
        "from fastapi import APIRouter",
        "",
        "from .schemas import *",
        "from .service import service",
        "",
        "",
        "router = APIRouter(prefix=\"/generated\", tags=[\"generated-dev\"])",
        "",
        "",
    ]
    for index, api in enumerate(apis or [{}], start=1):
        method, path, stem = _endpoint_parts(api, index)
        request_name = _class_name(stem, "Request")
        response_name = _class_name(stem, "Response")
        operation = _safe_name(stem, f"endpoint_{index}")
        lines.extend([
            f"@router.{method}(\"{path}\", response_model={response_name})",
            f"async def {operation}(request: {request_name}) -> {response_name}:",
            f"    result = await service.execute({operation!r}, request.payload)",
            f"    return {response_name}(data=result)",
            "",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def _test_code(apis: list[dict[str, Any]]) -> str:
    first = _endpoint_parts((apis or [{}])[0], 1)
    method, path, _ = first
    return "\n".join([
        "from __future__ import annotations",
        "",
        "from fastapi import FastAPI",
        "from fastapi.testclient import TestClient",
        "",
        "from backend.generated.navigator_dev.router import router",
        "",
        "",
        "def test_generated_backend_route_accepts_payload() -> None:",
        "    app = FastAPI()",
        "    app.include_router(router)",
        "    client = TestClient(app)",
        f"    response = client.{method}(\"/generated{path}\", json={{\"payload\": {{\"sample\": True}}}})",
        "    assert response.status_code == 200",
        "    assert response.json()[\"status\"] == \"ok\"",
        "",
    ])


def _ts_operation_name(stem: str) -> str:
    parts = [part for part in stem.split("_") if part]
    if not parts:
        return "generatedEndpoint"
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


def _express_routes_code(apis: list[dict[str, Any]]) -> str:
    lines = [
        "import { Router } from 'express';",
        "import { executeGeneratedOperation } from './service';",
        "",
        "export const generatedRouter = Router();",
        "",
    ]
    for index, api in enumerate(apis or [{}], start=1):
        method, path, stem = _endpoint_parts(api, index)
        operation = _ts_operation_name(stem)
        lines.extend([
            f"generatedRouter.{method}('{path}', async (req, res, next) => {{",
            "  try {",
            f"    const data = await executeGeneratedOperation('{operation}', req.body ?? {{}});",
            "    res.status(200).json({ status: 'ok', data });",
            "  } catch (error) {",
            "    next(error);",
            "  }",
            "});",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def _express_service_code(goal: str, apis: list[dict[str, Any]], tables: list[dict[str, Any]]) -> str:
    return "\n".join([
        "export type GeneratedPayload = Record<string, unknown>;",
        "",
        f"const goal = {json.dumps(goal, ensure_ascii=False)};",
        f"const apiContracts = {json.dumps(apis, ensure_ascii=False, indent=2)} as const;",
        f"const tableContracts = {json.dumps(tables, ensure_ascii=False, indent=2)} as const;",
        "",
        "export async function executeGeneratedOperation(operation: string, payload: GeneratedPayload) {",
        "  return {",
        "    operation,",
        "    accepted: true,",
        "    payload,",
        "    goal,",
        "    apiContracts,",
        "    tableContracts,",
        "    contractVerified: true,",
        "  };",
        "}",
        "",
    ])


def _express_test_code(apis: list[dict[str, Any]]) -> str:
    method, path, _ = _endpoint_parts((apis or [{}])[0], 1)
    return "\n".join([
        "import express from 'express';",
        "import request from 'supertest';",
        "import { generatedRouter } from '../src/routes';",
        "",
        "describe('generated backend route', () => {",
        "  it('accepts a payload', async () => {",
        "    const app = express();",
        "    app.use(express.json());",
        "    app.use('/generated', generatedRouter);",
        f"    const response = await request(app).{method}('/generated{path}').send({{ sample: true }});",
        "    expect(response.status).toBe(200);",
        "    expect(response.body.status).toBe('ok');",
        "  });",
        "});",
        "",
    ])


def _express_package_json() -> str:
    return json.dumps({
        "scripts": {
            "dev": "ts-node src/index.ts",
            "build": "tsc",
            "start": "node dist/index.js",
            "test": "vitest run",
            "typecheck": "tsc --noEmit",
        },
        "dependencies": {
            "express": "^4.18.3",
        },
        "devDependencies": {
            "@types/express": "^4.17.21",
            "@types/supertest": "^6.0.2",
            "supertest": "^6.3.4",
            "typescript": "^5.4.0",
            "vitest": "^1.6.0",
        },
    }, indent=2)


NODE_PACKAGE_VERSIONS = {
    "@supabase/supabase-js": "^2.45.4",
    "cors": "^2.8.5",
    "dotenv": "^16.4.5",
    "express": "^4.18.3",
}

NODE_DEV_PACKAGE_VERSIONS = {
    "@types/cors": "^2.8.17",
    "@types/express": "^4.17.21",
    "@types/node": "^20.14.10",
    "@types/supertest": "^6.0.2",
    "supertest": "^6.3.4",
    "typescript": "^5.4.0",
    "vitest": "^1.6.0",
}

NODE_IMPORT_TO_TYPES = {
    "cors": "@types/cors",
    "express": "@types/express",
    "supertest": "@types/supertest",
}

NODE_BUILTIN_TYPES_PACKAGES = {
    "@supabase/supabase-js",
    "vite",
    "vitest",
}


def _node_imports_from_files(files: list[tuple[str, str]]) -> set[str]:
    imports: set[str] = set()
    pattern = re.compile(
        r"(?:import\s+(?:type\s+)?(?:[^'\"\n]+?\s+from\s+)?|require\()\s*['\"]([^'\"\n]+)['\"]"
    )
    for path, content in files:
        if not path.replace("\\", "/").endswith((".ts", ".tsx", ".js", ".jsx")):
            continue
        for match in pattern.finditer(content):
            name = match.group(1).strip()
            if not name or name.startswith(".") or name.startswith("/"):
                continue
            if name.startswith("@"):
                parts = name.split("/")
                package_name = "/".join(parts[:2]) if len(parts) >= 2 else name
            else:
                package_name = name.split("/", 1)[0]
            imports.add(package_name)
    return imports


def _uses_node_globals(files: list[tuple[str, str]]) -> bool:
    combined = "\n".join(content for _, content in files)
    return bool(re.search(r"\b(process|Buffer|__dirname|__filename)\b", combined))


def _merge_node_package_json(
    generated_content: str,
    template_content: str,
    generated_files: list[tuple[str, str]],
) -> str:
    try:
        generated = json.loads(generated_content) if generated_content.strip() else {}
    except json.JSONDecodeError:
        generated = {}
    try:
        template = json.loads(template_content) if template_content.strip() else {}
    except json.JSONDecodeError:
        template = {}

    merged = dict(generated or {})
    merged["scripts"] = {
        **(template.get("scripts") or {}),
        **(generated.get("scripts") or {}),
    }
    merged["dependencies"] = {
        **(template.get("dependencies") or {}),
        **(generated.get("dependencies") or {}),
    }
    merged["devDependencies"] = {
        **(template.get("devDependencies") or {}),
        **(generated.get("devDependencies") or {}),
    }

    for package_name in sorted(_node_imports_from_files(generated_files)):
        if package_name in NODE_PACKAGE_VERSIONS:
            merged["dependencies"].setdefault(package_name, NODE_PACKAGE_VERSIONS[package_name])
        types_package = None if package_name in NODE_BUILTIN_TYPES_PACKAGES else NODE_IMPORT_TO_TYPES.get(package_name)
        if types_package:
            merged["devDependencies"].setdefault(types_package, NODE_DEV_PACKAGE_VERSIONS[types_package])

    if _uses_node_globals(generated_files):
        merged["devDependencies"].setdefault("@types/node", NODE_DEV_PACKAGE_VERSIONS["@types/node"])

    if "vitest" in merged["devDependencies"] and "jest" not in merged["devDependencies"]:
        merged["scripts"]["test"] = "vitest run"
    elif "jest" in merged["devDependencies"]:
        merged["scripts"]["test"] = "jest --detectOpenHandles --runInBand"

    return json.dumps(merged, ensure_ascii=False, indent=2)


def _express_tsconfig() -> str:
    return json.dumps({
        "compilerOptions": {
            "target": "ES2020",
            "module": "CommonJS",
            "moduleResolution": "Node",
            "strict": True,
            "esModuleInterop": True,
            "skipLibCheck": True,
            "outDir": "dist",
        },
        "include": ["src", "tests"],
    }, indent=2)


def _java_package(goal: str) -> str:
    return "\n".join([
        "package com.navigator.generated;",
        "",
        "public record GeneratedResponse(String status, String message) {",
        "    public static GeneratedResponse ok() {",
        f"        return new GeneratedResponse(\"ok\", {json.dumps(goal, ensure_ascii=False)});",
        "    }",
        "}",
        "",
    ])


def _java_controller(apis: list[dict[str, Any]]) -> str:
    lines = [
        "package com.navigator.generated;",
        "",
        "import org.springframework.http.ResponseEntity;",
        "import org.springframework.web.bind.annotation.GetMapping;",
        "import org.springframework.web.bind.annotation.PostMapping;",
        "import org.springframework.web.bind.annotation.RequestBody;",
        "import org.springframework.web.bind.annotation.RequestMapping;",
        "import org.springframework.web.bind.annotation.RestController;",
        "",
        "import java.util.Map;",
        "",
        "@RestController",
        "@RequestMapping(\"/generated\")",
        "public class GeneratedController {",
        "",
    ]
    for index, api in enumerate(apis or [{}], start=1):
        method, path, stem = _endpoint_parts(api, index)
        java_path = path.replace("{", "{").replace("}", "}")
        name = _ts_operation_name(stem)
        if method == "get":
            lines.extend([
                f"    @GetMapping(\"{java_path}\")",
                f"    public ResponseEntity<GeneratedResponse> {name}() {{",
                "        return ResponseEntity.ok(GeneratedResponse.ok());",
                "    }",
                "",
            ])
        else:
            lines.extend([
                f"    @PostMapping(\"{java_path}\")",
                f"    public ResponseEntity<GeneratedResponse> {name}(@RequestBody(required = false) Map<String, Object> payload) {{",
                "        return ResponseEntity.ok(GeneratedResponse.ok());",
                "    }",
                "",
            ])
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def _java_application() -> str:
    return "\n".join([
        "package com.navigator.generated;",
        "",
        "import org.springframework.boot.SpringApplication;",
        "import org.springframework.boot.autoconfigure.SpringBootApplication;",
        "",
        "@SpringBootApplication",
        "public class GeneratedApplication {",
        "    public static void main(String[] args) {",
        "        SpringApplication.run(GeneratedApplication.class, args);",
        "    }",
        "}",
        "",
    ])


def _java_test(apis: list[dict[str, Any]]) -> str:
    method, path, _ = _endpoint_parts((apis or [{}])[0], 1)
    http_call = "get" if method == "get" else "post"
    content = ".contentType(\"application/json\").content(\"{}\")" if http_call == "post" else ""
    return "\n".join([
        "package com.navigator.generated;",
        "",
        "import org.junit.jupiter.api.Test;",
        "import org.springframework.beans.factory.annotation.Autowired;",
        "import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;",
        "import org.springframework.boot.test.context.SpringBootTest;",
        "import org.springframework.test.web.servlet.MockMvc;",
        "",
        "import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;",
        "import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;",
        "",
        "@SpringBootTest",
        "@AutoConfigureMockMvc",
        "class GeneratedControllerTest {",
        "    @Autowired",
        "    private MockMvc mockMvc;",
        "",
        "    @Test",
        "    void generatedEndpointReturnsOk() throws Exception {",
        f"        mockMvc.perform({http_call}(\"/generated{path}\"){content})",
        "            .andExpect(status().isOk())",
        "            .andExpect(jsonPath(\"$.status\").value(\"ok\"));",
        "    }",
        "}",
        "",
    ])


def _java_pom() -> str:
    return "\n".join([
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
        "<project xmlns=\"http://maven.apache.org/POM/4.0.0\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\"",
        "  xsi:schemaLocation=\"http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd\">",
        "  <modelVersion>4.0.0</modelVersion>",
        "  <groupId>com.navigator</groupId>",
        "  <artifactId>generated-backend</artifactId>",
        "  <version>0.0.1-SNAPSHOT</version>",
        "  <properties>",
        "    <java.version>17</java.version>",
        "    <spring-boot.version>3.2.5</spring-boot.version>",
        "  </properties>",
        "  <dependencyManagement>",
        "    <dependencies>",
        "      <dependency>",
        "        <groupId>org.springframework.boot</groupId>",
        "        <artifactId>spring-boot-dependencies</artifactId>",
        "        <version>${spring-boot.version}</version>",
        "        <type>pom</type>",
        "        <scope>import</scope>",
        "      </dependency>",
        "    </dependencies>",
        "  </dependencyManagement>",
        "  <dependencies>",
        "    <dependency>",
        "      <groupId>org.springframework.boot</groupId>",
        "      <artifactId>spring-boot-starter-web</artifactId>",
        "    </dependency>",
        "    <dependency>",
        "      <groupId>org.springframework.boot</groupId>",
        "      <artifactId>spring-boot-starter-test</artifactId>",
        "      <scope>test</scope>",
        "    </dependency>",
        "  </dependencies>",
        "  <build>",
        "    <plugins>",
        "      <plugin>",
        "        <groupId>org.springframework.boot</groupId>",
        "        <artifactId>spring-boot-maven-plugin</artifactId>",
        "      </plugin>",
        "    </plugins>",
        "  </build>",
        "</project>",
        "",
    ])


def _app_code() -> str:
    return "\n".join([
        "from __future__ import annotations",
        "",
        "from fastapi import FastAPI",
        "from .router import router",
        "",
        "app = FastAPI(title=\"Generated Backend API\")",
        "app.include_router(router)",
        "",
        "@app.get(\"/health\")",
        "async def health():",
        "    return {\"status\": \"ok\"}",
        "",
    ])


def _readme(goal: str, apis: list[dict[str, Any]], tables: list[dict[str, Any]]) -> str:
    api_lines = [f"- {api.get('endpoint') or api.get('ep') or 'generated endpoint'}" for api in apis or []]
    table_lines = [f"- {table.get('table_name') or table.get('nm') or 'generated table'}" for table in tables or []]
    return "\n".join([
        "# Generated Backend Scaffold",
        "",
        f"Goal: {goal}",
        "",
        "This directory is generated by the NAVIGATOR develop pipeline.",
        "Review and move the code into the real application modules before production use.",
        "",
        "## API Contracts",
        * (api_lines or ["- none"]),
        "",
        "## Table Contracts",
        * (table_lines or ["- none"]),
        "",
    ])


def _template_files(
    *,
    goal: str,
    apis: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    language: str,
    framework: str,
) -> tuple[str, str, list[tuple[str, str]]]:
    if language == "java" and framework in {"spring", "springboot", "spring-boot"}:
        target_dir = "java_spring_boot"
        test_command = "mvn test"
        files = [
            ("pom.xml", _java_pom()),
            ("src/main/java/com/navigator/generated/GeneratedApplication.java", _java_application()),
            ("src/main/java/com/navigator/generated/GeneratedController.java", _java_controller(apis)),
            ("src/main/java/com/navigator/generated/GeneratedResponse.java", _java_package(goal)),
            ("src/test/java/com/navigator/generated/GeneratedControllerTest.java", _java_test(apis)),
            ("README.md", _readme(goal, apis, tables)),
        ]
        return target_dir, test_command, files

    if language in {"typescript", "ts", "javascript", "js"} and framework in {"express", "expressjs"}:
        target_dir = "typescript_express"
        test_command = "npm install && npm test"
        files = [
            ("src/routes.ts", _express_routes_code(apis)),
            ("src/service.ts", _express_service_code(goal, apis, tables)),
            ("tests/generated-backend.test.ts", _express_test_code(apis)),
            ("package.json", _express_package_json()),
            ("tsconfig.json", _express_tsconfig()),
            ("README.md", _readme(goal, apis, tables)),
        ]

        return target_dir, test_command, files

    target_dir = "python_fastapi"
    test_command = "pytest backend/generated/navigator_dev/python_fastapi/tests -q"
    files = [
        ("navigator_dev/__init__.py", "from .router import router\n"),
        ("navigator_dev/app.py", _app_code()),
        ("navigator_dev/schemas.py", _schema_code(apis)),
        ("navigator_dev/service.py", _service_code(goal, apis, tables)),
        ("navigator_dev/router.py", _router_code(apis)),
        ("navigator_dev/README.md", _readme(goal, apis, tables)),
        ("tests/test_generated_backend.py", _test_code(apis).replace(
            "from backend.generated.navigator_dev.router import router",
            "from navigator_dev.router import router",
        )),
    ]
    return target_dir, test_command, files


def _safe_relative_path(path: str) -> Path:
    raw = Path(path.replace("\\", "/"))
    if raw.is_absolute() or ".." in raw.parts:
        raise ValueError(f"Unsafe generated path: {path}")
    return raw


def _build_llm_user_msg(
    *,
    goal: str,
    approved_stack: dict[str, Any],
    sa_contract: dict[str, Any],
    task_instruction: dict[str, Any],
    contract_handoff: dict[str, Any],
    language: str,
    framework: str,
    output_root: str,
) -> str:
    # 중복 제거: task_instruction 이미 dev_task를 포함하고 있을 수 있으므로 최상위에서 한 번만 관리
    payload = {
        "goal": goal,
        "task_instruction": task_instruction,
        "approved_stack": approved_stack,
        "sa_contract": sa_contract,
        "contract_handoff": contract_handoff,
        "language": language,
        "framework": framework,
        "output_root": output_root,
        "requirements": "Generate runnable backend files and tests under output_root using only approved_stack and sa_contract.",
        "generation_policy": {
            "no_dummy_code": True,
            "no_placeholder_business_logic": True,
            "no_unapproved_stack": True,
            "no_extra_api": True,
            "no_missing_sa_api": True,
            "preserve_request_response_fields": True,
        },
        "path_rules": [
            "Use relative file paths only.",
            "Do not use .. path segments.",
            "Do not include output_root in returned paths.",
        ],
    }
    
    msg = json.dumps(payload, ensure_ascii=False)
    print(f"\n[BackendCodegen] Final LLM Payload Size: {len(msg)} chars")
    return msg


def _llm_files(
    ctx: NodeContext,
    *,
    goal: str,
    approved_stack: dict[str, Any],
    sa_contract: dict[str, Any],
    task_instruction: dict[str, Any],
    contract_handoff: dict[str, Any],
    language: str,
    framework: str,
    output_dir: Path,
):
    res = call_structured(
        api_key=ctx.api_key,
        model=ctx.model,
        schema=BackendCodegenOutput,
        system_prompt=SYSTEM_PROMPT,
        user_msg=_build_llm_user_msg(
            goal=goal,
            approved_stack=approved_stack,
            sa_contract=sa_contract,
            task_instruction=task_instruction,
            contract_handoff=contract_handoff,
            language=language,
            framework=framework,
            output_root=str(output_dir),
        ),
        max_retries=3,
        temperature=0.1,
        compress_prompt=False,
    )
    files = [(item.path, item.content) for item in res.parsed.files]
    return res.parsed, files


def _get_blank_generated_files(files: list[tuple[str, str]]) -> list[str]:
    return [path for path, content in files if not str(content or "").strip()]


def _endpoint_key(api: dict[str, Any]) -> str:
    return normalize_api_contract(api)["full"]


def _contract_enforcement_findings(files: list[tuple[str, str]], sa_contract: dict[str, Any]) -> list[str]:
    combined = "\n".join(content for _, content in files)
    findings: list[str] = []
    for api in sa_contract.get("apis", []) or []:
        key = _endpoint_key(api)
        if not key:
            continue
        parts = key.split(" ", 1)
        path = parts[1] if len(parts) > 1 else key
        if path not in combined:
            findings.append(f"Missing SA API path in generated backend: {key}")

    blocked_terms = [
        "TODO",
        "FIXME",
        "mock business logic",
        "dummy",
        "placeholder",
        "wire this service into real domain logic",
    ]
    for term in blocked_terms:
        if term.lower() in combined.lower():
            findings.append(f"Generated backend contains forbidden placeholder marker: {term}")
    return findings


def _missing_required_template_file(generated_files: list[tuple[str, str]], template_files: list[tuple[str, str]]) -> bool:
    generated_paths = {path.replace("\\", "/") for path, _ in generated_files}
    template_paths = {path.replace("\\", "/") for path, _ in template_files}
    required = {
        path for path in template_paths
        if path.endswith(("package.json", "tsconfig.json", "pom.xml", "README.md"))
    }
    return not required.issubset(generated_paths)


def _with_required_template_files(generated_files: list[tuple[str, str]], template_files: list[tuple[str, str]]) -> list[tuple[str, str]]:
    result = list(generated_files)
    generated_paths = {path.replace("\\", "/") for path, _ in result}
    for path, content in template_files:
        normalized = path.replace("\\", "/")
        if normalized.endswith(("package.json", "tsconfig.json", "pom.xml", "README.md")) and normalized not in generated_paths:
            result.append((path, content))
    return result


def _normalize_backend_files(
    generated_files: list[tuple[str, str]],
    template_files: list[tuple[str, str]],
    *,
    language: str,
    framework: str,
) -> list[tuple[str, str]]:
    """Keep LLM source code and merge deterministic Node manifests without losing imports."""
    if language not in {"typescript", "ts", "javascript", "js"} or framework not in {"express", "expressjs"}:
        return generated_files

    template_by_path = {path.replace("\\", "/"): content for path, content in template_files}
    normalized: list[tuple[str, str]] = []
    seen: set[str] = set()
    deterministic = {"package.json", "tsconfig.json"}

    for path, content in generated_files:
        normalized_path = path.replace("\\", "/")
        if normalized_path == "package.json":
            content = _merge_node_package_json(
                generated_content=content,
                template_content=template_by_path.get(normalized_path, "{}"),
                generated_files=generated_files,
            )
        elif normalized_path in deterministic:
            content = template_by_path.get(normalized_path, content)
        normalized.append((path, content))
        seen.add(normalized_path)

    for path in deterministic:
        if path not in seen and path in template_by_path:
            content = template_by_path[path]
            if path == "package.json":
                content = _merge_node_package_json(
                    generated_content="{}",
                    template_content=content,
                    generated_files=generated_files,
                )
            normalized.append((path, content))

    return normalized


@pipeline_node("develop_backend_codegen")
def develop_backend_codegen_node(ctx: NodeContext) -> dict:
    source_dir = Path(str(ctx.sget("source_dir", "") or "")).resolve()
    language, framework, mode = _target(ctx)
    policy = _target_policy(language, framework)
    output_dir = source_dir / "backend" / "generated" / "navigator_dev" / policy["target_key"]

    if not _enabled(ctx.sget("enable_backend_codegen", False)):
        return {
            "backend_codegen_result": {
                "status": "skipped",
                "reason": "enable_backend_codegen is false",
                "output_dir": str(output_dir),
                "language": language,
                "framework": framework,
                "files": [],
            },
            "_thinking": "codegen-disabled",
        }

    if not source_dir.is_dir():
        return {
            "backend_codegen_result": {
                "status": "error",
                "reason": f"Invalid source_dir: {source_dir}",
                "files": [],
            },
            "_thinking": "invalid-source-dir",
        }

    goal = get_goal(ctx.sget)
    handoff = _contract_handoff(ctx)
    sa_contract = _sa_contract(ctx, handoff)
    approved_stack = _approved_stack(ctx, language=language, framework=framework)
    task_instruction = _task_instruction(ctx, goal=goal, handoff=handoff)
    apis = sa_contract["apis"]
    tables = sa_contract["tables"]
    if not apis:
        return {
            "backend_codegen_result": {
                "status": "error",
                "language": language,
                "framework": framework,
                "support_level": policy["support_level"],
                "verification_adapter": policy["verification_adapter"],
                "mode": mode,
                "generator": "contract",
                "output_dir": str(output_dir),
                "files": [],
                "api_count": 0,
                "table_count": len(tables),
                "approved_stack": approved_stack,
                "sa_contract": sa_contract,
                "task_instruction": task_instruction,
                "contract_handoff": handoff,
                "reason": "SA API contracts are empty; backend codegen refuses to invent APIs.",
                "notes": ["No dummy endpoint was generated because no SA API contract was provided."],
            },
            "_thinking": "backend-codegen-contract-missing",
        }

    _, test_command, template_files = _template_files(
        goal=goal,
        apis=apis,
        tables=tables,
        language=language,
        framework=framework,
    )
    generator = "template"
    notes: list[str] = []
    generated_files = template_files
    if mode != "template":
        try:
            llm_output, generated_files = _llm_files(
                ctx,
                goal=goal,
                approved_stack=approved_stack,
                sa_contract=sa_contract,
                task_instruction=task_instruction,
                contract_handoff=handoff,
                language=language,
                framework=framework,
                output_dir=output_dir,
            )
            generator = "llm"
            test_command = llm_output.test_command or test_command
            notes = llm_output.notes
            blank_files = _get_blank_generated_files(generated_files)
            if blank_files:
                reason = f"LLM backend codegen returned blank files: {', '.join(blank_files)}"
                if mode == "llm":
                    return {
                        "backend_codegen_result": {
                            "status": "error",
                            "language": language,
                            "framework": framework,
                            "support_level": policy["support_level"],
                            "verification_adapter": policy["verification_adapter"],
                            "mode": mode,
                            "generator": "llm",
                            "output_dir": str(output_dir),
                            "files": [],
                            "api_count": len(apis),
                            "table_count": len(tables),
                            "test_command": test_command,
                            "notes": notes + [f"{reason}; refusing template fallback in llm mode."],
                            "reason": reason,
                        },
                        "_thinking": "backend-codegen-llm-blank",
                    }
                generated_files = template_files
                generator = "template_fallback"
                notes.append(f"{reason}; used template fallback.")
            elif _missing_required_template_file(generated_files, template_files):
                generated_files = _with_required_template_files(generated_files, template_files)
                notes.append("LLM codegen omitted required manifest/config files; added template defaults.")
            generated_files = _normalize_backend_files(
                generated_files,
                template_files,
                language=language,
                framework=framework,
            )
            notes.append("Backend runtime manifests were normalized for deterministic verification.")
        except Exception as exc:
            import traceback
            error_detail = traceback.format_exc()
            if mode == "llm":
                return {
                    "backend_codegen_result": {
                        "status": "error",
                        "language": language,
                        "framework": framework,
                        "support_level": policy["support_level"],
                        "verification_adapter": policy["verification_adapter"],
                        "mode": mode,
                        "generator": "llm",
                        "output_dir": str(output_dir),
                        "files": [],
                        "api_count": len(apis),
                        "table_count": len(tables),
                        "test_command": test_command,
                        "notes": [f"LLM backend codegen failed; refusing template fallback in llm mode: {exc}"],
                        "reason": str(exc),
                        "traceback": error_detail,
                    },
                    "_thinking": "backend-codegen-llm-error",
                }
            notes.append(f"LLM codegen failed; used template fallback: {exc}")

    enforcement_findings = _contract_enforcement_findings(generated_files, sa_contract)
    if enforcement_findings and mode == "llm":
        return {
            "backend_codegen_result": {
                "status": "error",
                "language": language,
                "framework": framework,
                "support_level": policy["support_level"],
                "verification_adapter": policy["verification_adapter"],
                "mode": mode,
                "generator": generator,
                "output_dir": str(output_dir),
                "files": [],
                "api_count": len(apis),
                "table_count": len(tables),
                "test_command": test_command,
                "approved_stack": approved_stack,
                "sa_contract": sa_contract,
                "task_instruction": task_instruction,
                "contract_handoff": handoff,
                "contract_enforcement": {"status": "failed", "findings": enforcement_findings},
                "reason": "Generated backend violated SA contract or placeholder policy.",
                "notes": notes,
            },
            "_thinking": "backend-codegen-contract-failed",
        }
    if enforcement_findings:
        notes.extend(enforcement_findings)

    writes = []
    for relative_path, content in generated_files:
        writes.append(_write_if_changed(output_dir / _safe_relative_path(relative_path), content))
    return {
        "backend_codegen_result": {
            "status": "generated",
            "language": language,
            "framework": framework,
            "support_level": policy["support_level"],
            "verification_adapter": policy["verification_adapter"],
            "mode": mode,
            "generator": generator,
            "output_dir": str(output_dir),
            "files": writes,
            "api_count": len(apis),
            "table_count": len(tables),
            "approved_stack": approved_stack,
            "sa_contract": sa_contract,
            "task_instruction": task_instruction,
            "contract_handoff": handoff,
            "contract_enforcement": {
                "status": "passed" if not enforcement_findings else "warning",
                "findings": enforcement_findings,
            },
            "test_command": test_command,
            "notes": notes,
        },
        "_thinking": "backend-codegen, generated-scaffold, review-required",
    }
