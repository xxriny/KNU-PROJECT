from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.core.utils import call_structured
from pipeline.domain.dev.nodes.backend_codegen import _safe_name, _write_if_changed
from pipeline.domain.dev.schemas import FrontendCodegenOutput


SYSTEM_PROMPT = """# Role: Frontend code generation agent
Generate frontend source files from UIUX handoff and API contracts.

Rules:
- Return structured JSON only.
- Generate only files under the provided output_root.
- Return relative file paths only.
- Do not use .. path segments or absolute paths.
- Do not include secrets.
- Use the requested language/framework exactly when provided.
- Tests must match generated behavior.
- thinking must be Korean keywords only, max 5 words.
"""

LEGACY_SYSTEM_PROMPT = SYSTEM_PROMPT
SYSTEM_PROMPT = """
당신은 '수석 프론트엔드 코드 생성자'입니다. UIUX artifact와 SA/API 계약을 기준으로 실행 가능한 프론트엔드 scaffold를 생성하십시오.

[1. UIUX/SA 계약 준수 (MANDATORY)]
- uiux_artifact.screens, user_flows, component_tree, frontend_handoff를 구현 기준으로 삼으십시오.
- frontend_handoff.routes는 실제 라우트/화면 구조에 반영하십시오.
- frontend_handoff.api_client_needs는 src/api/client.ts에 반영하십시오.
- data_contracts와 screen_bindings를 무시하지 마십시오.
- PM requirement trace가 사라지지 않도록 화면/테스트 이름과 notes에 반영하십시오.

[2. 생성 안전 규칙 (ZERO-TOLERANCE)]
- output_root 밖의 파일을 생성하거나 수정하지 마십시오.
- path는 상대 경로만 사용하고 절대 경로와 '..'를 금지합니다.
- secret, API key, .env 파일을 생성하지 마십시오.
- 테스트는 생성된 UI와 모순되면 안 됩니다.
- markdown fence를 content에 넣지 마십시오.

[3. React/Vite 필수 규칙]
- TypeScript React Vite는 src/main.tsx, src/App.tsx, src/api/client.ts, tests를 포함하십시오.
- Vitest에서 jest-dom matcher를 쓰면 setupFiles와 tests/setup.ts를 반드시 연결하십시오.
- ImportMeta.env를 쓰면 src/vite-env.d.ts에 vite/client reference를 추가하십시오.
- node_modules 설치는 생성하지 말고 package.json scripts로 안내하십시오.

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


def _target(ctx: NodeContext) -> tuple[str, str, str]:
    language = str(ctx.sget("frontend_codegen_language", "") or "").strip().lower() or "typescript"
    framework = str(ctx.sget("frontend_codegen_framework", "") or "").strip().lower() or "react-vite"
    mode = str(ctx.sget("frontend_codegen_mode", "template") or "template").strip().lower()
    return language, framework, mode


def _target_policy(language: str, framework: str) -> dict[str, str]:
    if language in {"typescript", "ts"} and framework in {"react-vite", "vite-react", "react", "vite"}:
        return {
            "support_level": "official",
            "verification_adapter": "node",
            "target_key": "typescript_react_vite",
        }
    adapter = "node" if language in {"typescript", "ts", "javascript", "js"} else "unknown"
    return {
        "support_level": "experimental",
        "verification_adapter": adapter,
        "target_key": f"{_safe_name(language, 'typescript')}_{_safe_name(framework, 'react_vite')}",
    }


def _safe_relative_path(path: str) -> Path:
    raw = Path(path.replace("\\", "/"))
    if raw.is_absolute() or ".." in raw.parts:
        raise ValueError(f"Unsafe generated path: {path}")
    return raw


def _method_path(endpoint: str) -> tuple[str, str]:
    match = re.match(r"^(GET|POST|PUT|PATCH|DELETE)\s+(.+)$", str(endpoint or "").strip(), re.I)
    if match:
        return match.group(1).upper(), match.group(2)
    return "GET", str(endpoint or "/generated").strip() or "/generated"


def _api_client(plan: dict) -> str:
    endpoints = plan.get("api_client_needs") or []
    lines = [
        "const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';",
        "",
        "async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {",
        "  const response = await fetch(`${API_BASE_URL}${path}`, {",
        "    headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) },",
        "    ...options,",
        "  });",
        "  if (!response.ok) {",
        "    throw new Error(`Request failed: ${response.status}`);",
        "  }",
        "  return response.json() as Promise<T>;",
        "}",
        "",
        "export const apiClient = {",
    ]
    if not endpoints:
        lines.append("  health: () => requestJson<Record<string, unknown>>('/'),")
    for index, endpoint in enumerate(endpoints, start=1):
        method, path = _method_path(endpoint)
        name = f"request{index}"
        if method == "GET":
            lines.append(f"  {name}: () => requestJson<Record<string, unknown>>('{path}'),")
        else:
            lines.append(
                f"  {name}: (payload: Record<string, unknown>) => requestJson<Record<string, unknown>>('{path}', "
                f"{{ method: '{method}', body: JSON.stringify(payload) }}),"
            )
    lines.extend(["};", ""])
    return "\n".join(lines)


def _app_tsx(uiux_artifact: dict, frontend_plan: dict) -> str:
    screens = frontend_plan.get("screen_bindings") or uiux_artifact.get("screens") or []
    if not screens:
        screens = [{"screen": "Generated Screen", "route": "/", "states": ["default", "loading", "empty", "error"]}]
    screen_items = json.dumps(screens, ensure_ascii=False, indent=2)
    return "\n".join([
        "import './styles.css';",
        "",
        f"const screens = {screen_items} as const;",
        "",
        "export default function App() {",
        "  return (",
        "    <main className=\"app-shell\">",
        "      <section className=\"app-header\">",
        "        <p className=\"eyebrow\">NAVIGATOR generated frontend</p>",
        "        <h1>Generated App Flow</h1>",
        "      </section>",
        "      <section className=\"screen-grid\" aria-label=\"Generated screens\">",
        "        {screens.map((screen) => (",
        "          <article className=\"screen-card\" key={`${screen.screen}-${screen.route}`}>",
        "            <div>",
        "              <p className=\"route\">{screen.route}</p>",
        "              <h2>{screen.screen}</h2>",
        "            </div>",
        "            <ul>",
        "              {(screen.states ?? []).map((state) => (",
        "                <li key={state}>{state}</li>",
        "              ))}",
        "            </ul>",
        "          </article>",
        "        ))}",
        "      </section>",
        "    </main>",
        "  );",
        "}",
        "",
    ])


def _main_tsx() -> str:
    return "\n".join([
        "import React from 'react';",
        "import ReactDOM from 'react-dom/client';",
        "import App from './App';",
        "",
        "ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(",
        "  <React.StrictMode>",
        "    <App />",
        "  </React.StrictMode>,",
        ");",
        "",
    ])


def _styles_css() -> str:
    return "\n".join([
        ":root {",
        "  font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;",
        "  color: #172026;",
        "  background: #f5f7f8;",
        "}",
        "",
        "body {",
        "  margin: 0;",
        "}",
        "",
        ".app-shell {",
        "  min-height: 100vh;",
        "  padding: 32px;",
        "}",
        "",
        ".app-header {",
        "  max-width: 960px;",
        "  margin: 0 auto 24px;",
        "}",
        "",
        ".eyebrow, .route {",
        "  margin: 0 0 8px;",
        "  color: #5f6f73;",
        "  font-size: 13px;",
        "}",
        "",
        "h1, h2 {",
        "  margin: 0;",
        "}",
        "",
        ".screen-grid {",
        "  max-width: 960px;",
        "  margin: 0 auto;",
        "  display: grid;",
        "  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));",
        "  gap: 16px;",
        "}",
        "",
        ".screen-card {",
        "  background: #ffffff;",
        "  border: 1px solid #d8e0e3;",
        "  border-radius: 8px;",
        "  padding: 20px;",
        "}",
        "",
        ".screen-card ul {",
        "  margin: 16px 0 0;",
        "  padding-left: 18px;",
        "}",
        "",
    ])


def _package_json() -> str:
    return json.dumps({
        "type": "module",
        "scripts": {
            "dev": "vite",
            "build": "tsc --noEmit && vite build",
            "test": "vitest run",
            "typecheck": "tsc --noEmit",
        },
        "dependencies": {
            "@vitejs/plugin-react": "^4.2.1",
            "vite": "^5.2.0",
            "react": "^18.2.0",
            "react-dom": "^18.2.0",
            "react-router-dom": "^6.22.1",
        },
        "devDependencies": {
            "@testing-library/jest-dom": "^6.4.2",
            "@testing-library/react": "^14.2.1",
            "@types/react": "^18.2.66",
            "@types/react-dom": "^18.2.22",
            "jsdom": "^24.0.0",
            "typescript": "^5.4.0",
            "vitest": "^1.6.0",
        },
    }, indent=2)


def _tsconfig() -> str:
    return json.dumps({
        "compilerOptions": {
            "target": "ES2020",
            "useDefineForClassFields": True,
            "lib": ["DOM", "DOM.Iterable", "ES2020"],
            "allowJs": False,
            "skipLibCheck": True,
            "esModuleInterop": True,
            "allowSyntheticDefaultImports": True,
            "strict": True,
            "forceConsistentCasingInFileNames": True,
            "module": "ESNext",
            "moduleResolution": "Node",
            "resolveJsonModule": True,
            "isolatedModules": True,
            "noEmit": True,
            "jsx": "react-jsx",
            "types": ["vitest/globals", "@testing-library/jest-dom"],
            "noUnusedLocals": False,
            "noUnusedParameters": False,
        },
        "include": ["src", "tests", "vite.config.ts"],
    }, indent=2)


def _vite_config() -> str:
    return "\n".join([
        "import { defineConfig } from 'vite';",
        "import react from '@vitejs/plugin-react';",
        "",
        "export default defineConfig({",
        "  plugins: [react()],",
        "  test: {",
        "    environment: 'jsdom',",
        "    globals: true,",
        "    setupFiles: './tests/setup.ts',",
        "  },",
        "});",
        "",
    ])


def _test_tsx() -> str:
    return "\n".join([
        "import { render, screen } from '@testing-library/react';",
        "import { cleanup } from '@testing-library/react';",
        "import { MemoryRouter } from 'react-router-dom';",
        "import { describe, expect, it } from 'vitest';",
        "import App from '../src/App';",
        "",
        "function renderGeneratedApp() {",
        "  try {",
        "    return render(<App />);",
        "  } catch (error) {",
        "    cleanup();",
        "    if (String(error).toLowerCase().includes('router')) {",
        "      return render(",
        "        <MemoryRouter>",
        "          <App />",
        "        </MemoryRouter>,",
        "      );",
        "    }",
        "    throw error;",
        "  }",
        "}",
        "",
        "describe('App', () => {",
        "  it('renders generated frontend without crashing', () => {",
        "    renderGeneratedApp();",
        "    expect(document.body.textContent?.trim().length ?? 0).toBeGreaterThan(0);",
        "    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();",
        "  });",
        "});",
        "",
    ])


def _setup_tests() -> str:
    return "import '@testing-library/jest-dom/vitest';\n"


def _vite_env() -> str:
    return "/// <reference types=\"vite/client\" />\n"


def _index_html() -> str:
    return "\n".join([
        "<!doctype html>",
        "<html lang=\"en\">",
        "  <head>",
        "    <meta charset=\"UTF-8\" />",
        "    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />",
        "    <title>NAVIGATOR Generated Frontend</title>",
        "  </head>",
        "  <body>",
        "    <div id=\"root\"></div>",
        "    <script type=\"module\" src=\"/src/main.tsx\"></script>",
        "  </body>",
        "</html>",
        "",
    ])


def _template_files(uiux_artifact: dict, frontend_plan: dict) -> tuple[str, list[tuple[str, str]]]:
    return "npm install && npm test", [
        ("package.json", _package_json()),
        ("tsconfig.json", _tsconfig()),
        ("vite.config.ts", _vite_config()),
        ("index.html", _index_html()),
        ("src/main.tsx", _main_tsx()),
        ("src/App.tsx", _app_tsx(uiux_artifact, frontend_plan)),
        ("src/styles.css", _styles_css()),
        ("src/api/client.ts", _api_client(frontend_plan)),
        ("src/vite-env.d.ts", _vite_env()),
        ("tests/App.test.tsx", _test_tsx()),
        ("tests/setup.ts", _setup_tests()),
    ]


def _llm_user_msg(*, uiux_artifact: dict, frontend_result: dict, output_root: str, language: str, framework: str) -> str:
    return json.dumps({
        "language": language,
        "framework": framework,
        "output_root": output_root,
        "uiux_artifact": uiux_artifact,
        "frontend_result": frontend_result,
        "requirements": "Generate runnable frontend scaffold files and tests under output_root.",
        "path_rules": ["Use relative file paths only.", "Do not use .. path segments."],
    }, ensure_ascii=False)


def _has_blank_generated_file(files: list[tuple[str, str]]) -> bool:
    return any(not str(content or "").strip() for _, content in files)


def _blank_generated_paths(files: list[tuple[str, str]]) -> list[str]:
    return [path for path, content in files if not str(content or "").strip()]


def _without_blank_generated_files(files: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(path, content) for path, content in files if str(content or "").strip()]


def _blank_required_frontend_paths(files: list[tuple[str, str]]) -> list[str]:
    required = {"package.json", "tsconfig.json", "vite.config.ts", "index.html", "src/main.tsx", "src/App.tsx"}
    return [
        path
        for path, content in files
        if path.replace("\\", "/") in required and not str(content or "").strip()
    ]


def _missing_required_template_file(generated_files: list[tuple[str, str]], template_files: list[tuple[str, str]]) -> bool:
    generated_paths = {path.replace("\\", "/") for path, _ in generated_files}
    template_paths = {path.replace("\\", "/") for path, _ in template_files}
    required = {
        path for path in template_paths
        if path in {"package.json", "tsconfig.json", "vite.config.ts", "index.html", "src/main.tsx"}
    }
    return not required.issubset(generated_paths)


def _with_required_template_files(generated_files: list[tuple[str, str]], template_files: list[tuple[str, str]]) -> list[tuple[str, str]]:
    result = list(generated_files)
    generated_paths = {path.replace("\\", "/") for path, _ in result}
    required = {"package.json", "tsconfig.json", "vite.config.ts", "index.html", "src/main.tsx"}
    for path, content in template_files:
        normalized = path.replace("\\", "/")
        if normalized in required and normalized not in generated_paths:
            result.append((path, content))
    return result


def _is_test_file(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    name = Path(normalized).name
    return (
        normalized.startswith("tests/")
        or name.endswith(".test.ts")
        or name.endswith(".test.tsx")
        or name.endswith(".spec.ts")
        or name.endswith(".spec.tsx")
    )


def _frontend_smoke_test_files(template_files: list[tuple[str, str]]) -> list[tuple[str, str]]:
    keep = {"tests/App.test.tsx", "tests/setup.ts"}
    return [(path, content) for path, content in template_files if path.replace("\\", "/") in keep]


def _normalize_frontend_files(generated_files: list[tuple[str, str]], template_files: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Keep LLM app code, but make Vite/Vitest manifests and tests deterministic."""
    template_by_path = {path.replace("\\", "/"): content for path, content in template_files}
    normalized: list[tuple[str, str]] = []
    seen: set[str] = set()
    deterministic = {
        "package.json",
        "tsconfig.json",
        "vite.config.ts",
        "src/vite-env.d.ts",
    }

    for path, content in generated_files:
        normalized_path = path.replace("\\", "/")
        if _is_test_file(normalized_path):
            continue
        if normalized_path in deterministic:
            content = template_by_path.get(normalized_path, content)
        normalized.append((path, content))
        seen.add(normalized_path)

    for path, content in template_files:
        normalized_path = path.replace("\\", "/")
        if normalized_path in deterministic and normalized_path not in seen:
            normalized.append((path, content))
            seen.add(normalized_path)

    for path, content in _frontend_smoke_test_files(template_files):
        normalized_path = path.replace("\\", "/")
        if normalized_path not in seen:
            normalized.append((path, content))
            seen.add(normalized_path)

    return normalized


@pipeline_node("develop_frontend_codegen")
def develop_frontend_codegen_node(ctx: NodeContext) -> dict:
    if not _enabled(ctx.sget("enable_frontend_codegen", False)):
        return {
            "frontend_codegen_result": {
                "status": "skipped",
                "reason": "enable_frontend_codegen is false",
                "files": [],
            },
            "_thinking": "frontend-codegen-disabled",
        }

    source_dir = Path(str(ctx.sget("source_dir", "") or "")).resolve()
    if not source_dir.is_dir():
        return {
            "frontend_codegen_result": {
                "status": "error",
                "reason": f"Invalid source_dir: {source_dir}",
                "files": [],
            },
            "_thinking": "frontend-invalid-source",
        }

    language, framework, mode = _target(ctx)
    policy = _target_policy(language, framework)
    output_dir = source_dir / "frontend" / "generated" / "navigator_dev" / policy["target_key"]
    frontend_result = ctx.sget("frontend_result", {}) or {}
    uiux_artifact = ctx.sget("uiux_artifact", {}) or {}
    frontend_plan = frontend_result.get("frontend_plan") or {}
    test_command, template_files = _template_files(uiux_artifact, frontend_plan)
    generated_files = template_files
    generator = "template"
    notes: list[str] = []

    if mode != "template":
        try:
            res = call_structured(
                api_key=ctx.api_key,
                model=ctx.model,
                schema=FrontendCodegenOutput,
                system_prompt=SYSTEM_PROMPT,
                user_msg=_llm_user_msg(
                    uiux_artifact=uiux_artifact,
                    frontend_result=frontend_result,
                    output_root=str(output_dir),
                    language=language,
                    framework=framework,
                ),
                max_retries=3,
                temperature=0.1,
                compress_prompt=False,
            )
            generated_files = [(item.path, item.content) for item in res.parsed.files]
            test_command = res.parsed.test_command or test_command
            notes = res.parsed.notes
            generator = "llm"
            blank_paths = _blank_generated_paths(generated_files)
            blank_required_paths = _blank_required_frontend_paths(generated_files)
            if blank_paths:
                if mode == "llm":
                    if blank_required_paths:
                        return {
                            "frontend_codegen_result": {
                                "status": "error",
                                "language": language,
                                "framework": framework,
                                "support_level": policy["support_level"],
                                "verification_adapter": policy["verification_adapter"],
                                "mode": mode,
                                "generator": "llm",
                                "output_dir": str(output_dir),
                                "files": [],
                                "test_command": test_command,
                                "notes": notes + [
                                    f"LLM frontend codegen returned blank required files: {', '.join(blank_required_paths)}"
                                ],
                                "reason": "LLM frontend codegen returned blank required files.",
                            },
                            "_thinking": "frontend-codegen-required-blank",
                        }
                    generated_files = _without_blank_generated_files(generated_files)
                    notes.append(f"LLM frontend codegen returned blank file entries and they were ignored: {', '.join(blank_paths)}")
                    if not generated_files:
                        return {
                            "frontend_codegen_result": {
                                "status": "error",
                                "language": language,
                                "framework": framework,
                                "support_level": policy["support_level"],
                                "verification_adapter": policy["verification_adapter"],
                                "mode": mode,
                                "generator": "llm",
                                "output_dir": str(output_dir),
                                "files": [],
                                "test_command": test_command,
                                "notes": notes,
                                "reason": "LLM frontend codegen returned only blank files.",
                            },
                            "_thinking": "frontend-codegen-llm-blank",
                        }
                else:
                    generated_files = template_files
                    generator = "template_fallback"
                    notes.append("LLM frontend codegen returned blank files; used template fallback.")
            if _missing_required_template_file(generated_files, template_files):
                generated_files = _with_required_template_files(generated_files, template_files)
                notes.append("LLM frontend codegen omitted required manifest/config files; added template defaults.")
            generated_files = _normalize_frontend_files(generated_files, template_files)
            notes.append("Frontend manifests and smoke tests were normalized for deterministic verification.")
        except Exception as exc:
            if mode == "llm":
                return {
                    "frontend_codegen_result": {
                        "status": "error",
                        "language": language,
                        "framework": framework,
                        "support_level": policy["support_level"],
                        "verification_adapter": policy["verification_adapter"],
                        "mode": mode,
                        "generator": "llm",
                        "output_dir": str(output_dir),
                        "files": [],
                        "test_command": test_command,
                        "notes": [f"LLM frontend codegen failed; refusing template fallback in llm mode: {exc}"],
                        "reason": str(exc),
                    },
                    "_thinking": "frontend-codegen-llm-error",
                }
            notes.append(f"LLM frontend codegen failed; used template fallback: {exc}")

    writes = []
    for relative_path, content in generated_files:
        writes.append(_write_if_changed(output_dir / _safe_relative_path(relative_path), content))

    return {
        "frontend_codegen_result": {
            "status": "generated",
            "language": language,
            "framework": framework,
            "support_level": policy["support_level"],
            "verification_adapter": policy["verification_adapter"],
            "mode": mode,
            "generator": generator,
            "output_dir": str(output_dir),
            "files": writes,
            "test_command": test_command,
            "notes": notes,
        },
        "_thinking": "frontend-codegen-generated",
    }
