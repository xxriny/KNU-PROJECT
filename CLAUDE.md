# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository

The project root is `KNU-PROJECT/` (the outer `NAVIGATOR_Agile_2/` directory is not the git root — `.git` lives inside `KNU-PROJECT/`). All commands below assume CWD is `KNU-PROJECT/`.

## Commands

### Run the full stack
- `run_v2.bat` — Windows one-click launcher. Kills stale node/python/electron processes on ports 5173/8765, starts Vite, waits for port 5173 (up to 90s), then launches Electron (which spawns the FastAPI sidecar itself — do **not** run `npm run backend` alongside it).
- `npm run dev` — cross-platform equivalent (`concurrently` runs `dev:vite` + `dev:electron`). Vite dev server is on **5173**; the backend port is chosen dynamically by Electron via `findFreePort()` and passed to Python as `--port`.
- `npm run dev:electron:now` — launch Electron immediately without waiting for Vite (used internally by the .bat).
- `run_test_user.bat` — runs Electron with an isolated `--user-data-dir` under `backend/storage/test_user_session` (test as a fresh user without wiping your real login).
- `npm run backend` — backend only, **hardcoded to port 8765** (only use when running Vite separately, e.g. in a browser, not under Electron).

### Build
- `npm run build` — Vite build to `dist/`.
- `npm run build:electron` — Vite build + electron-builder (NSIS on Windows, DMG on macOS). Bundles `backend/` as `extraResources`, excluding `__pycache__` and `*.pyc`.

### Backend tests (pytest, run from `backend/`)
- `python -m pytest -q test/` — full suite. `pytest.ini` sets `testpaths = test` and registers a `regression` marker for LLM-output schema regressions.
- Single file: `python -m pytest -q test/test_phase6_agile_layer.py`
- Single test: `python -m pytest -q test/test_phase6_agile_layer.py::test_name`
- Tests are organized by phase (`test_phase1_*` … `test_phase8_*`, plus `test_dev_tracking_pipeline.py` and `test_integration_quality.py`). Each phase corresponds to a vertical slice (SA nodes, RBAC, Agile layer, GitHub integration, etc.). There is no JS test runner configured.

### Backend env setup (one-time)
```
cd backend
python -m venv .venv
.venv\Scripts\activate   # PowerShell/cmd on Windows
pip install -r requirements.txt
copy .env.example .env   # then edit GEMINI_API_KEY
```

## Architecture

NAVIGATOR is an Electron desktop app with a Python FastAPI sidecar. **Three pipelines** run as LangGraph state machines and stream progress over a single WebSocket:
- **Design** — text idea or codebase → full PM+SA documentation (RTM, components, APIs, DB schema, tests, project structure)
- **Agile** — SA artifacts → distributed tasks, GitHub publishing, PM-approved design change flow
- **Dev Tracking** — GitHub PR webhook → reverse-engineer the branch → diff against published spec → PM approval for INTENTIONAL gaps

### Process topology
- **Electron main** (`electron/main.cjs`) spawns the Python backend as a child process. It allocates a free port via `findFreePort()`, passes it as `--port`, polls `GET /health` until ready (up to 240×500ms), then opens the BrowserWindow. On exit it kills the Python tree (`taskkill /f /t` on Windows, SIGTERM→SIGKILL elsewhere). All stdout/stderr pipes have explicit EPIPE guards — do not remove them.
- **Renderer** (`src/`, React 18 + Vite + Zustand + ReactFlow + Monaco) gets the backend port via IPC `get-backend-port` exposed in `electron/preload.cjs`.
- **Custom protocol** `navigator://` is registered for GitHub OAuth callbacks. Windows uses single-instance lock + `second-instance` event; macOS/Linux uses `open-url`.

### Backend layering (under `backend/`)
- `main.py` — FastAPI app factory only. Registers routers, mounts `/metrics`, runs `init_db()` in lifespan.
- `transport/` — `rest_handler.py` (REST APIRouter), `ws_handler.py` (`/ws/pipeline` entry point), `connection_manager.py`. **Pipeline imports are lazy** (`_ensure_pipeline()` at the top of `rest_handler.py`) to avoid LangGraph cold-start cost on the `/health` check. Symbols like `get_analysis_pipeline`, `execute_pipeline`, `build_reverse_context`, `normalize_action_type` are hoisted into module globals only after the first analyze/idea-chat call.
- `orchestration/` — `pipeline_runner.py` (WS-facing `run_analysis`, `run_idea_chat`, streaming, result persistence) and `executor.py` (REST-facing synchronous runner).
- `pipeline/core/` — `state.py` (`PipelineState` TypedDict), `action_type.py` (`normalize_action_type` → one of `CREATE` / `UPDATE` / `REVERSE_ENGINEER`, default `CREATE`), `ast_scanner.py`, `cost_manager.py`, `schemas.py`.
- `pipeline/orchestration/` — LangGraph wiring (NOT under `orchestration/`, despite the name overlap). `graph.py` builds compiled PM/SA/full-analysis graphs with a `_PipelineRegistry` cache; `facade.py` is the public accessor used by `orchestration/pipeline_runner.py` and `transport/`; `aux_graphs.py` holds the idea-chat graph; **`dev_tracking_graphs.py` holds the Dev Tracking PR graph** (own `_PipelineRegistry`).
- `pipeline/domain/{pm,sa,agile,chat,dev_tracking}/` — domain packages. PM/SA/Agile/chat use `nodes/` subfolders for individual LangGraph nodes. `dev_tracking/` is a flat package with `service.py` (entry adapter), `nodes.py`, `artifacts.py`, `knowledge.py`, `doc_updater.py`, `followup.py`.
- `result_shaping/` — `shape_result()` converts the raw final state dict into the UI-ready payload sent on `{type: "result", node: "complete"}`.
- `auth/` — JWT + GitHub OAuth (web flow + device flow) + RBAC. `database.py` defines two SQLAlchemy engines: `engine` (local.db) and `shared_engine` (shared.db). `deps.py` exposes `get_current_user`, `get_current_user_optional`, `require_pm`, etc.
- `connectors/` — `github_connector.py`, `folder_connector.py`, `repo_cache.py` (clones GitHub repos into a local cache so AST scanning can run on them).
- `observability/` — `structlog` logger, Prometheus `track_node` context manager wrapping each node execution.
- `storage/` — `publish_service.py` for shared.db snapshots.

### Two `orchestration` packages — disambiguation
- `backend/orchestration/` = the **runner** layer (WS streaming, REST executor, state persistence).
- `backend/pipeline/orchestration/` = the **graph definition** layer (LangGraph `StateGraph` construction, conditional edges, registry cache, dev_tracking graph builder).
When importing, the inner one is `pipeline.orchestration.facade` / `pipeline.orchestration.graph` / `pipeline.orchestration.dev_tracking_graphs`; the outer one is `orchestration.pipeline_runner` / `orchestration.executor`. Don't merge them.

### Pipeline graphs (`pipeline/orchestration/graph.py`)
Three compiled graphs cached in `_PipelineRegistry`:
- **PM** chain: `requirement_analyzer → stack_planner` with a conditional self-heal loop: if `stack_planner_output` contains items with `status == "PENDING_CRAWL"`, route to `stack_crawling → guardian → stack_planner` (max 2 iterations enforced by `loop_count`).
- **SA** chain: `sa_merge_project → component_scheduler → sa_unified_modeler → sa_test_analysis → sa_project_structure`. Single pass — `_route_sa_analysis` always returns `finish`.
- **Full analysis** (`get_analysis_pipeline`): PM chain + SA chain joined, where the stack-loop's `finish` edge goes directly to `sa_merge_project`.

### Dev Tracking graph (`pipeline/orchestration/dev_tracking_graphs.py`)
Separate from the analysis graph; built and cached in its own `_PipelineRegistry`. Linear chain (no loops, but with early-termination `_BLOCKING_ACTIONS = {"blocked", "pm_approval_pending"}`):
```
dev_task_planner → branch_fetcher → reverse_analyzer → code_inventory_builder
  → forensic_profiler → spec_loader → gap_analyzer → dev_knowledge_loader
  → intent_classifier → milestone_tracker → pm_report_generator
  → pr_comment_notifier → pr_status_check_updater → task_coordinator
  → analysis_persister → develop_embedding → develop_loop_controller
```
- Entry adapter: `pipeline.domain.dev_tracking.service.run_dev_tracking_analysis(payload, shared_db=...)`. Initial state seeds `timeline = []` and stashes `_shared_db` (popped before returning).
- Recursion limit: 150. Each node is wrapped with `_with_timeline()` so every transition appends `{node, status, ts}` to `state["timeline"]`.
- Return shape: `{status: "pending_pm_approval" | "complete" | "error", timeline, data: state}`. `NO_GAP_DETECTED` short-circuits to `complete`.

### Action types (`pipeline/core/action_type.py`)
- `CREATE` — text idea → full design.
- `UPDATE` — previous analysis JSON in `project_context` + new feature; `_inject_previous_artifacts()` parses prior `stack_planner_output`, `sa_test_analysis_output`, `sa_project_structure` into `previous_*` keys so nodes preserve IDs/positions.
- `REVERSE_ENGINEER` — `source_dir` is AST-scanned by `build_reverse_context()` (single scan produces both `project_context` string and `code_inventory` dict). For GitHub repos in `owner/repo` form, `repo_cache.get_local_repo_path()` clones/pulls first.
Always normalize with `normalize_action_type()` before branching — unknown values fall back to `CREATE`.

### Adding a pipeline node
```python
# backend/pipeline/domain/<domain>/nodes/your_node.py
from pipeline.core.state import PipelineState

async def your_node(state: PipelineState) -> dict:
    return {"your_output_key": ...}
```
Register in the relevant `_build_*_pipeline()` in `pipeline/orchestration/graph.py` (or `dev_tracking_graphs.py` for dev-tracking nodes). If you want cost tracking, wrap with `_wrap_node_with_usage("your_node", your_node)` (utility lives in `orchestration/pipeline_runner.py`). To stream "thinking" text to the UI, append `{"node": "...", "thinking": "..."}` entries to `state["thinking_log"]`; `stream_pipeline_updates` deduplicates and emits them as `{type: "thinking"}` messages.

### WebSocket protocol (`/ws/pipeline`)
The runner emits three message types — match this contract when adding nodes:
- `{type: "status", node, data: {status: "running"|"done"|"error", message?}}`
- `{type: "thinking", node, data: {text}}`
- `{type: "result", node: "complete"|"idea_chat", data: <shaped payload>}`

### Auth + RBAC
Three roles: `pm` (full access), `engineer`, `viewer`. Pipeline execution (`/api/analyze`, `/ws/pipeline analyze`) is **PM-only** — `run_analysis` checks `user.role != "pm"` and rejects. Use `Depends(get_current_user)` for any authenticated route, `Depends(get_current_user_optional)` where anonymous access is acceptable, and `Depends(require_pm)` for PM-gated ones. CORS is locked to `localhost` / `127.0.0.1` via `ALLOWED_ORIGIN_REGEX` in `main.py`; do not relax this.

### Databases
- `local.db` — personal data: `analysis_sessions`, `analysis_results`, `memo_items`, `design_change_requests`, `agile_tasks`. Accessed via `SessionLocal` / `get_db()`.
- `shared.db` — cross-team/server-owned data: `users`, `teams`, `subscriptions`, `published_snapshots`, `dev_pr_analyses` (the `DevPrAnalysis` table backs webhook duplicate-PR detection). **NAVIGATOR-SERVER owns shared.db**; default path is `../server/shared.db` (relative to `KNU-PROJECT/`). Override with `NAVIGATOR_SHARED_DB_PATH`. Accessed via `SharedSessionLocal` / `get_shared_db()`.
- local.db lives under `NAVIGATOR_STORAGE_DIR` (env var) or default `backend/storage/`. `run_test_user.bat` relies on this being separable.

### Dev Tracking webhook flow (`POST /api/webhook/github`)
1. **HMAC verification** — `X-Hub-Signature-256` validated against `NAVIGATOR_GITHUB_WEBHOOK_SECRET` via `_verify_github_webhook_signature()`. Missing secret produces a warning but does not reject.
2. **Event filter** — only `pull_request` events with action in `{opened, synchronize, reopened}` proceed; others return `handled: false` with a reason.
3. **Duplicate detection** — `_normalize_github_pr_webhook()` extracts `(owner, repo, pr_number, head_sha)`; if a `DevPrAnalysis` row already exists for that tuple, the request returns `handled: false, reason: "duplicate head_sha already analyzed"`. Duplicate-check failure does NOT block the rest of the flow (caught silently).
4. **Pipeline invocation** — `run_dev_tracking_analysis(normalized, shared_db=...)` runs the Dev Tracking graph and returns its result under `data`.
5. **PM decision follow-up** — when PM approves/rejects via the agile task PATCH flow, `dev_tracking.followup.run_dev_gap_decision_followup()` runs three things:
   - Builds the decision artifact + persists to shared knowledge store (`persist_dev_knowledge_artifact`).
   - Calls `run_doc_updater_for_dev_gap_decision()` — only on `APPROVED_INTENTIONAL_CHANGE`, calls `agile.nodes.doc_sync.sync_docs()` with retry (`doc_update_max_attempts`, default 2). On reject/pending, returns `{synced: false, action: "skipped"}` without touching docs.
   - Posts a PR comment via `gh pr comment` (runner injected — defaults to a stub that returns WARN if unavailable). Comment failure never blocks the decision itself.

### Frontend state (`src/store/`)
Zustand store split into slices under `src/store/slices/` (auth, pipeline, ws, session, github, publish, ui, file, notification). Don't add new top-level state — extend the matching slice. The WS slice owns reconnection and the message dispatch table that maps `{type, node}` back to slice mutations.

`useAppStore.js` composes all slices with a `setWithSave` wrapper that debounces (`500ms`) `saveCurrentSession()` after every mutation, so session persistence is automatic — you don't need to call save manually after each `set`.

### Memo flow (relevant when touching memo/UPDATE features)
- Memos are scoped to `currentSessionId` and persisted to `local.db` (`memo_items`). Endpoint: `GET/POST/DELETE /api/memos`, plus `POST /api/memos/apply` (`MemoApplyRequest{memo_ids: list}`) which marks `applied=true` + sets `applied_at`.
- `MemoManager` (`src/components/resultViewer/MemoManager.jsx`) splits view into "활성 메모" (`!applied`) vs "이전 메모" (`applied`).
- `pipelineSlice.startMemoDrivenUpdate(memoIds)` runs UPDATE in the **same session** (does not call `createSession`) — it marks the selected memos applied locally, then calls `markMemosApplied(persistableIds)` to persist (skipping `temp_*` IDs that haven't been confirmed by the server yet). Creating a new session here would orphan archived memos against the previous session ID.
- `syncMemos` has a guard: if the server returns an empty list but local non-temp memos exist, it preserves them (handles new-session race where backend hasn't been written yet).

### LLM model
`backend/version.py` defines `DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"` and `APP_VERSION`. The only currently active model in `AVAILABLE_MODELS` (`transport/rest_handler.py`) is the default — other Gemini variants are commented out as "not available yet". `GEMINI_API_KEY` is required in `backend/.env`.

### Environment variables
| Variable | Purpose |
|----------|---------|
| `GEMINI_API_KEY` | **Required.** Google Gemini API key. |
| `NAVIGATOR_STORAGE_DIR` | Override `backend/storage/` (local.db + cached repos + sessions). |
| `NAVIGATOR_SHARED_DB_PATH` | Override default `../server/shared.db` for the shared DB. |
| `NAVIGATOR_GITHUB_TOKEN` / `GITHUB_TOKEN` | Used by Dev Tracking doc_sync + PR comment posting. `NAVIGATOR_GITHUB_TOKEN` takes precedence. |
| `NAVIGATOR_GITHUB_WEBHOOK_SECRET` | HMAC secret for `/api/webhook/github`. Missing = warning, not rejection. |
| `NAVIGATOR_DEFAULT_TEAM_ID` | Team ID stamped on webhook-initiated Dev Tracking runs. |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | GitHub OAuth (Web + Device flow). |
| `ENV` | `dev` / `prod` (default `dev`). |
