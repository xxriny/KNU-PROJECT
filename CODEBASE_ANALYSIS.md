# 프로젝트 분석서


## 1. 루트 설정 파일

### index.html (29줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1 | `<!DOCTYPE html>` | HTML5 문서 선언 |
| 2 | `<html lang="ko">` | 한국어 UI 앱 명시 |
| 3–24 | `<head>` | 메타 태그, `<title>PM Agent Pipeline v2</title>`, Pretendard·Inter·JetBrains Mono 웹폰트 링크, `<style>` 블록(다크 배경 `#0f172a`, Pretendard 기본 폰트) |
| 25–28 | `<body>` | `#root` div, Vite 엔트리(`/src/main.jsx`) 모듈 로드 |

### package.json

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–5 | `name`, `version`, `description`, `main` | 프로젝트명 `pm-agent-pipeline-v2`, v2.0.0, `electron/main.js` 진입점 |
| 6–15 | `scripts` | `dev`→concurrently(vite+electron), `dev:vite`→Vite, `dev:electron`→wait-on+electron, `build`→Vite 빌드, `build:electron`→electron-builder, `start`→electron, `backend`→python main.py |
| 16–23 | `dependencies` | `@monaco-editor/react`, `lucide-react`, `react` 18.3, `react-dom`, `react-resizable-panels`, `reactflow` 11.11, `zustand` 4.5 |
| 24–35 | `devDependencies` | `@types/react`, `@types/react-dom`, `@vitejs/plugin-react`, `autoprefixer`, `concurrently`, `electron` 31, `electron-builder`, `postcss`, `tailwindcss` 3.4, `vite` 5.3, `wait-on` |

### vite.config.js (23줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–3 | import | `defineConfig`, `react` 플러그인, `path` |
| 5–22 | `defineConfig` | `base: "./"`, `root: "."`, `@` → `src/` 별칭, React 플러그인, dev 서버 포트 5173(`strictPort`), `build: { outDir: "dist", emptyOutDir: true }` |

### tailwind.config.js (22줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–3 | `export default`, `content` | `./index.html`, `./src/**/*.{js,jsx,ts,tsx}` 대상 |
| 4–20 | `theme.extend` | 커스텀 다크 컬러(`slate-850: #141c2e`, `slate-950: #0b1120`), `fontFamily`(sans: Pretendard+Inter, display: Inter, mono: JetBrains Mono+Fira Code) |
| 21–22 | `plugins` | 빈 배열 |

### postcss.config.js (6줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–6 | `export default` | `tailwindcss` + `autoprefixer` 플러그인 적용 |

### run_v2.bat (42줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–5 | 초기 설정 | `@echo off`, `setlocal`, `title PM Agent Pipeline v2`, `cd /d "%~dp0"` |
| 7–10 | kill 이전 프로세스 | `taskkill /f /im node.exe`, `python.exe`, `electron.exe` — 3종 프로세스 강제 종료 |
| 12–13 | Vite 서버 시작 | `start /b cmd /c "npm run dev:vite > vite.log 2>&1"` |
| 15–31 | Vite 대기 루프 | PowerShell `TcpClient`로 localhost:5173 포트 폴링, 최대 90초 대기, 실패 시 vite.log 출력 |
| 33–34 | Electron 시작 | `npm run dev:electron` 실행 |
| 36–42 | 정리 | `taskkill` node/python 종료, `pause` |

---

## 2. Electron 레이어

### electron/main.js (~358줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–17 | JSDoc 주석 | 역할 설명(포트 할당, Python 실행, health 폴링, IPC, 종료 처리), v2.2 EPIPE 수정 변경 이력 |
| 19–23 | import | `electron`(app, BrowserWindow, ipcMain, Menu, dialog, nativeTheme), `child_process.spawn`, `path`, `net`, `http` |
| 26–30 | 상태 변수 | `mainWindow`, `pythonProcess`, `backendPort`, `isQuitting` — 런타임 상태 |
| 32–35 | 경로 설정 | `isDev`(app.isPackaged), `BACKEND_DIR` — 개발/프로덕션 백엔드 디렉토리 분기 |
| 38–44 | EPIPE 방어 | `process.stdout/stderr.on("error")` — EPIPE 크래시 방지 전역 핸들러 |
| 46–57 | `safeLog()` / `safeError()` | EPIPE 안전 로깅 래퍼 함수 |
| 68–78 | `findFreePort()` | `net.createServer().listen(0)` — OS 임시 포트 동적 할당 |
| 87–145 | `startPythonBackend(port)` | `spawn("python", ["main.py", "--port", port])`, stdio pipe, PYTHONUNBUFFERED, stdout/stderr EPIPE 방어 핸들러 |
| 152–190 | `waitForBackend(port)` | `http.get(/health)` 폴링 최대 60회(500ms 간격, 30초), 200 응답 대기 |
| 194–238 | `killPythonProcess()` | stdout/stderr 파이프 destroy → Windows `taskkill /pid /f /t` 또는 Unix SIGTERM/SIGKILL 종료 |
| 242–275 | `createWindow()` | BrowserWindow(1600×1000, minWidth 1200, `titleBarStyle: "hidden"`, `titleBarOverlay`, nativeTheme dark), preload, Vite DEV URL 또는 dist/index.html, maximize, 메뉴 제거 |
| 286–313 | IPC 핸들러 | `get-backend-port`→포트 반환, `select-folder`→폴더 다이얼로그, `get-backend-status`→포트+running 상태 |
| 319–340 | `app.whenReady()` | findFreePort → startPythonBackend → waitForBackend → createWindow, macOS activate 처리 |
| 343–358 | 종료 처리 | `window-all-closed`→앱 종료(macOS 제외), `before-quit`/`will-quit`→killPythonProcess 호출 |

### electron/preload.js (~33줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–11 | JSDoc 주석 | contextBridge 역할 설명, React 사용 예시(`window.electronAPI.getBackendPort()`) |
| 12 | import | `contextBridge`, `ipcRenderer` |
| 14–33 | `electronAPI` | `getBackendPort()`→포트 번호, `getBackendStatus()`→{port, running}, `selectFolder()`→폴더 경로 — IPC invoke 래퍼 노출 |

---

## 3. Backend — 핵심 구조

### backend/version.py (7줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 3 | `APP_VERSION = "2.2.0"` | 앱 버전 |
| 5 | `DEFAULT_MODEL = "gemini-2.5-flash"` | 기본 LLM 모델 |
| 6 | `DEFAULT_TEMPERATURE = 0.3` | 기본 temperature |
| 7 | `MAX_LLM_RETRIES = 3` | LLM 호출 최대 재시도 |

### backend/requirements.txt (12줄)

| 라인 | 패키지 | 역할 |
|------|--------|------|
| 1–2 | `fastapi>=0.104.0`, `uvicorn[standard]>=0.24.0` | HTTP 서버 |
| 3 | `websockets>=12.0` | WS 통신 |
| 4 | `python-dotenv>=1.0.0` | `.env` 로드 |
| 5 | `pydantic>=2.5.0` | 데이터 검증 |
| 6–8 | `langchain-google-genai`, `langgraph`, `google-genai` | LLM 파이프라인 |
| 9 | `networkx>=3.0` | 그래프 알고리즘 |
| 10 | `chromadb>=0.3.21` | 벡터 DB |
| 11–12 | `structlog>=24.0.0`, `prometheus_client>=0.20.0` | 관측성 |

### backend/pytest.ini (4줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–4 | `testpaths`, `markers` | 테스트 디렉토리 `test`, `regression` 마커 정의 |

### backend/main.py (87줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–14 | docstring | 모듈 설명 — 계층 구조(transport/orchestration/result_shaping/observability), usage: `python main.py --port 8765` |
| 16–23 | import | `os`, `sys`, `argparse`, `asynccontextmanager`, `FastAPI`, `CORSMiddleware`, `APP_VERSION` |
| 26–28 | 경로 설정 | `ROOT` 자동 감지, `sys.path` 등록 |
| 31–34 | dotenv | `.env` UTF-8 로드(ImportError 시 무시) |
| 37–41 | 계층 임포트 | `rest_router`, `websocket_pipeline`, `make_metrics_app`, `get_logger` |
| 43 | `ALLOWED_ORIGIN_REGEX` | `^(null\|https?://(127\.0\.0\.1\|localhost)(:\d+)?)$` — CORS 정규식 |
| 47–49 | `lifespan` | asynccontextmanager — startup/shutdown 로그만 출력(DB 초기화 없음) |
| 53–67 | FastAPI 앱 | `app = FastAPI(title, version, lifespan)`, CORS(`allow_origins=[]`, `allow_origin_regex`로 localhost만 허용) |
| 70 | 라우터 등록 | `app.include_router(rest_router)` |
| 71 | WS 라우트 | `app.add_api_websocket_route("/ws/pipeline", websocket_pipeline)` — 경로 `/ws/pipeline` |
| 74–76 | Prometheus | `make_metrics_app()` → `/metrics` 마운트(설치 시 활성) |
| 80–87 | `__main__` | `argparse`로 `--port`(기본 8765)/`--host`(기본 `127.0.0.1`) 파싱, `uvicorn.run()` |

---

## 4. Backend — pipeline 패키지

### backend/pipeline/__init__.py

| 라인 | 코드 | 설명 |
|------|------|------|
| — | (빈 파일) | 패키지 초기화 |

### backend/pipeline/action_type.py 

| 라인 | 코드 | 설명 |
|------|------|------|
| 3 | `ANALYSIS_ACTION_TYPES` | `{"CREATE","UPDATE","REVERSE_ENGINEER"}` 집합 |
| 5–8 | `normalize_action_type()` | `.upper()` 후 집합 포함 검증, 미포함 시 예외 |

### backend/pipeline/state.py 

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–15 | import | `TypedDict`, `Annotated`, `typing` |
| 17–21 | `_merge_thinking_logs()` | 리스트 누적 리듀서 — 여러 노드의 thinking_log 병합 |
| 24–28 | `_keep_last_step()` | 마지막 current_step 값 유지 리듀서 |
| 32–37 | `_BaseState` | `api_key`, `model`, `run_id`, `error`, `thinking_log`(Annotated), `current_step`(Annotated) |
| 40–70 | `_AnalysisFields` | `input_idea`, `project_context`, `source_dir`, `action_type`, `requirements_rtm`, `semantic_graph`, `context_spec`, `sa_phase1`~`sa_phase8`, `sa_artifacts`, `sa_output` 등 분석 단계 필드 |
| 73–77 | `_ChatFields` | `user_request`, `chat_history`, `agent_reply`, `previous_result` — 수정 모드 필드 |
| 80–84 | `_IdeaFields` | `idea_ready`, `idea_summary`, `suggested_mode` — 아이디어 발산 필드 |
| 88–92 | `PipelineState` | `_BaseState + _AnalysisFields + _ChatFields + _IdeaFields` 통합 TypedDict |
| 102–109 | `sget()` | 안전한 state 딕셔너리 접근 헬퍼(KeyError 방지, 기본값 반환) |
| 112–118 | `make_sget()` | curried `sget` 반환 — 노드 상단에서 `sget = make_sget(state)` 패턴 |

### backend/pipeline/node_base.py 

| 라인 | 코드 | 설명 |
|------|------|------|
| 14–22 | `NodeContext` 데이터클래스 | `state`, `sget`, `api_key`, `model`, `node_name` — 노드 공통 실행 문맥 |
| 24–26 | `thinking_log` property | thinking_log 리스트 반환 |
| 29–89 | `@pipeline_node` 데코레이터 | (1) `sget` 자동 초기화, (2) `api_key`/`model` 추출, (3) thinking_log 누적, (4) try-except 안전망 → 에러 시 `{"error": msg, "current_step": "error"}` 반환 |

### backend/pipeline/graph.py 

| 라인 | 코드 | 설명 |
|------|------|------|
| 25–36 | `_PipelineRegistry` | 싱글턴 캐시 — 파이프라인 그래프 재생성 방지 |
| 68 | `SA_EARLY_TERMINATION_STATUSES` | `{"Error"}` — SA 조기 종료 조건 |
| 71 | `PM_INPUT_READINESS_FAILURE_STATUSES` | `{"Needs_Clarification","Error","Completed_with_errors"}` |
| 72–92 | `_check_status()` | 조기 종료 라우터 — SA Error→END, PM 실패→END |
| 95–110 | `_add_all_analysis_nodes()` | 모든 분석 노드(atomizer~sa_phase8+reverse) 등록 |
| 113–121 | `_wire_linear_pipeline()` | 순차 파이프라인 배선(START→chain→END) + 조건부 라우팅 |
| 137 | `_CREATE_CHAIN` | 12개 노드 튜플(atomizer→prioritizer→rtm_builder→semantic_indexer→context_spec→sa_phase3→sa_phase4→sa_phase5→sa_phase6→sa_phase7→sa_phase8→sa_reverse_context) |
| 142 | `_UPDATE_CHAIN` | 15개 노드 튜플(sa_phase1→PM 5단계→sa_phase2~sa_phase8) |
| 147 | `_REVERSE_CHAIN` | 8개 노드 튜플(sa_phase1→sa_phase3→sa_phase4→sa_phase5→sa_phase6→sa_phase7→sa_phase8) |
| 151–174 | 파이프라인 빌더 | `_build_analysis_pipeline()`, `_get_create_pipeline()`, `get_update_sa_pipeline()`, `get_reverse_sa_pipeline()` |
| 177–215 | 공개 API | `get_analysis_pipeline(action_type)`, `get_revision_pipeline()`, `get_idea_pipeline()` — StateGraph 빌드 |
| 234–266 | 라우팅 맵 | `get_pipeline_routing_map()`, `get_revision_routing_map()`, `get_idea_chat_routing_map()` |

### backend/pipeline/ast_scanner.py 

| 라인 | 코드 | 설명 |
|------|------|------|
| 8–21 | 상수 | `_PYTHON_EXTS`, `_JS_EXTS`, `_MAX_FILE_BYTES`(5MB), `_SKIP_DIRS`, `_JS_IMPORT_RE` |
| 34–36 | `_should_skip_dir()` | `__pycache__`, `node_modules` 등 무시 판정 |
| 41–67 | `_parse_python_file()` | Python AST 파싱 → 함수/메서드 시그니처 추출 |
| 70–95 | `_collect_python_imports()` | Python import 구문 추출 |
| 108–136 | `_parse_js_file()` / `_collect_js_imports()` | JS/TS 정규식 기반 함수/import 추출 |
| 139–167 | `_enumerate_source_files()` / `_language_for_suffix()` / `_entrypoint_hint()` | 소스 파일 열거, 언어 판정, 진입점 감지 |
| 176–251 | 내부 임포트 해석 | Python/JS import 후보 경로 생성 → 내부 import 필터링 |
| 256–286 | `extract_functions()` | **공개 API** — 소스 함수 목록 추출(최대 300개 토큰 제한) |
| 289–324 | `extract_file_inventory()` | **공개 API** — 파일 인벤토리 + 내부 import 관계 반환 |
| 327–345 | `summarize_for_llm()` | **공개 API** — 함수 목록을 LLM 프롬프트용 텍스트 변환 |

### backend/pipeline/utils.py 

| 라인 | 코드 | 설명 |
|------|------|------|
| 16 | `_CACHE_LIMIT` | 32개 LRU 캐시 제한 |
| 21–25 | `LLMResult` 데이터클래스 | `parsed`, `usage`, `thinking` — LLM 호출 결과 |
| 28–37 | 캐시 유틸 | `_make_llm_cache_key()`, `_remember_cache_entry()` — `(key:model:temp)` 키 LRU |
| 39–59 | `_get_effective_key()` | 인자 우선 → `os.environ["GEMINI_API_KEY"]` 폴백 → 예외 |
| 65–83 | `get_llm()` | `ChatGoogleGenerativeAI` 싱글턴 캐싱(threading.Lock 보호) |
| 86–117 | `_retry_loop()` | Self-Correction 재시도 루프(MAX_LLM_RETRIES회, validator 콜백) |
| 121–165 | `call_structured()` | **공개 API** — `with_structured_output()` 호출 → `LLMResult[T]` 반환 |
| 168–195 | `call_structured_with_usage()` / `call_structured_with_thinking()` | 하위 호환 래퍼 |
| 200–240 | `_get_raw_client()` / `call_gemini()` | `google.genai` 직접 API 호출(비구조화 텍스트) |
| 243–269 | JSON/thinking 추출 | `extract_json_block()`, `parse_json_safe()`, `extract_thinking()` |
| 272–286 | `to_serializable()` | Pydantic/set/Enum 등 재귀 직렬화 변환 |

### backend/pipeline/chroma_client.py 

| 라인 | 코드 | 설명 |
|------|------|------|
| 8 | `CHROMA_DB_PATH` | `backend/Data/chroma_db` |
| 11–12 | 싱글턴 | `_client`, `_collection` — Optional 전역 변수 |
| 15–24 | `_init_chroma()` | `PersistentClient` 초기화, 컬렉션 `pm_agent_knowledge` |
| 27–56 | `add_knowledge()` | REQ_ID↔소스코드 매핑 벡터 저장, `run_id` 메타데이터 |
| 59–78 | `delete_by_run_id()` | 특정 실행 결과 삭제 |
| 81–115 | `search_similar()` | 코사인 유사도 검색(top_k=5) |
| 118–125 | `get_collection_stats()` | 컬렉션 문서 수 반환 |

---

## 5. Backend — pipeline/schemas

### backend/pipeline/schemas/__init__.py

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–2 | `from .core import *` | 모든 스키마 re-export |

### backend/pipeline/schemas/core.py 

| 라인 | 코드 | 설명 |
|------|------|------|
| 9–25 | PM 우선순위 스키마 | `PrioritizedRequirement`(REQ_ID, category, description, priority, rationale), `PrioritizerOutput`(thinking, requirements) |
| 28–47 | RTM 스키마 | `RTMRequirement`(REQ_ID + depends_on, test_criteria), `RTMBuilderOutput` |
| 50–84 | 시맨틱 그래프 | `CodeFunctionLink`(file, func_name, lineno, confidence), `SemanticNode`(id, label, category, tags, code_links), `SemanticEdge`(source, target, relation), `SemanticIndexerOutput` |
| 87–116 | 컨텍스트 스키마 | `ContextSpecOutput`(summary, key_decisions, tech_stack_suggestions, risk_factors 등), `ReverseContextOutput`(REVERSE 전용 경량 요약) |
| 119–166 | SA3 역분석 스키마 | `EvidenceSummary`(evidence_quality_score, scanned_files 등), `ScoreBreakdownItem`(code, delta, message), `SA3Output`(status, complexity_score, diagnostic_code, score_breakdown) |
| 169–176 | `SAStatusEnum` | `Pass`, `Needs_Clarification`, `Fail`, `Skipped`, `Warning_Hallucination_Detected`, `Error` |
| 178–235 | SA Phase 1–8 스키마 | `SAStatus`(base) → `SAPhase1Output`~`SAPhase8Output` — 각 SA 단계별 출력 상속 스키마 |
| 238–248 | `SAOutput` | 8개 SA 단계 종합 산출물 aggregator |

---

## 6. Backend — pipeline/nodes (22개 파일, 노드 함수 15개 + 스키마/유틸)

### backend/pipeline/nodes/__init__.py

| 라인 | 코드 | 설명 |
|------|------|------|
| — | (빈 파일) | 패키지 초기화 |

### backend/pipeline/nodes/atomizer.py 

| 라인 | 코드 | 설명 |
|------|------|------|
| 3–6 | `AtomicRequirement` | Pydantic 스키마 — `REQ_ID`, `category`, `description` |
| 8–13 | `AtomizerMetadata` | `project_name`, `action_type`, `status`, `total_requirements` |
| 15–19 | `AtomizerOutput` | `thinking_process`, `metadata`, `clarification_questions`, `atomic_requirements` |
| 22–30 | `PM_SYSTEM_PROMPT` | MECE 기반 요구사항 분해 지시 상수 |
| 32–42 | `REVERSE_SYSTEM_PROMPT` | 역공학 모드 — 환각 방지 가드레일 포함 |

### backend/pipeline/nodes/pm_phase1.py (140줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 7–9 | `PM_SYSTEM_PROMPT` | CREATE/UPDATE 모드 PM 프롬프트 상수 |
| 36–65 | `REVERSE_SYSTEM_PROMPT` | REVERSE 모드 가드레일 프롬프트 |
| 68–138 | `atomizer_node()` | `action_type` 감지 → 모드별 프롬프트 선택 → `call_structured(AtomizerOutput)` LLM 호출 → `requirements_rtm` 저장 |

### backend/pipeline/nodes/pm_phase2.py (55줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 7–10 | `SYSTEM_PROMPT` | MoSCoW 우선순위 분류 지시 |
| 13–54 | `prioritizer_node()` | LLM에 Must/Should/Could 분류 지시, 실패 시 기본 우선순위 할당 |

### backend/pipeline/nodes/pm_phase3.py (185줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 20–27 | `SYSTEM_PROMPT` | 의존성 매핑 규칙 상수 |
| 30–62 | `_validate_dependency_quality()` | 자기참조, 존재하지 않는 ID, 빈 의존성 >20%, 순환참조 검출 |
| 65–184 | `rtm_builder_node()` | Self-Correction 루프 — 1차 LLM 호출 → 검증 → 불합격 시 피드백 포함 재시도 |

### backend/pipeline/nodes/pm_phase4.py (211줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 13–24 | `GRAPH_SYSTEM_PROMPT` | 시맨틱 그래프 생성 지시 |
| 27–35 | `_dedupe_semantic_edges()` | 양방향 관계 정규화 + 중복 엣지 제거 |
| 41–52 | 코드 매핑 스키마 | `_FuncMapping`, `_CodeMappingOutput` — REQ_ID↔함수 매핑 |
| 54–59 | `CODE_MAPPING_SYSTEM_PROMPT` | 코드↔요구사항 시맨틱 링킹 지시 |
| 62–211 | `semantic_indexer_node()` | 지식 그래프 생성 + `ast_scanner` 소스 스캔 → 요구사항-코드 매핑 + ChromaDB 저장 |

### backend/pipeline/nodes/pm_phase5.py (392줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 15–19 | `SYSTEM_PROMPT` | 컨텍스트 명세서 생성 지시 |
| 22–48 | `_build_tech_stack_details()` | manifest 증거 기반 기술 스택 상세 빌드 |
| 50–97 | `_save_project_state_md()` | PROJECT_STATE.md 파일 → `backend/Data/{timestamp}_{hash}_{name}_PROJECT_STATE.md` 저장 |
| 100–392 | `context_spec_node()` | 롤링 컨텍스트 명세서 빌드 — 이전 SA 결과 + 사용자 프롬프트 합성 |

### backend/pipeline/nodes/chat_revision.py (442줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 9–54 | Pydantic 스키마 | `RTMRevision`(신규 항목), `RTMRequirementPatch`(부분 수정), `ChatRevisionPatchOutput`(added/modified/deleted 목록) |
| 57–90 | `SYSTEM_PROMPT` | 패치 기반 수정 에이전트 지시(전체 재작성 금지) |
| 93–149 | `chat_revision_node()` | 사용자 요청 → 범위 선택 → LLM 패치 생성 → RTM 인메모리 적용 |
| 160–317 | 내부 헬퍼 | `_normalize_rtm()`, `_normalize_semantic_graph()`, `_select_revision_context()`(광범위/타겟 분기), `_extract_req_ids()`, `_tokenize_request()`, `_build_adjacency()`, `_is_broad_revision_request()` |
| 320–407 | 패치 적용 | `_apply_revision_patch()`(추가/수정/삭제 병합), `_merge_context_spec()` |

### backend/pipeline/nodes/idea_chat.py (101줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 6–36 | `SYSTEM_PROMPT` | PM AI 어시스턴트 — 아이디어 발전 + 분석 준비 감지 |
| 39–100 | `idea_chat_node()` | 대화형 아이디어 발산 → `parse_json_safe()` 응답 파싱 + 텍스트 폴백 → `idea_ready` 플래그 반환 |

### backend/pipeline/nodes/sa_phase1.py (355줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 8–15 | `SAPhase1LLMOutput` | 코드 분석 출력 스키마(thinking, status, confidence, assessment, modules, concerns) |
| 17–29 | `SYSTEM_PROMPT` | SA 아키텍트 코드 구조 분석 지시 |
| 32–42 | `_safe_read_text()` | 인코딩 오류 방어 파일 읽기 |
| 45–163 | `_detect_framework_evidence()` | `package.json`/`requirements.txt`/`pyproject.toml` 파싱 → 프레임워크 감지 |
| 166–194 | `_build_representative_function_sample()` | 대표 함수 샘플 선발(LLM 입력 크기 제한) |
| 197–354 | `sa_phase1_node()` | 프로젝트 전체 AST 스캔 → 프레임워크 감지 → LLM 아키텍처 평가 |

### backend/pipeline/nodes/sa_phase2.py (92줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 7–17 | 스키마 | `RequirementImpact`(req_id, impact_level, change_type, side_effects), `GapReportOutput` |
| 19–23 | `IMPACT_SYSTEM_PROMPT` | 요구사항별 영향 분석 지시 |
| 25–91 | `sa_phase2_node()` | 시맨틱 그래프에서 touched files 추출 → 갭 리포트(충족 불가 요구사항 식별) |

### backend/pipeline/nodes/sa_phase3.py (199줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 12–17 | `FeasibilityOutput` | 타당성 스키마(status, complexity_score, reasons, alternatives, high_risk_reqs) |
| 19–75 | 시스템 프롬프트 | CREATE/REVERSE 모드별 타당성 평가 지시문 |
| 78–92 | `_validate_rtm_schema()` | RTM 구조 + REQ_ID 존재 검증 |
| 97–199 | 핸들러 + 노드 | `_handle_reverse()`(역분석 위임), `_handle_create_update()`(LLM 타당성), `sa_phase3_node()`(디스패처) |

### backend/pipeline/nodes/sa_phase3_reverse.py (397줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 18–55 | 스키마 | `ReverseEvidence`(scanned_files, frameworks, test 존재, observability 등), `ReverseAssessment` |
| 59–174 | 내부 헬퍼 | `_validate_phase1_readiness()`, `_safe_read_text()`, `_path_exists()`, `_grep_any(root, tokens)`(임의 토큰 검색), `_detect_tests()`, `_clamp_score()`, `_append_unique()` |
| 177–309 | 증거 수집 + 평가 | `_collect_reverse_evidence()`(코드 시그널 수집), `_assess_reverse_maintainability()`(규칙 기반 점수화) |
| 312–397 | `assess_reverse()` | 역공학 유지보수성 평가 메인 함수 |

### backend/pipeline/nodes/sa_phase4.py (119줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 8–10 | `PackageExtractionOutput` | 패키지 추출 스키마(thinking, proposed_packages) |
| 24–60 | PyPI 검증 | `_verify_pypi_package()`(HEAD 요청), `_verify_pypi_packages_parallel()`(`ThreadPoolExecutor` 4워커, 4초 타임아웃) |
| 63–118 | `sa_phase4_node()` | 기술 스택 → PyPI 패키지 추출 + 존재 검증 |

### backend/pipeline/nodes/sa_phase5.py (103줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 10–102 | `sa_phase5_node()` | Clean Architecture 4레이어(Presentation/Application/Domain/Infrastructure) 매핑 — LLM 매핑 + `score_layers()` 휴리스틱 폴백 |

### backend/pipeline/nodes/sa_phase5_schemas.py (86줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 7–18 | 매핑 스키마 | `RequirementMapping`(REQ_ID, layer, reason), `ArchitectureMappingOutput`(thinking, pattern_name, mapped_requirements) |
| 21–32 | 모듈 라벨 스키마 | `ModuleFunctionalLabel`(canonical_id, functional_name), `ModuleLabelBatchOutput` |
| 36–73 | 시스템 프롬프트 | `MAPPING_SYSTEM_PROMPT`(레이어 매핑), `MODULE_LABEL_SYSTEM_PROMPT`(한국어 기능명) |

### backend/pipeline/nodes/sa_phase6.py (134줄) — `@pipeline_node` 사용

| 라인 | 코드 | 설명 |
|------|------|------|
| 8–31 | 보안 스키마 | `RoleDefinition`, `AuthzMatrixItem`(restriction_level: Public/Authenticated/Authorized/InternalOnly), `TrustBoundary`, `SecurityDesignOutput` |
| 33–42 | `SECURITY_SYSTEM_PROMPT` | RBAC + Trust Boundary 설계 지시 |
| 46–133 | `sa_phase6_node()` | **`@pipeline_node("sa_phase6")` 데코레이터**, `NodeContext` 수신 — RBAC 역할 정의, AuthZ 매트릭스, Trust Boundaries 생성 |

### backend/pipeline/nodes/sa_phase7.py (137줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 7–22 | 스키마 | `InterfaceContract`(contract_id, layer, interface_name, input_spec, output_spec, error_handling), `Phase7Output`(interface_contracts, guardrails) |
| 24–35 | `INTERFACE_SYSTEM_PROMPT` | 모듈 간 통신 계약 + 개발 가드레일 지시 |
| 38–137 | `sa_phase7_node()` | phase5/6 결과 기반 인터페이스 계약 + 보안/무결성 가드레일 생성 |

### backend/pipeline/nodes/sa_phase8.py (405줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 10–41 | 상수 | `TOKEN_ALIASES`, `TOKEN_STOPWORDS`, `LOW_SIGNAL_TOKENS`, `MIN_CANONICAL_CONFIDENCE`(0.65) |
| 49–130 | 의존성 유틸 | `_extract_contract_tokens()`, `_collect_contract_token_frequency()`, `_is_cross_cutting_contract()`, `_calculate_dependency_confidence()`, `_parse_req_id_from_contract()`, `_normalize_module_path()`, `_module_aliases()` |
| 133–227 | 의존성 합성 | `_synthesize_import_dependencies()`(코드 import 힌트), `_synthesize_dependencies()`(explicit + semantic + data-flow 통합) |
| 230–266 | `_topo_sort_with_batches()` | BFS 기반 위상 정렬 + 병렬 배치 분리(Kahn's algorithm) |
| 269–405 | `sa_phase8_node()` | 4종 의존성 소스 통합 → 위상 정렬 → 실행 순서 + `sa_output` 전체 SA 페이즈 집계 |

### backend/pipeline/nodes/sa_reverse_context.py (107줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 9–44 | 내부 헬퍼 | `_top_frameworks()`, `_layer_distribution()`, `_top_low_confidence_modules()`, `_module_name()` |
| 47–106 | `sa_reverse_context_node()` | REVERSE 전용 — 프레임워크·레이어·위상·리스크·다음 단계 통합 요약 생성 |

### backend/pipeline/nodes/sa_reverse_module.py (262줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 9–114 | `build_reverse_module_profiles()` | AST 스캔 기반 모듈 프로파일 생성(파일 수, 함수 수, import 관계) |
| 117–143 | `batch_label_modules()` | LLM 일괄 호출 → 모듈별 한국어 기능 라벨 자동 부여 |
| 146–262 | `build_reverse_module_mapping()` | sa_phase1 프로파일 → 아키텍처 매핑 요구사항(MOD-001 등) + confidence 점수 |

### backend/pipeline/nodes/sa_layer_heuristics.py (353줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 6–31 | 상수 | `LAYER_ORDER`(4레이어), `LAYER_KEYWORDS`(키워드→레이어), `FRAMEWORK_LAYER_HINTS`, `BACKEND_FRAMEWORKS`, `FRONTEND_FRAMEWORKS`, `MODULE_SIGNAL_HINTS`, `LAYER_BY_CATEGORY` |
| 43–127 | 유틸 함수 | `infer_layer_from_path()`, `tokenize_text()`, `normalize_module_path()`, `canonical_module_id()`, `framework_scope_map()`, `module_family()`(backend/frontend/electron 분류), `_path_is_close()`, `scoped_frameworks_for_module()` |
| 181–282 | `score_layers()` | 30+ 시그널 기반 다중 점수화 → 최고 점수 레이어 + confidence + evidence 반환 |
| 285–297 | `fallback_mapping_info()` | LLM 실패 시 폴백 레이어 매핑 정보 |

---

## 7. Backend — connectors

### backend/connectors/folder_connector.py (62줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–16 | 상수 + import | `IGNORE` 집합 — `node_modules`, `.git`, `__pycache__`, `dist`, `build` 등 무시 |
| 18–62 | `scan_folder()` | 재귀 파일 트리 빌드 → `{name, path, children}` 구조, 내부 `walk()` 재귀 함수 |

### backend/connectors/result_logger.py (156줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 24 | `_safe_filename()` | 파일명 정규화 헬퍼 |
| 33 | `save_result()` | JSON 직렬화 → `backend/Data/{timestamp}_{runid}_{name}.json` 저장 |
| 60 | `delete_session_files()` | `run_id`로 관련 파일 일괄 삭제 |
| 95 | `delete_exact_file()` | 특정 파일 경로 삭제 |

---

## 8. Backend — observability

### backend/observability/__init__.py (8줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–8 | re-export | `get_logger`, `configure_logging`, `NODE_LATENCY`, `NODE_FAILURE`, `track_node`, `make_metrics_app` |

### backend/observability/logger.py (103줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 14 | `_ensure_configured()` | structlog 단회 설정(JSON/dev 렌더러 자동 전환) |
| 35 | `configure_logging()` | 로깅 초기화 진입점 |
| 39 | `get_logger()` | structlog 래퍼, `run_id` 바인딩 |
| 65 | `_FallbackLogger` | structlog 미설치 시 stdlib `logging` 폴백 클래스 |

### backend/observability/metrics.py (94줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 18 | `NODE_LATENCY` | Prometheus Histogram — 노드 처리 시간 |
| 23 | `NODE_FAILURE` | Prometheus Counter — 노드 실패 수 |
| 28 | `make_metrics_app()` | Prometheus ASGI 앱 생성(main.py에서 `/metrics` 마운트) |
| 32 | `track_node()` | context manager — 노드 실행 시간 측정 + 실패 카운트, prometheus_client 미설치 시 no-op |

---

## 9. Backend — orchestration

### backend/orchestration/__init__.py (1줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| — | (빈 파일) | 패키지 초기화 |

### backend/orchestration/pipeline_runner.py (330줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 23 | `validate_analysis_inputs()` | 입력 매개변수(api_key, model 등) 검증 |
| 33 | `build_reverse_context()` | AST 스캔 결과 → 프로젝트 컨텍스트 변환 |
| 49 | `analysis_pipeline_type()` | action_type 기반 파이프라인 타입 결정 |
| 57–114 | `_run_pipeline_base()` | 공통 파이프라인 실행 로직(state 초기화, invoke, 결과 수집) |
| 115–168 | `run_analysis()` | 분석 파이프라인 WS 진입점 — state 초기화 → 파이프라인 실행 → 결과 반환 |
| 169–191 | `run_revision()` | 수정 파이프라인 실행 |
| 192–212 | `run_idea_chat()` | 아이디어 채팅 노드 단독 실행 |
| 213–330 | `stream_pipeline_updates()` | 비동기 제너레이터 — 각 노드 완료 시 WS 스트리밍, `_emit_thinking()`, `_merge_state()` 헬퍼 |

### backend/orchestration/executor.py (38줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 9–13 | `PipelineResult` | `@dataclass` — 파이프라인 결과 컨테이너 |
| 18–33 | `execute_pipeline()` | REST 동기 호출용 — 파이프라인 invoke → `shape_result()` 통합 |

---

## 10. Backend — transport

### backend/transport/__init__.py (1줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| — | (빈 파일) | 패키지 초기화 |

### backend/transport/connection_manager.py (30줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 8 | `ConnectionManager` | `active_connections: set` — 활성 WS 연결 관리, `send_json()` 전송 + 실패 시 연결 제거 |
| 27 | `manager` | 싱글턴 인스턴스 |

### backend/transport/ws_handler.py (67줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 8–67 | `websocket_pipeline()` | WS accept → 메시지 루프, `type` 필드 기반 라우팅: `analyze`→분석, `revision`→수정, `idea_chat`→아이디어, `stream_pipeline_updates()` 실시간 전송, ConnectionClosed 처리 |

### backend/transport/rest_handler.py (270줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 27–41 | 보안 헬퍼 | `_normalize_path()`, `_is_within_root()`(경로 순회 방지), `register_project_root()`, `is_allowed_project_file()` |
| 45–76 | Pydantic 요청 스키마 | `AnalysisRequest`, `RevisionRequest`, `IdeaChatRequest`, `ScanRequest`, `ReadFileRequest`, `DeleteSessionRequest`, `HealthResponse` |
| 80 | `rest_router` | FastAPI APIRouter 인스턴스 |
| 83 | `GET /health` | 헬스체크 엔드포인트 |
| 88 | `GET /api/config` | 모델/버전 정보 반환 |
| 95 | `POST /api/scan-folder` | 폴더 스캔 + 프로젝트 루트 등록 |
| 110 | `POST /api/read-file` | 파일 읽기(경로 보안 검증 포함) |
| 134 | `POST /api/analyze` | `execute_pipeline()` 호출 |
| 163 | `POST /api/revise` | 수정 파이프라인 실행 |
| 177 | `POST /api/idea-chat` | 아이디어 채팅 실행 |
| 191 | `DELETE /api/session/{run_id}` | 세션 파일 삭제 |

---

## 11. Backend — result_shaping

### backend/result_shaping/__init__.py (1줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| — | re-export | `shape_result`, `deep_sanitize` |

### backend/result_shaping/result_shaper.py (232줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 12–23 | Pydantic 스키마 | `PMOverview`, `SAOverview`, `ProjectOverview` — 정형화된 출력 모델 |
| 67–151 | 내부 빌더 | `_collect_skipped_phases()`, `_build_pm_overview()`, `_build_sa_overview()`, `_resolve_summary()`, `_build_priority_counts()`, `_build_layer_distribution()`, `_build_data_flags()`, `_compute_next_actions()`, `_build_project_overview()` |
| 189–231 | `shape_result()` | 파이프라인 원시 출력 → 프론트엔드 친화적 구조(`pm_overview`, `sa_overview`, `project_overview`) |
| 232 | `deep_sanitize()` | `to_serializable` 호환 별칭 |

### backend/result_shaping/sa_artifact_compiler.py (502줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 14–31 | `compile_sa_artifacts()` | SA 페이즈 데이터 → 5종 산출물 컴파일(LLM 미사용) |
| 32–56 | `_build_flowchart_spec()` | 위상 정렬 → 실행 단계 순서 그래프 |
| 57–123 | `_build_uml_component_spec()` | 레이어별 컴포넌트 + 인터페이스 + 관계 |
| 124–168 | 유틸 | `_data_quality()`, `_strip_module_prefix()`, `_match_container()`, `_normalize_layer_name()` |
| 169–319 | `_build_container_diagram_spec()` | container_config 기반 컴포넌트/외부시스템/연결 그래프 |
| 320–341 | `_build_interface_definition_doc()` | 인터페이스 계약 + 가드레일 문서 |
| 342–502 | `_build_decision_table()` | 역할·레이어·제한·액션 의사결정 테이블 |

### backend/result_shaping/container_config.py (148줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 3 | `LAYER_ORDER` | 레이어 순서 상수 |
| 6–69 | `CONTAINER_GROUPS` | 컨테이너 그룹 정의(Electron Shell, React UI, Python API 등) |
| 70–95 | `CONTAINER_EDGES` | 컨테이너 간 연결(IPC, HTTP, process 등) |
| 96–120 | `EXTERNAL_SYSTEM_SIGNALS` | 외부 시스템 시그널(Gemini API, ChromaDB, PyPI, File System) |
| 121–148 | `LAYER_FALLBACK_CONTAINERS` | 레이어→기본 컨테이너 매핑 |

---

## 12. Frontend — 엔트리

### src/main.jsx (10줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–4 | import | `React`, `ReactDOM`, `App`, `index.css` |
| 6–10 | `createRoot()` | `#root`에 `<React.StrictMode><App /></React.StrictMode>` 마운트 |

### src/index.css (145줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–3 | Tailwind 디렉티브 | `@tailwind base/components/utilities` |
| 4–30 | CSS 변수 + 글로벌 | 다크 테마 컬러, `app-drag`/`app-no-drag` 영역(Electron frameless), 스크롤바 커스텀 |
| 31–145 | 컴포넌트 스타일 | `doc-font-up` 스케일링, 마크다운 렌더링, 애니메이션 등 |

### src/App.jsx (79줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–10 | 주석 + docblock | 3단 분할 레이아웃 설명 |
| 12–19 | import | `Panel`/`PanelGroup`/`PanelResizeHandle`, `useAppStore`, Sidebar, Workspace, ChatPanel, SessionPanel, StatusBar |
| 21–53 | `App()` 컴포넌트 | `useEffect`에서 Electron IPC or 기본 포트(8765) → `connectWebSocket()` + `fetchConfig()` |
| 55–79 | 3패널 레이아웃 | 상단: 타이틀 바, Sidebar(20%) + Workspace(60%) + ChatPanel+SessionPanel(24%), 하단: StatusBar |

---

## 13. Frontend — store (Zustand)

### src/store/useAppStore.js (581줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–38 | import + 초기 상태 | `zustand`, 슬라이스, 헬퍼 함수, WS/파이프라인/결과/뷰포트/채팅/세션 상태 |
| 40–91 | `_handleWsMessage()` | WS 메시지 `type` 분기: `node_start`/`node_complete`/`pipeline_complete`/`error`/`thinking_log` |
| 92–131 | 파이프라인 실행 | `startAnalysis()`(L92), `startRevision()`(L116), `sendIdeaChat()`(L132) — `sendWsMessage()` 호출 |
| 163–188 | `_processResult()` | 파이프라인 결과 → `spreadResultData()` 통해 각 필드 분배 |
| 189–240 | Viewport/Tab 관리 | `activateCodeTab()`(L189), `activateOutputTab()`(L191), `openFile()`(L196), `updateOpenFileContent()`(L209), `closeFile()`(L222) |
| 241–261 | 채팅/파일 | `addChatMessage()`(L241), `setChatInput()`(L247), `clearChat()`(L249), `setFileTree()`(L259) |
| 263–390 | 프로젝트 관리 | `ensureProjectFolderAccess()`(L263), `selectAndScanFolder()`(L286), `openProjectFile()`(L310), `detectLanguage()`(L391) |
| 411–517 | 세션 CRUD | `createSession()`(L411), `saveCurrentSession()`(L448), `loadSession()`(L481), `deleteSession()`(L518) |
| 565–581 | `resetPipeline()` | 파이프라인 상태 초기화 |

### src/store/storeHelpers.js (117줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 5 | `SESSION_STORAGE_KEY` | localStorage 키 |
| 6 | `DEFAULT_VIEWPORT_TAB` | 기본 뷰포트 탭 |
| 8 | `MODE_TO_ACTION_TYPE` | UI 모드 → 백엔드 액션 타입 매핑 |
| 14 | `MODE_TO_PIPELINE_TYPE` | UI 모드 → 파이프라인 타입 매핑 |
| 20 | `normalizeMode()` | 문자열 정규화(create/update/reverse) |
| 24–37 | 세션 유틸 | `loadSessions()`/`persistSessions()` — localStorage JSON 직렬화 |
| 38–51 | 탭/결과 유틸 | `cloneViewportTab()`, `normalizeOutputTabId()`, `extractRunId()` |
| 59–71 | `inferPipelineTypeFromResult()` | 결과 구조에서 파이프라인 타입 추론 |
| 72–91 | `EMPTY_RESULT_FIELDS` | 빈 결과 상태 초기값 |
| 92–117 | `spreadResultData()` | 파이프라인 결과 → 스토어 각 필드 분배 |

### src/store/slices/wsSlice.js (58줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–9 | 초기 상태 | WS 연결 상태, `setBackendPort()`, `setWsStatus()` |
| 11–48 | `connectWebSocket()` | `new WebSocket()`, `onmessage` → `_handleWsMessage()` 위임, `onclose` → 3초 후 재연결 |
| 49–58 | `sendWsMessage()` | JSON 직렬화 전송 |

### src/store/slices/configSlice.js (30줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–30 | `createConfigSlice()` | `apiKey`, `model`, `fetchConfig()` — `GET /api/config` → 기본 모델/버전 수신 |

### src/store/debounce.js (12줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–12 | `debounce()` | 범용 디바운스(기본 500ms) — 자동저장에 사용 |

---

## 14. Frontend — 컴포넌트 (메인)

### src/components/Sidebar.jsx (175줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–21 | import | lucide 아이콘, `useAppStore` |
| 22–146 | `Sidebar` 컴포넌트 | 프로젝트 로고·타이틀, API 키 입력, 모델 선택 드롭다운(gemini-2.5-flash/pro 등), 폴더 선택, 파일 트리 렌더 |
| 148 | `FileTreeNode` | 재귀 트리 컴포넌트 — 폴더 펼침/접기 |
| 158 | `FileTreeItem` | 단일 파일 항목 — 클릭 → `openProjectFile()` |

### src/components/HomeScreen.jsx (161줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–38 | import + 상수 | 아이콘, `useAppStore`, 모드 카드 정의 |
| 39–161 | `HomeScreen` | Create/Update/Reverse 3가지 모드 카드 UI, 프로젝트 설명 textarea, 실행 버튼 → `startAnalysis()` |

### src/components/ChatPanel.jsx (164줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–11 | import | 아이콘, `useAppStore` |
| 12–131 | `ChatPanel` | Chat/Apply 토글, 메시지 히스토리(사용자 파란/어시스턴트 회색 말풍선), 자동 스크롤, 텍스트 입력 + 전송 → `sendIdeaChat()` |
| 133–164 | `ChatMessage` | 개별 메시지 렌더링 서브 컴포넌트 |

### src/components/Workspace.jsx (233줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–32 | import + 상수 | 탭 컴포넌트들, `useAppStore`, 탭 ID 정의 |
| 33–233 | `Workspace` | 2-tier 탭(상단: 코드 파일 탭, 하단: 출력 탭), PM/SA 드롭다운 메뉴, `activeTabId` 기반 뷰포트 라우팅, 파이프라인 진행 상태에 따라 HomeScreen/PipelineProgress/결과 뷰 전환 |

### src/components/PipelineProgress.jsx (169줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–19 | import + 상수 | 아이콘, `useAppStore` |
| 20–66 | 파이프라인 단계 정의 | CREATE 11단계, UPDATE 14단계, REVERSE 9단계, analysis(PM only) 5단계, revision 1단계, idea_chat 1단계 |
| 67–138 | `PipelineProgress` | 진행 표시(대기/진행중/완료/에러 아이콘+라벨), Thinking 로그 실시간 스트림 |
| 139–169 | `StepItem` | 개별 단계 렌더링 서브 컴포넌트 |

### src/components/ResultViewer.jsx (38줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–32 | import | 12개 서브 탭 컴포넌트 |
| 33–38 | `ResultViewer` | `tabId` 기반 탭 라우터 — Overview/RTM/Context/Topology/SA* 탭 분기 |

### src/components/StatusBar.jsx (71줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–9 | import | `useAppStore` |
| 10–71 | `StatusBar` | WS 연결 (🟢/🔴), 파이프라인 상태, 모델명, 백엔드 포트 |

### src/components/CodeViewer.jsx (57줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–10 | import | `@monaco-editor/react`, `useAppStore` |
| 11–57 | `CodeViewer` | Monaco 에디터 래퍼, 언어 자동 감지(확장자 기반), 다크 테마, **편집 가능**(readOnly: false), `onChange` → `updateOpenFileContent()` |

### src/components/SessionPanel.jsx (62줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–4 | import | `useAppStore`, 아이콘 |
| 5–62 | `SessionPanel` | 세션 목록 렌더링(타임스탬프·이름), `loadSession()`, `deleteSession()` 버튼 |

---

## 15. Frontend — resultViewer 서브 컴포넌트 (14개)

### src/components/resultViewer/SharedComponents.jsx (60줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 3 | `StatCard` | 숫자 통계 카드(라벨, 값, 색상) |
| 13 | `PriorityBadge` | Must/Should/Could 우선순위 배지(빨강/노랑/초록) |
| 26 | `StatusBadge` | Pass/Fail/Error/Needs_Clarification 등 상태 배지 |
| 42 | `Section` | 제목+아이콘+children 래퍼 컨테이너 |
| 53 | `EmptyState` | 데이터 없을 때 "~가 없습니다" 메시지 |

### src/components/resultViewer/resultUtils.js (37줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 5 | `toCompactModuleLabel()` | "핵심 분석 모듈:" 접두사 제거 → 짧은 라벨 |
| 14 | `buildReqFunctionNameMap()` | `mapped_requirements` → `{REQ_ID: 기능명}` 맵 빌드 |
| 29 | `layerBadgeTone()` | 레이어명 → Tailwind 배지 색상 클래스 반환 |

### src/components/resultViewer/OverviewTab.jsx (357줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–20 | import/state 추출 | `useAppStore`에서 모든 결과 데이터 구조 분해 |
| 21–80 | 통계 계산 | 요구사항 수, MoSCoW 분포, 카테고리 집계, 오버뷰 데이터 합성(`projectOverview` 우선, 없으면 폴백) |
| 81–130 | 의사결정 라벨링 | saStatus + criticalGaps + highRiskReqs 기반 → "진행 가능"/"정보 보강 필요"/"주의 필요" |
| 131–230 | PM 요약 UI | 통계 카드, 카테고리 막대그래프, 리스크 목록 |
| 231–310 | SA 요약 UI | 기술 타당성, 구현 난이도, 판정 근거, 대안, 건너뛴 단계 |
| 311–357 | 권장 다음 단계 + 상단 카드 | `next_actions` 순서형 리스트, 막힌 항목·주요 컴포넌트·외부 의존 경계 수 |

### src/components/resultViewer/RTMTab.jsx (57줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–57 | 테이블 렌더링 | ID, 카테고리, 설명, 우선순위 배지, 의존성, 테스트 기준 6열 테이블 |

### src/components/resultViewer/ContextTab.jsx (180줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–15 | import | `useAppStore`, lucide 아이콘, `Section` |
| 16–25 | 분기 | `context_spec` 있으면 일반, 없고 `sa_reverse_context`만 있으면 `ReverseContextTab` |
| 26–100 | 일반 ContextTab | 프로젝트 요약, 핵심 결정사항, 미해결 질문, 기술 스택 제안, 리스크, 다음 단계 |
| 101–180 | `ReverseContextTab()` | 역분석 요약, 구조 하이라이트, 관측 기술스택, 의존성 관찰, 리스크, 검증 단계 |

### src/components/resultViewer/TopologyTab.jsx (18줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–18 | 렌더 | `semantic_graph` 유효 시 `<TopologyGraph>` 렌더링, 없으면 EmptyState |

### src/components/resultViewer/SAArchitectureTab.jsx (393줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–50 | 레이어 메타 / 정규화 | `layerMeta` 5+1 레이어 정의, `normalizeLayer()` |
| 51–100 | 레이어 보드 | `useMemo` 그룹화, 레이어 카드 렌더(클릭 → 필터) |
| 101–165 | 인터페이스 계약 탐색 | 검색/필터 UI, `inferCommType()` (API/UI/Event/Internal 분류) |
| 166–210 | `toHumanReadableTitle()` | 영어 인터페이스명 → 한국어 번역(phrase 규칙 + word 사전) |
| 211–320 | 계약 카드 | 커뮤니케이션 타입 배지, Input→Output 시각화, 레이어 배지 |
| 321–393 | 통계 카드 + 가드레일 | 매핑 요구사항·활성 레이어·계약·가드레일 수 |

### src/components/resultViewer/SASecurityTab.jsx (260줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–30 | 유틸 함수 | `toCompactModuleLabel()`, `extractFileRoot()`, `toKoreanFunctionName()`, `isLikelyFilePath()` |
| 31–70 | 데이터 매핑 | sa_phase7·sa_phase5에서 req별 타이틀/파일루트 역추적 |
| 71–100 | `getBoundaryVisual()` | Trust Boundary 종류별 이모지(🌐/🤖/🗄️/💻/🛡️) |
| 101–140 | RBAC 역할 | 역할 pill 배지 렌더링 |
| 141–175 | Trust Boundaries | 경계 카드(이모지+이름+데이터+통제) |
| 176–260 | 권한 매트릭스 | 요구사항·역할·접근수준 3열 테이블(최대 16행) |

### src/components/resultViewer/SATopologyTab.jsx (192줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–30 | 상태 추출 | `sa_phase8`의 `topo_queue`, `cyclic_requirements`, `parallel_batches`, `dependency_sources` |
| 31–60 | `reqMeta` 빌드 | sa_phase5 매핑에서 이름·레이어 추출 |
| 61–100 | `cyclePathMap` | DFS로 순환 의존성 경로 탐색 |
| 101–130 | `phaseGroups` | batches → Phase 그룹 또는 단일 순차 큐 |
| 131–170 | 순환 경고 UI | 순환 의존 모듈 버튼 + 클릭 시 경로 펼치기 |
| 171–192 | 실행 그룹 UI | Phase별 카드 — 순번·REQ_ID·기능명·레이어 배지 |

### src/components/resultViewer/SASystemDiagramTab.jsx (36줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–15 | import | `SAArtifactGraph`, `normalizeContainerDiagramForGraph`, `StatCard` |
| 16–36 | 요약 통계 + 그래프 | 컴포넌트·외부시스템·연결 수, `normalizeContainerDiagramForGraph()` → `<SAArtifactGraph>` 620px |

### src/components/resultViewer/SAFlowchartTab.jsx (55줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–15 | import | `SAArtifactGraph`, `normalizeFlowchartForGraph`, `buildReqFunctionNameMap` |
| 16–35 | REQ→기능명 매핑 | `reqFunctionNameMap` 생성 → stage별 `function_names` 주입 |
| 36–55 | 요약 + 그래프 | Stage 수, Parallel 수, 완전성 + 560px 그래프 |

### src/components/resultViewer/SAUMLComponentTab.jsx (82줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–20 | import | `SAArtifactGraph`, `normalizeUMLForGraph` |
| 21–40 | 보기 모드 | `expandedLayer` 상태 — 기본 "cluster", 클릭 시 "detail" 전환 |
| 41–60 | 대규모 그래프 감지 | `relations ≥ 600` 시 dense 모드 표시 |
| 61–82 | 그래프 렌더 | 클러스터 노드 클릭 → 해당 레이어 상세 보기 |

### src/components/resultViewer/SAInterfacesTab.jsx (165줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–20 | import | `buildReqFunctionNameMap`, `layerBadgeTone`, `Section` |
| 21–45 | 계약 테이블 | 계약 ID, 레이어, 인터페이스명, Input/Output 미리보기, 상세 열 |
| 46–80 | 펼치기/접기 | `expandedContractId` 토글 → Input/Output Full JSON 표시 |
| 81–110 | I/O 포맷팅 | `formatIoPreview()` 86자 truncate, `formatExpandedIo()` JSON pretty-print |
| 111–165 | Guardrails | 보안 키워드 하이라이트(mTLS, 최소 권한 등 → 앰버 색상) |

### src/components/resultViewer/SADecisionTableTab.jsx (104줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–15 | import | `buildReqFunctionNameMap`, `layerBadgeTone` |
| 16–30 | 톤 함수 | `restrictionTone()` Internal/Public, `actionTone()` ALLOW/REVIEW |
| 31–104 | Decision 테이블 | 요구사항·Layer·Restriction·Roles·Action 5열 테이블(최대 40행) |

---

## 16. Frontend — 그래프 시스템

### src/components/SAArtifactGraph.jsx (325줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–12 | import | `ReactFlow`, `Handle`, `MarkerType`, `Position` |
| 13–49 | `SAArtifactNode` | 커스텀 노드 — 타이틀, 서브타이틀, 배지, accent 컬러, dimmed/highlighted 상태 |
| 50–130 | `SAArtifactGraph` 컴포넌트 | `graph.nodes/edges` → ReactFlow 렌더, `FIT_VIEW_OPTIONS`(padding 0.1, zoom 0.05~1.5), 인접성 기반 하이라이트(hover/select 시 연결 노드만 강조) |
| 131–200 | 줌 레벨 반응 | `zoomLevel < 0.78` 시 저우선 엣지 라벨 숨김 |
| 201–325 | 사이드 패널 | 선택 노드 상세 — module_id, 기능 목록(테이블), 파일 경로, 매핑 요구사항, 의존 모듈, 증거 |

### src/components/saGraphAdapters.js (379줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–3 | import | `graphLayout`, `graphUtils` |
| 4–79 | `normalizeSystemDiagramForGraph()` | spec → 레이어별 x배치, degree 정렬, 관계 타입별 색상(explicit 파랑/semantic 보라/execution_order 회색) |
| 80–120 | `normalizeFlowchartForGraph()` | stages → 수평 나열, sequential 파랑/parallel 틸, 기능명 프리뷰 |
| 121–269 | `normalizeUMLForGraph()` | cluster 모드: 레이어 집계 노드, detail 모드: 개별 컴포넌트 노드, `hideExecutionOrder`/`minConfidence` 필터 |
| 270–379 | `normalizeContainerDiagramForGraph()` | container_config 기반 — 컴포넌트/외부시스템 그래프, edge 색상(http 파랑/ipc 보라/data 틸/external 앰버) |

### src/components/graphLayout.js (43줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 5 | `LAYER_ORDER` | 5+1 레이어 순서 상수 |
| 7 | `LAYER_COLOR` | 레이어별 색상 매핑 |
| 16 | `getLayerX()` | 레이어명 → x좌표(120 + index×620) |
| 22 | `clamp()` | 값 범위 제한 유틸 |
| 26–43 | `buildDynamicLayerXMap()` | 활성 레이어 수·최대 아이템 수 기반 동적 갭 계산 → `{layer: x}` 맵 |

### src/components/graphUtils.js (42줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 5 | `groupBy()` | 배열 → 키 함수 기반 그룹 객체 |
| 14 | `dedupeEdges()` | `source|target|type` 키 중복 엣지 제거 |
| 22 | `compactPathLabel()` | "핵심 분석 모듈:" 접두사 제거 + 마지막 2 디렉토리 축약(40자 제한) |
| 33 | `buildDegreeMap()` | 엣지 목록 → `{nodeId: degree}` 연결 수 맵 |

### src/components/TopologyGraph.jsx (478줄)

| 라인 | 코드 | 설명 |
|------|------|------|
| 1–14 | import | `@xyflow/react`의 `ReactFlow`, `Background`, `Controls`, `MarkerType`, 색상 상수 |
| 15–96 | `computeLayeredLayout()` | 의존성 기반 BFS 레이어링 → 우선순위 정렬 → x/y 좌표 계산 |
| 97–101 | `truncateLabel()` | 긴 라벨 축약 헬퍼 |
| 102–250 | `TopologyGraph` 컴포넌트 | `rtmMap` 빌드, 노드 원형 스타일(border=우선순위 색), 엣지 smoothstep, NODE_W 332, NODE_H 162 |
| 251–380 | ReactFlow 렌더 | fitView, zoom 0.2~2, 범례(우선순위 3컬러 + 도형 4종) |
| 381–470 | 사이드 패널 | 선택 노드 상세 — ID, 설명, 카테고리, 우선순위, 의존성 버튼, 태그, 네비게이션(Workspace 상세/RTM 탭/SA Topology) |
| 471–478 | `SideSection` | 사이드 패널 내부 섹션 서브 컴포넌트 |

---

## 17. Backend — test

| 파일 | 테스트 대상 |
|------|-------------|
| backend/test/test_pipeline_setup.py | 파이프라인 빌드 및 초기화 |
| backend/test/test_atomizer_fix.py | atomizer 노드 수정 검증 |
| backend/test/test_llm_regression.py | LLM 호출 회귀 테스트 |
| backend/test/test_pm_phase5.py | context_spec 노드 |
| backend/test/test_sa_artifact_compiler.py | SA 산출물 컴파일러 |
| backend/test/test_sa_phase3.py | 타당성 평가 노드 |
| backend/test/test_sa_phase5.py | 아키텍처 매핑 노드 |
| backend/test/test_sa_phase6.py | 보안 경계 노드 |
| backend/test/test_sa_phase8.py | 위상 정렬 노드 |
| backend/test/test_sa_reverse_context.py | 역분석 컨텍스트 노드 |
| backend/test/test_ws.py | WebSocket 핸들러 |

---

## 파일 총 개요

| 카테고리 | 파일 수 | 주요 역할 |
|----------|---------|-----------|
| 루트 설정 | 6 | Vite/Tailwind/PostCSS/배치/HTML/npm |
| Electron | 2 | 데스크톱 셸, IPC preload |
| Backend 핵심 | 4 | main.py, version, requirements, pytest |
| Pipeline 코어 | 7 | state, graph, node_base, utils, ast_scanner, chroma, action_type |
| Pipeline 스키마 | 2 | Pydantic 모델(core.py + __init__.py) |
| Pipeline 노드 | 22 | PM 5단계 + SA 8단계(+sa_phase3_reverse, sa_phase5_schemas) + 채팅/아이디어 + 역분석 2개 + 휴리스틱 + atomizer + __init__ |
| Connectors | 2 | 폴더 스캔, 결과 저장 |
| Observability | 3 | 로깅, Prometheus 메트릭 |
| Orchestration | 3 | 파이프라인 실행/스트리밍 |
| Transport | 4 | WS/REST/커넥션 매니저 |
| Result Shaping | 4 | 결과 정형화, SA 산출물, 컨테이너 설정 |
| Frontend Store | 5 | Zustand 스토어(메인 + 슬라이스 2개 + 헬퍼 + 디바운스) |
| Frontend 메인 컴포넌트 | 9 | App, Sidebar, ChatPanel, Workspace, HomeScreen, PipelineProgress, ResultViewer, StatusBar, CodeViewer, SessionPanel |
| Frontend resultViewer | 14 | 12개 탭 + SharedComponents + resultUtils |
| Frontend 그래프 | 5 | SAArtifactGraph, saGraphAdapters, graphLayout, graphUtils, TopologyGraph |
| Backend 테스트 | 11 | 각 노드 단위/통합 테스트 |
| **합계** | **~103개** | |
