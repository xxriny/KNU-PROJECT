from __future__ import annotations

import json
import re
from pathlib import Path

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.core.utils import call_structured
from pipeline.domain.dev.schemas import GlobalFESyncPlanningOutput


SYSTEM_PROMPT = """# 역할: Global FE Sync Gate
## 목표
- UI/UX 결과와 Frontend 결과의 정합성을 검토한다.
- pass 또는 재작업 대상을 결정한다.

## 규칙
- 출력은 반드시 구조화된 JSON만 반환한다.
- status는 pass, rework_uiux, rework_frontend 중 하나만 사용한다.
- reason은 FE sync 판단 근거를 한 문장으로 작성한다.
- shared_components는 실제로 맞물리는 공통 컴포넌트/대상만 적는다.
- sync_actions는 재정렬이 필요할 때 구체적으로 작성한다.
- UI intent, shared component naming, frontend wiring 정합성을 우선 검토한다.
- thinking은 반드시 한국어 핵심 단어 3개 이내로 작성한다.
"""


LEGACY_SYSTEM_PROMPT = SYSTEM_PROMPT

SYSTEM_PROMPT = """
당신은 '프론트엔드 전역 동기화 게이트'입니다. UIUX 핸드오프와 프론트엔드 계획이 같은 화면, 라우트, 컴포넌트, API 계약을 바라보는지 판정하십시오.

[1. 판정 기준 (MANDATORY)]
- UIUX routes는 frontend_plan.routes에 모두 포함되어야 합니다.
- UIUX component_tree와 frontend files/screen_bindings는 같은 화면 책임을 공유해야 합니다.
- api_client_needs와 data_contracts는 프론트엔드 계획에 누락 없이 반영되어야 합니다.
- UIUX가 문제면 rework_uiux, 프론트 구현 계획이 문제면 rework_frontend로 명확히 분기하십시오.

[2. 출력 규칙]
- structured JSON만 반환하십시오.
- status는 "pass", "rework_uiux", "rework_frontend" 중 하나만 사용하십시오.
- reason은 판정 근거를 한 문장으로 작성하십시오.
- shared_components는 실제로 양쪽에서 공유되는 대상만 작성하십시오.
- sync_actions는 재작업이 필요한 경우에만 구체적으로 작성하십시오.
- thinking은 한국어 핵심 단어 3개 이내입니다.

[3. 출력 규격(JSON)]
{
  "thinking": "단어 3개",
  "status": "pass|rework_uiux|rework_frontend",
  "reason": "판정 근거",
  "shared_components": ["공유 대상"],
  "sync_actions": ["동기화 작업"]
}
"""


def _build_user_message(
    *,
    uiux_result: dict,
    frontend_result: dict,
    uiux_task_spec: dict,
    frontend_task_spec: dict,
    project_rag_context: dict,
    artifact_rag_context: dict,
) -> str:
    return json.dumps({
        "uiux_result": uiux_result,
        "frontend_result": frontend_result,
        "uiux_task_spec": uiux_task_spec,
        "frontend_task_spec": frontend_task_spec,
        "project_rag_context": project_rag_context,
        "artifact_rag_context": artifact_rag_context,
    }, ensure_ascii=False)


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


def _read_frontend_code(codegen_result: dict) -> tuple[str, list[str]]:
    contents = []
    paths = []
    for path in _result_file_paths(codegen_result, (".ts", ".tsx", ".js", ".jsx")):
        try:
            contents.append(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            contents.append(path.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
        paths.append(str(path))
    return "\n".join(contents), paths


def _endpoint_path(value: str) -> str:
    text = str(value or "").strip()
    match = re.match(r"^(GET|POST|PUT|PATCH|DELETE)\s+(.+)$", text, re.I)
    if match:
        text = match.group(2)
    return text.rstrip("/") or text


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


@pipeline_node("develop_global_fe_sync_gate")
def develop_global_fe_sync_gate_node(ctx: NodeContext) -> dict:
    uiux = ctx.sget("uiux_result", {}) or {}
    uiux_artifact = ctx.sget("uiux_artifact", {}) or {}
    frontend = ctx.sget("frontend_result", {}) or {}
    frontend_codegen = ctx.sget("frontend_codegen_result", {}) or {}

    def _normalize(items: list) -> set[str]:
        normalized = set()
        for item in items or []:
            text = str(item)
            normalized.add(text.split(":", 1)[-1] if ":" in text else text)
        return normalized

    ui_files = _normalize(uiux.get("files", []) or [])
    fe_files = _normalize(frontend.get("files", []) or [])
    overlap = sorted(ui_files & fe_files)

    sync_actions = []
    status = "pass"
    reason = "UI/UX and frontend plans are aligned."
    handoff = uiux_artifact.get("frontend_handoff") or {}
    ui_routes = set(str(route) for route in handoff.get("routes", []) or [] if route)
    fe_routes = set(str(route) for route in (frontend.get("frontend_plan", {}) or {}).get("routes", []) or [] if route)
    frontend_code, frontend_code_files = _read_frontend_code(frontend_codegen)

    if ui_routes and fe_routes and not ui_routes.issubset(fe_routes):
        status = "rework_frontend"
        reason = "Frontend plan does not cover all UI/UX handoff routes."
        missing = sorted(ui_routes - fe_routes)
        sync_actions.append(f"Add missing frontend routes: {', '.join(missing)}")
    elif not overlap and ui_files and fe_files:
        status = "rework_frontend"
        reason = "UI/UX handoff and frontend scope do not share explicit targets."
        sync_actions.append("Align frontend targets with UI/UX shared component scope.")

    if frontend_code:
        missing_code_routes = [
            route for route in sorted(ui_routes)
            if route and route not in frontend_code
        ]
        if missing_code_routes:
            status = "rework_frontend"
            reason = "Generated frontend code does not implement all UI/UX handoff routes."
            _append_unique(sync_actions, f"Add generated route/code references for UI/UX routes: {', '.join(missing_code_routes)}")

        api_needs = [str(item) for item in handoff.get("api_client_needs", []) or [] if str(item).strip()]
        missing_api_needs = [
            need for need in api_needs
            if _endpoint_path(need) and _endpoint_path(need) not in frontend_code
        ]
        if missing_api_needs:
            status = "rework_frontend"
            reason = "Generated frontend code does not implement all UI/UX API client needs."
            _append_unique(sync_actions, f"Bind generated frontend API client to UI/UX needs: {', '.join(missing_api_needs)}")

        required_states = set()
        for screen in uiux_artifact.get("screens", []) or []:
            if isinstance(screen, dict):
                required_states.update(str(state).lower() for state in screen.get("states", []) or [] if state)
        missing_states = [
            state for state in sorted(required_states)
            if state in {"loading", "error", "empty", "success", "validation"}
            and re.search(r"\b" + re.escape(state) + r"\b", frontend_code, re.I) is None
        ]
        if missing_states:
            status = "rework_frontend"
            reason = "Generated frontend code does not represent all UI/UX screen states."
            _append_unique(sync_actions, f"Represent UI/UX screen states in generated frontend code: {', '.join(missing_states)}")

    fallback = {
        "status": status,
        "reason": reason,
        "shared_components": overlap,
        "sync_actions": sync_actions,
        "code_sync": {
            "checked_files": frontend_code_files,
            "checked": bool(frontend_code),
        },
    }

    # ── 리턴값 구성 ──
    prev_retry = int(ctx.sget("global_fe_sync_retry_count", 0) or 0)
    next_retry = prev_retry + 1 if status != "pass" else prev_retry

    if ctx.api_key:
        res = call_structured(
            api_key=ctx.api_key,
            model=ctx.model,
            schema=GlobalFESyncPlanningOutput,
            system_prompt=SYSTEM_PROMPT,
            user_msg=_build_user_message(
                uiux_result=uiux,
                frontend_result={"frontend_result": frontend, "uiux_artifact": uiux_artifact},
                uiux_task_spec=ctx.sget("uiux_task_spec", {}) or {},
                frontend_task_spec=ctx.sget("frontend_task_spec", {}) or {},
                project_rag_context=ctx.sget("project_rag_context", {}) or {},
                artifact_rag_context=ctx.sget("artifact_rag_context", {}) or {},
            ),
            max_retries=3,
            temperature=0.1,
            compress_prompt=True,
        )
        out = res.parsed.model_dump()
        if out.get("status") != "pass":
            next_retry = prev_retry + 1
        
        return {
            "global_fe_sync_result": out,
            "global_fe_sync_retry_count": next_retry,
            "_thinking": res.parsed.thinking or "fe-sync, shared-components, alignment",
        }

    return {
        "global_fe_sync_result": fallback,
        "global_fe_sync_retry_count": next_retry,
        "_thinking": "uiux-frontend-sync, shared-components, scope-alignment",
    }
