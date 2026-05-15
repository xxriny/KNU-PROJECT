from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.core.utils import call_structured
from pipeline.domain.dev.nodes.backend_codegen import _resolve_repo_layout, _safe_name, _write_if_changed
from pipeline.domain.dev.nodes._shared import (
    approved_stack_for_domain,
    generation_policy,
    get_apis,
    get_components,
    get_tables,
    placeholder_policy_findings,
)
from pipeline.domain.dev.schemas import FrontendCodegenOutput


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


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


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
        "  health: () => requestJson<Record<string, unknown>>('/'),",
    ]
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


def _design_tokens_json() -> str:
    return json.dumps({
        "$schema": "https://tr.designtokens.org/format/",
        "color": {
            "brand": {
                "primary": {"$type": "color", "$value": "#2563eb"},
                "surface": {"$type": "color", "$value": "#ffffff"},
                "background": {"$type": "color", "$value": "#f5f7f8"},
                "text": {"$type": "color", "$value": "#172026"},
                "muted": {"$type": "color", "$value": "#5f6f73"},
            },
            "state": {
                "error": {"$type": "color", "$value": "#b42318"},
                "success": {"$type": "color", "$value": "#067647"},
                "warning": {"$type": "color", "$value": "#b54708"},
            },
        },
        "radius": {
            "card": {"$type": "dimension", "$value": "8px"},
            "control": {"$type": "dimension", "$value": "6px"},
        },
        "space": {
            "sm": {"$type": "dimension", "$value": "8px"},
            "md": {"$type": "dimension", "$value": "16px"},
            "lg": {"$type": "dimension", "$value": "24px"},
            "xl": {"$type": "dimension", "$value": "32px"},
        },
    }, indent=2)


def _tokens_css() -> str:
    return "\n".join([
        ":root {",
        "  --color-brand-primary: #2563eb;",
        "  --color-brand-surface: #ffffff;",
        "  --color-brand-background: #f5f7f8;",
        "  --color-brand-text: #172026;",
        "  --color-brand-muted: #5f6f73;",
        "  --color-state-error: #b42318;",
        "  --color-state-success: #067647;",
        "  --color-state-warning: #b54708;",
        "  --radius-card: 8px;",
        "  --radius-control: 6px;",
        "  --space-sm: 8px;",
        "  --space-md: 16px;",
        "  --space-lg: 24px;",
        "  --space-xl: 32px;",
        "}",
        "",
    ])


def _tailwind_config() -> str:
    return "\n".join([
        "/** @type {import('tailwindcss').Config} */",
        "export default {",
        "  content: ['./index.html', './src/**/*.{ts,tsx}'],",
        "  theme: {",
        "    extend: {",
        "      colors: {",
        "        brand: {",
        "          primary: 'var(--color-brand-primary)',",
        "          surface: 'var(--color-brand-surface)',",
        "          background: 'var(--color-brand-background)',",
        "          text: 'var(--color-brand-text)',",
        "          muted: 'var(--color-brand-muted)',",
        "        },",
        "      },",
        "      borderRadius: { card: 'var(--radius-card)', control: 'var(--radius-control)' },",
        "      spacing: { sm: 'var(--space-sm)', md: 'var(--space-md)', lg: 'var(--space-lg)', xl: 'var(--space-xl)' },",
        "    },",
        "  },",
        "};",
        "",
    ])


def _fsm_json(uiux_artifact: dict, frontend_plan: dict) -> str:
    routes = frontend_plan.get("routes") or (uiux_artifact.get("frontend_handoff") or {}).get("routes") or ["/"]
    states = ["idle", "loading", "success", "empty", "error"]
    return json.dumps({
        "id": "navigatorGeneratedUi",
        "initial": "idle",
        "context": {"routes": routes},
        "states": {
            state: {"on": {}}
            for state in states
        },
        "transitions": [
            {"from": "idle", "event": "FETCH", "to": "loading"},
            {"from": "loading", "event": "RESOLVE", "to": "success"},
            {"from": "loading", "event": "RESOLVE_EMPTY", "to": "empty"},
            {"from": "loading", "event": "REJECT", "to": "error"},
            {"from": "error", "event": "RETRY", "to": "loading"},
        ],
    }, indent=2)


def _fsm_store() -> str:
    return "\n".join([
        "import { create } from 'zustand';",
        "",
        "export type UiState = 'idle' | 'loading' | 'success' | 'empty' | 'error';",
        "export type UiEvent = 'FETCH' | 'RESOLVE' | 'RESOLVE_EMPTY' | 'REJECT' | 'RETRY' | 'RESET';",
        "",
        "const transitions: Record<UiState, Partial<Record<UiEvent, UiState>>> = {",
        "  idle: { FETCH: 'loading' },",
        "  loading: { RESOLVE: 'success', RESOLVE_EMPTY: 'empty', REJECT: 'error' },",
        "  success: { FETCH: 'loading', RESET: 'idle' },",
        "  empty: { FETCH: 'loading', RESET: 'idle' },",
        "  error: { RETRY: 'loading', RESET: 'idle' },",
        "};",
        "",
        "type UiStore = {",
        "  state: UiState;",
        "  send: (event: UiEvent) => void;",
        "};",
        "",
        "export const useUiMachine = create<UiStore>((set, get) => ({",
        "  state: 'idle',",
        "  send: (event) => {",
        "    const next = transitions[get().state][event];",
        "    if (next) set({ state: next });",
        "  },",
        "}));",
        "",
    ])


def _openapi_document(plan: dict) -> str:
    paths: dict[str, Any] = {}
    for endpoint in plan.get("api_client_needs") or []:
        method, path = _method_path(endpoint)
        normalized_path = path or "/generated"
        paths.setdefault(normalized_path, {})[method.lower()] = {
            "operationId": _safe_name(f"{method}_{normalized_path}", "generated_operation"),
            "responses": {
                "200": {
                    "description": "Generated response matching SA contract",
                    "content": {
                        "application/json": {
                            "schema": {"type": "object", "additionalProperties": True}
                        }
                    },
                }
            },
        }
    return json.dumps({
        "openapi": "3.0.3",
        "info": {"title": "NAVIGATOR Generated API", "version": "0.1.0"},
        "paths": paths or {"/": {"get": {"operationId": "health", "responses": {"200": {"description": "OK"}}}}},
    }, indent=2)


def _generated_api_types(plan: dict) -> str:
    endpoints = plan.get("api_client_needs") or []
    lines = [
        "export type ApiRecord = Record<string, unknown>;",
        "",
        "export type GeneratedEndpoint =",
    ]
    if endpoints:
        for endpoint in endpoints:
            lines.append(f"  | {json.dumps(str(endpoint))}")
    else:
        lines.append("  | '/'")
    lines.extend([
        ";",
        "",
        "export type GeneratedApiResponse<T extends GeneratedEndpoint = GeneratedEndpoint> = {",
        "  endpoint: T;",
        "  data: ApiRecord;",
        "};",
        "",
    ])
    return "\n".join(lines)


def _contract_registry(uiux_artifact: dict, frontend_plan: dict) -> str:
    handoff = uiux_artifact.get("frontend_handoff") or {}
    routes = frontend_plan.get("routes") or handoff.get("routes") or []
    api_client_needs = frontend_plan.get("api_client_needs") or handoff.get("api_client_needs") or []
    data_contracts = frontend_plan.get("data_contracts") or handoff.get("data_contracts") or []
    screens = frontend_plan.get("screen_bindings") or uiux_artifact.get("screens") or []
    return "\n".join([
        "export const generatedRoutes = " + json.dumps(routes, ensure_ascii=False, indent=2) + " as const;",
        "",
        "export const generatedApiClientNeeds = " + json.dumps(api_client_needs, ensure_ascii=False, indent=2) + " as const;",
        "",
        "export const generatedDataContracts = " + json.dumps(data_contracts, ensure_ascii=False, indent=2) + " as const;",
        "",
        "export const generatedScreens = " + json.dumps(screens, ensure_ascii=False, indent=2) + " as const;",
        "",
    ])


def _query_client() -> str:
    return "\n".join([
        "import { QueryClient } from '@tanstack/react-query';",
        "",
        "export const queryClient = new QueryClient({",
        "  defaultOptions: {",
        "    queries: {",
        "      retry: 1,",
        "      staleTime: 30_000,",
        "      refetchOnWindowFocus: false,",
        "    },",
        "    mutations: {",
        "      retry: 0,",
        "    },",
        "  },",
        "});",
        "",
    ])


def _query_hooks(plan: dict) -> str:
    endpoints = plan.get("api_client_needs") or []
    first_get_index = next(
        (index for index, endpoint in enumerate(endpoints, start=1) if _method_path(endpoint)[0] == "GET"),
        None,
    )
    first_get = endpoints[first_get_index - 1] if first_get_index is not None else None
    path = _method_path(first_get)[1] if first_get else "/"
    query_fn = f"apiClient.request{first_get_index}()" if first_get_index is not None else "apiClient.health()"
    return "\n".join([
        "import { useQuery } from '@tanstack/react-query';",
        "import { apiClient } from './client';",
        "",
        "export function useGeneratedData() {",
        "  return useQuery({",
        f"    queryKey: ['generated-data', {json.dumps(path)}],",
        "    queryFn: async () => {",
        f"      return {query_fn};",
        "    },",
        "  });",
        "}",
        "",
    ])


def _app_tsx(uiux_artifact: dict, frontend_plan: dict) -> str:
    screens = frontend_plan.get("screen_bindings") or uiux_artifact.get("screens") or []
    if not screens:
        screens = [{"screen": "Generated Screen", "route": "/", "states": ["default", "loading", "empty", "error"]}]
    screen_items = json.dumps(screens, ensure_ascii=False, indent=2)
    return "\n".join([
        "import './styles.css';",
        "",
        "type ScreenItem = {",
        "  id?: string;",
        "  screen?: string;",
        "  name?: string;",
        "  title?: string;",
        "  route?: string;",
        "  states?: readonly string[];",
        "  [key: string]: unknown;",
        "};",
        "",
        f"const screens = {screen_items} as readonly ScreenItem[];",
        "",
        "const normalizedScreens = screens.map((screen) => ({",
        "  ...screen,",
        "  screen: screen.screen ?? screen.name ?? screen.title ?? screen.id ?? 'Generated Screen',",
        "  route: screen.route ?? '/',",
        "  states: screen.states ?? [],",
        "}));",
        "",
        "export default function App() {",
        "  return (",
        "    <main className=\"app-shell\">",
        "      <section className=\"app-header\">",
        "        <p className=\"eyebrow\">NAVIGATOR generated frontend</p>",
        "        <h1>Generated App Flow</h1>",
        "      </section>",
        "      <section className=\"screen-grid\" aria-label=\"Generated screens\">",
        "        {normalizedScreens.map((screen) => (",
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
        "import { QueryClientProvider } from '@tanstack/react-query';",
        "import App from './App';",
        "import { queryClient } from './api/queryClient';",
        "",
        "ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(",
        "  <React.StrictMode>",
        "    <QueryClientProvider client={queryClient}>",
        "      <App />",
        "    </QueryClientProvider>",
        "  </React.StrictMode>,",
        ");",
        "",
    ])


def _styles_css() -> str:
    return "\n".join([
        "@import './styles/tokens.css';",
        "",
        ":root {",
        "  font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;",
        "  color: var(--color-brand-text);",
        "  background: var(--color-brand-background);",
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
        "  background: var(--color-brand-surface);",
        "  border: 1px solid #d8e0e3;",
        "  border-radius: var(--radius-card);",
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
            "zustand": "^4.5.2",
            "@tanstack/react-query": "^5.28.4",
        },
        "devDependencies": {
            "@testing-library/jest-dom": "^6.4.2",
            "@testing-library/react": "^14.2.1",
            "@types/react": "^18.2.66",
            "@types/react-dom": "^18.2.22",
            "jsdom": "^24.0.0",
            "typescript": "^5.4.0",
            "vitest": "^1.6.0",
            "@openapitools/openapi-generator-cli": "^2.13.4",
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
        ("tailwind.config.js", _tailwind_config()),
        ("design-tokens.json", _design_tokens_json()),
        ("openapi.generated.json", _openapi_document(frontend_plan)),
        ("fsm.generated.json", _fsm_json(uiux_artifact, frontend_plan)),
        ("index.html", _index_html()),
        ("src/main.tsx", _main_tsx()),
        ("src/App.tsx", _app_tsx(uiux_artifact, frontend_plan)),
        ("src/styles.css", _styles_css()),
        ("src/styles/tokens.css", _tokens_css()),
        ("src/api/client.ts", _api_client(frontend_plan)),
        ("src/api/generated.ts", _generated_api_types(frontend_plan)),
        ("src/api/queryClient.ts", _query_client()),
        ("src/api/hooks.ts", _query_hooks(frontend_plan)),
        ("src/generated-contracts.ts", _contract_registry(uiux_artifact, frontend_plan)),
        ("src/state/uiMachine.ts", _fsm_store()),
        ("src/vite-env.d.ts", _vite_env()),
        ("tests/App.test.tsx", _test_tsx()),
        ("tests/setup.ts", _setup_tests()),
    ]


def _frontend_task_instruction(ctx: NodeContext, *, frontend_result: dict) -> dict[str, Any]:
    spec = ctx.sget("frontend_task_spec", {}) or {}
    dev_task = spec.get("dev_task") or {}
    dev_context = dev_task.get("context") or {}
    return {
        "dev_task": dev_task,
        "domain": "frontend",
        "goal": spec.get("goal") or ctx.sget("develop_goal", ""),
        "feature_id": spec.get("feature_id") or ctx.sget("current_feature_id", ""),
        "requirement_ids": _as_list(spec.get("requirement_ids")),
        "focus": _as_list(spec.get("focus")),
        "inputs": _as_list(spec.get("inputs")),
        "target_components": _as_list(dev_context.get("target_components")) or _as_list(spec.get("target_components")),
        "acceptance_criteria": _as_list(spec.get("acceptance_criteria")),
        "rework_instruction": dev_context.get("rework_instruction") or spec.get("rework_instruction") or frontend_result.get("rework_instruction") or {},
    }


def _frontend_sa_contract(ctx: NodeContext, *, frontend_result: dict, uiux_artifact: dict) -> dict[str, Any]:
    spec = ctx.sget("frontend_task_spec", {}) or {}
    dev_task = spec.get("dev_task") or {}
    dev_context = dev_task.get("context") or {}
    frontend_plan = frontend_result.get("frontend_plan") or {}
    handoff = uiux_artifact.get("frontend_handoff") or {}
    return {
        "source": "frontend_task_spec.dev_task.context|frontend_result.frontend_plan|uiux_artifact.frontend_handoff|sa_bundle.data",
        "apis": [item for item in (_as_list(dev_context.get("target_api_specs")) or get_apis(ctx.sget)) if isinstance(item, dict)],
        "tables": [item for item in (_as_list(dev_context.get("target_table_specs")) or get_tables(ctx.sget)) if isinstance(item, dict)],
        "components": [item for item in (_as_list(dev_context.get("component_specs")) or get_components(ctx.sget)) if isinstance(item, dict)],
        "routes": _as_list(frontend_plan.get("routes")) or _as_list(handoff.get("routes")),
        "api_client_needs": _as_list(frontend_plan.get("api_client_needs")) or _as_list(handoff.get("api_client_needs")),
        "data_contracts": _as_list(frontend_plan.get("data_contracts")) or _as_list(handoff.get("data_contracts")),
    }


def _llm_user_msg(
    *,
    uiux_artifact: dict,
    frontend_result: dict,
    task_instruction: dict[str, Any],
    approved_stack: dict[str, Any],
    sa_contract: dict[str, Any],
    output_root: str,
    language: str,
    framework: str,
) -> str:
    return json.dumps({
        "language": language,
        "framework": framework,
        "output_root": output_root,
        "dev_task": task_instruction.get("dev_task", {}),
        "task_instruction": task_instruction,
        "approved_stack": approved_stack,
        "sa_contract": sa_contract,
        "uiux_artifact": uiux_artifact,
        "frontend_result": frontend_result,
        "requirements": "Generate runnable frontend files and tests under output_root using only approved_stack and sa_contract.",
        "generation_policy": generation_policy(),
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
    """Keep LLM app code, but make runtime and SA API contract files deterministic."""
    template_by_path = {path.replace("\\", "/"): content for path, content in template_files}
    normalized: list[tuple[str, str]] = []
    seen: set[str] = set()
    deterministic = {
        "package.json",
        "tsconfig.json",
        "vite.config.ts",
        "openapi.generated.json",
        "src/api/client.ts",
        "src/api/generated.ts",
        "src/api/hooks.ts",
        "src/api/queryClient.ts",
        "src/generated-contracts.ts",
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


def _frontend_contract_findings(files: list[tuple[str, str]], sa_contract: dict[str, Any]) -> list[str]:
    combined = "\n".join(content for _, content in files)
    findings = placeholder_policy_findings(files, label="Generated frontend")
    for endpoint in sa_contract.get("api_client_needs", []) or []:
        _, path = _method_path(str(endpoint))
        if path and path not in combined:
            findings.append(f"Missing SA/UIUX API client path in generated frontend: {endpoint}")
    for route in sa_contract.get("routes", []) or []:
        if route and str(route) not in combined:
            findings.append(f"Missing UIUX route in generated frontend: {route}")
    return findings


@pipeline_node("develop_frontend_codegen")
def develop_frontend_codegen_node(ctx: NodeContext) -> dict:
    source_dir = Path(str(ctx.sget("source_dir", "") or "")).resolve()
    language, framework, mode = _target(ctx)
    policy = _target_policy(language, framework)
    _, _, frontend_root = _resolve_repo_layout(source_dir)
    output_dir = frontend_root / "generated" / "navigator_dev" / policy["target_key"]

    if not _enabled(ctx.sget("enable_frontend_codegen", False)):
        return {
            "frontend_codegen_result": {
                "status": "skipped",
                "reason": "enable_frontend_codegen is false",
                "output_dir": str(output_dir),
                "language": language,
                "framework": framework,
                "files": [],
            },
            "_thinking": "frontend-codegen-disabled",
        }

    if not source_dir.is_dir():
        return {
            "frontend_codegen_result": {
                "status": "error",
                "reason": f"Invalid source_dir: {source_dir}",
                "files": [],
            },
            "_thinking": "frontend-invalid-source",
        }

    frontend_result = ctx.sget("frontend_result", {}) or {}
    uiux_artifact = ctx.sget("uiux_artifact", {}) or {}
    frontend_plan = frontend_result.get("frontend_plan") or {}
    task_instruction = _frontend_task_instruction(ctx, frontend_result=frontend_result)
    dev_task = task_instruction.get("dev_task") or {}
    dev_context = dev_task.get("context") or {}
    approved_stack = (
        dev_context.get("approved_stack")
        or (ctx.sget("frontend_task_spec", {}) or {}).get("approved_stack")
        or frontend_result.get("approved_stack")
        or approved_stack_for_domain(ctx.sget, domain="frontend", language=language, framework=framework)
    )
    sa_contract = _frontend_sa_contract(ctx, frontend_result=frontend_result, uiux_artifact=uiux_artifact)
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
                    task_instruction=task_instruction,
                    approved_stack=approved_stack,
                    sa_contract=sa_contract,
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

    enforcement_findings = _frontend_contract_findings(generated_files, sa_contract)
    if enforcement_findings and mode == "llm":
        return {
            "frontend_codegen_result": {
                "status": "error",
                "language": language,
                "framework": framework,
                "support_level": policy["support_level"],
                "verification_adapter": policy["verification_adapter"],
                "mode": mode,
                "generator": generator,
                "output_dir": str(output_dir),
                "files": [],
                "test_command": test_command,
                "task_instruction": task_instruction,
                "approved_stack": approved_stack,
                "sa_contract": sa_contract,
                "generation_policy": generation_policy(),
                "contract_enforcement": {"status": "failed", "findings": enforcement_findings},
                "notes": notes,
                "reason": "Generated frontend violated SA/UIUX contract or placeholder policy.",
            },
            "_thinking": "frontend-contract-failed",
        }
    if enforcement_findings:
        notes.extend(enforcement_findings)

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
            "task_instruction": task_instruction,
            "approved_stack": approved_stack,
            "sa_contract": sa_contract,
            "generation_policy": generation_policy(),
            "contract_enforcement": {
                "status": "passed" if not enforcement_findings else "warning",
                "findings": enforcement_findings,
            },
            "notes": notes,
        },
        "_thinking": "frontend-codegen-generated",
    }
