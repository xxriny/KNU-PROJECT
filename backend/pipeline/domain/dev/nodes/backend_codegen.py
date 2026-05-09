from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.core.utils import call_structured
from pipeline.domain.dev.nodes._shared import get_apis, get_goal, get_tables, slugify
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
- requirement_id, API endpoint, DB table/field 계약을 임의로 바꾸지 마십시오.
- SA에 없는 API를 임의로 양산하지 마십시오. 필요한 경우 notes에 "계약 외 제안"으로만 남기십시오.
- API 필드명과 DB 컬럼명은 계약에 있는 이름을 우선 사용하십시오.
- 인증/권한/검증/차단 규칙은 API 동작 또는 테스트에 반드시 반영하십시오.

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
    raw = str(api.get("endpoint") or api.get("ep") or "").strip()
    match = re.match(r"^(GET|POST|PUT|PATCH|DELETE)\s+(.+)$", raw, re.I)
    if match:
        method = match.group(1).lower()
        path = match.group(2).strip()
    else:
        method = "post"
        path = raw or f"/generated/action-{index}"
    if not path.startswith("/"):
        path = f"/{path}"
    stem = _safe_name(path.replace("{", "").replace("}", ""), f"endpoint_{index}")
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
        "    \"\"\"Generated service scaffold. Replace in-memory logic with project repositories.\"\"\"",
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
        "            \"next_step\": \"wire this service into real domain logic and persistence\",",
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
        "    nextStep: 'wire this service into real domain logic and persistence',",
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
            ("package.generated.json", _express_package_json()),
            ("tsconfig.json", _express_tsconfig()),
            ("README.md", _readme(goal, apis, tables)),
        ]
        return target_dir, test_command, files

    target_dir = "python_fastapi"
    test_command = "pytest backend/generated/navigator_dev/python_fastapi/tests -q"
    files = [
        ("navigator_dev/__init__.py", "from .router import router\n"),
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
    apis: list[dict[str, Any]],
    tables: list[dict[str, Any]],
    language: str,
    framework: str,
    output_root: str,
) -> str:
    return json.dumps({
        "goal": goal,
        "language": language,
        "framework": framework,
        "output_root": output_root,
        "apis": apis,
        "tables": tables,
        "requirements": "Generate runnable backend scaffold files and tests under output_root.",
        "path_rules": [
            "Use relative file paths only.",
            "Do not use .. path segments.",
            "Do not include output_root in returned paths.",
        ],
    }, ensure_ascii=False)


def _llm_files(ctx: NodeContext, *, goal: str, apis: list[dict[str, Any]], tables: list[dict[str, Any]], language: str, framework: str, output_dir: Path):
    res = call_structured(
        api_key=ctx.api_key,
        model=ctx.model,
        schema=BackendCodegenOutput,
        system_prompt=SYSTEM_PROMPT,
        user_msg=_build_llm_user_msg(
            goal=goal,
            apis=apis,
            tables=tables,
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


def _has_blank_generated_file(files: list[tuple[str, str]]) -> bool:
    return any(not str(content or "").strip() for _, content in files)


def _missing_required_template_file(generated_files: list[tuple[str, str]], template_files: list[tuple[str, str]]) -> bool:
    generated_paths = {path.replace("\\", "/") for path, _ in generated_files}
    template_paths = {path.replace("\\", "/") for path, _ in template_files}
    required = {
        path for path in template_paths
        if path.endswith(("package.generated.json", "package.json", "tsconfig.json", "pom.xml", "README.md"))
    }
    return not required.issubset(generated_paths)


def _with_required_template_files(generated_files: list[tuple[str, str]], template_files: list[tuple[str, str]]) -> list[tuple[str, str]]:
    result = list(generated_files)
    generated_paths = {path.replace("\\", "/") for path, _ in result}
    for path, content in template_files:
        normalized = path.replace("\\", "/")
        if normalized.endswith(("package.generated.json", "package.json", "tsconfig.json", "pom.xml", "README.md")) and normalized not in generated_paths:
            result.append((path, content))
    return result


def _normalize_backend_files(
    generated_files: list[tuple[str, str]],
    template_files: list[tuple[str, str]],
    *,
    language: str,
    framework: str,
) -> list[tuple[str, str]]:
    """Keep LLM source code, but force known runtime manifests for official Node targets."""
    if language not in {"typescript", "ts", "javascript", "js"} or framework not in {"express", "expressjs"}:
        return generated_files

    template_by_path = {path.replace("\\", "/"): content for path, content in template_files}
    normalized: list[tuple[str, str]] = []
    seen: set[str] = set()
    deterministic = {"package.generated.json", "tsconfig.json"}

    for path, content in generated_files:
        normalized_path = path.replace("\\", "/")
        if normalized_path in deterministic:
            content = template_by_path.get(normalized_path, content)
        normalized.append((path, content))
        seen.add(normalized_path)

    for path in deterministic:
        if path not in seen and path in template_by_path:
            normalized.append((path, template_by_path[path]))

    return normalized


@pipeline_node("develop_backend_codegen")
def develop_backend_codegen_node(ctx: NodeContext) -> dict:
    if not _enabled(ctx.sget("enable_backend_codegen", False)):
        return {
            "backend_codegen_result": {
                "status": "skipped",
                "reason": "enable_backend_codegen is false",
                "files": [],
            },
            "_thinking": "codegen-disabled",
        }

    source_dir = Path(str(ctx.sget("source_dir", "") or "")).resolve()
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
    apis = get_apis(ctx.sget)
    tables = get_tables(ctx.sget)
    language, framework, mode = _target(ctx)
    policy = _target_policy(language, framework)
    if not apis:
        apis = [{"endpoint": f"POST /{slugify(goal)[:32] or 'generated'}"}]

    target_dir, test_command, template_files = _template_files(
        goal=goal,
        apis=apis,
        tables=tables,
        language=language,
        framework=framework,
    )
    output_dir = source_dir / "backend" / "generated" / "navigator_dev" / policy["target_key"]
    generator = "template"
    notes: list[str] = []
    generated_files = template_files
    if mode != "template":
        try:
            llm_output, generated_files = _llm_files(
                ctx,
                goal=goal,
                apis=apis,
                tables=tables,
                language=language,
                framework=framework,
                output_dir=output_dir,
            )
            generator = "llm"
            test_command = llm_output.test_command or test_command
            notes = llm_output.notes
            if _has_blank_generated_file(generated_files):
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
                            "notes": notes + ["LLM backend codegen returned blank files; refusing template fallback in llm mode."],
                            "reason": "LLM backend codegen returned blank files.",
                        },
                        "_thinking": "backend-codegen-llm-blank",
                    }
                generated_files = template_files
                generator = "template_fallback"
                notes.append("LLM codegen returned blank files; used template fallback.")
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
                    },
                    "_thinking": "backend-codegen-llm-error",
                }
            notes.append(f"LLM codegen failed; used template fallback: {exc}")

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
            "test_command": test_command,
            "notes": notes,
        },
        "_thinking": "backend-codegen, generated-scaffold, review-required",
    }
