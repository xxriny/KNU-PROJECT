"""
Pipeline Orchestration 계층 
WebSocket 핸들러에서 파이프라인 실행 로직을 분리.
_ws_run_* 시리즈 + 스트리밍 로직을 단일 모듈에서 관리.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from fastapi import WebSocket

from pipeline.orchestration.facade import (
    get_analysis_pipeline,
    get_idea_pipeline,
    get_pm_pipeline,
    get_sa_pipeline,
    get_scan_pipeline,
    get_rag_ingest_pipeline,
    get_pipeline_routing_map,
    get_pm_routing_map,
    get_sa_routing_map,
    get_scan_routing_map,
    get_rag_routing_map,
    get_idea_chat_routing_map,
)
from pipeline.core.action_type import ANALYSIS_ACTION_TYPES, normalize_action_type
from pipeline.domain.rag.ast_scanner import extract_functions, summarize_for_llm
from result_shaping.result_shaper import shape_result
from pipeline.core.utils import to_serializable
from observability.logger import get_logger
from observability.metrics import track_node
from transport.connection_manager import manager
from version import DEFAULT_MODEL


# ─── 입력 검증 ────────────────────────────────────────────

def validate_analysis_inputs(action_type: str, idea: str, source_dir: str) -> str | None:
    """모드별 필수 입력 검증. 에러 메시지 또는 None 반환."""
    normalized = normalize_action_type(action_type)
    idea_text = (idea or "").strip()
    source_path = (source_dir or "").strip()

    if normalized == "REVERSE_ENGINEER" and not source_path:
        return "역공학 모드입니다. 먼저 폴더를 선택하세요."
    if normalized in {"CREATE", "UPDATE"} and not idea_text:
        return "신규 기획/기능 확장 모드에서는 아이디어 입력이 필요합니다."
    return None


def build_reverse_context(source_dir: str) -> str:
    """source_dir AST 스캔 결과를 REVERSE 분석용 project_context로 변환."""
    source_path = (source_dir or "").strip()
    if not source_path:
        return ""
    functions = extract_functions(source_path, max_functions=250)
    if not functions:
        return ""
    unique_files = len({fn.get("file", "") for fn in functions if fn.get("file")})
    summary = summarize_for_llm(functions, max_chars=7000)
    return (
        "아래는 로컬 프로젝트 정적 스캔 결과입니다. "
        "이 정보를 기준으로 프로젝트 구조, 핵심 모듈, 유지보수 리스크를 분석하세요.\n\n"
        f"- source_dir: {source_path}\n"
        f"- scanned_files: {unique_files}\n"
        f"- scanned_functions: {len(functions)}\n\n"
        "[함수 요약]\n"
        f"{summary}"
    )


def analysis_pipeline_type(action_type: str) -> str:
    normalized = normalize_action_type(action_type)
    if normalized == "REVERSE_ENGINEER":
        return "analysis_reverse"
    if normalized == "UPDATE":
        return "analysis_update"
    return "analysis_create"


async def _run_pipeline_base(
    ws: WebSocket,
    *,
    pipeline,
    routing: dict,
    state_payload: dict,
    pipeline_type: str,
    result_node: str = "complete",
    save: bool = True,
    result_mutator=None,
    log=None,
) -> dict:
    """공통 파이프라인 실행, 결과 정형화, 전송, 저장 처리.
    연속 실행을 위해 최종 결과를 반환함.
    """
    try:
        result = await stream_pipeline_updates(ws, pipeline, state_payload, routing=routing)

        if result.get("error"):
            await manager.send_json(ws, {"type": "error", "data": {"message": result["error"]}})
            return result

        # 중간 단계에서는 저장을 스킵할 수 있음 (save=False)
        if save:
            shaped = shape_result(result)
            shaped["pipeline_type"] = pipeline_type
            if result_mutator is not None:
                result_mutator(shaped)

            await manager.send_json(ws, {"type": "result", "node": result_node, "data": shaped})
        
        return result

    except Exception as e:
        get_logger().exception("pipeline execution failed")
        await manager.send_json(ws, {"type": "error", "data": {"message": str(e)}})
        return {"error": str(e)}


# ─── WebSocket 파이프라인 실행 ────────────────────────────

async def run_analysis(ws: WebSocket, payload: dict) -> None:
    api_key = payload.get("api_key", "")
    model = payload.get("model", DEFAULT_MODEL)
    idea = payload.get("idea", "")
    context = payload.get("context", "")
    action_type = normalize_action_type(payload.get("action_type", "CREATE"))
    source_dir = payload.get("source_dir", "")

    validation_error = validate_analysis_inputs(action_type, idea, source_dir)
    if validation_error:
        await manager.send_json(ws, {"type": "error", "data": {"message": validation_error}})
        return

    if action_type == "REVERSE_ENGINEER" and not (context or "").strip():
        context = build_reverse_context(source_dir)
        if not context:
            await manager.send_json(ws, {
                "type": "error",
                "data": {"message": "선택한 폴더에서 분석 가능한 함수/메서드를 찾지 못했습니다. 프로젝트 루트를 확인하세요."},
            })
            return

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    log = get_logger(run_id)
    log.info("analysis_start", action_type=action_type)

    initial_state = {
        "api_key": api_key,
        "model": model,
        "input_idea": idea,
        "project_context": context,
        "source_dir": source_dir,
        "action_type": action_type,
        "run_id": run_id,
    }

    # 1. RAG Ingestion (Stage 1) - 코드 청킹 및 벡터 색인
    scan_result = await _run_pipeline_base(
        ws,
        pipeline=get_rag_ingest_pipeline(),
        routing=get_rag_routing_map(),
        state_payload=initial_state,
        pipeline_type="rag_ingest",
        save=False,
        log=log,
    )

    if scan_result.get("error"):
        return

    # 2. PM Pipeline (Stage 2) - 요구사항 원자화 및 기획
    pm_result = await _run_pipeline_base(
        ws,
        pipeline=get_pm_pipeline(),
        routing=get_pm_routing_map(),
        state_payload=scan_result,
        pipeline_type="pm_only",
        save=False,
        log=log,
    )

    if pm_result.get("error"):
        return

    # 3. SA Pipeline (Stage 3) - 아키텍처 설계
    sa_result = await _run_pipeline_base(
        ws,
        pipeline=get_sa_pipeline(),
        routing=get_sa_routing_map(),
        state_payload=pm_result,
        pipeline_type=analysis_pipeline_type(action_type),
        result_node="complete",
        save=True,
        log=log,
    )


async def run_idea_chat(ws: WebSocket, payload: dict) -> None:
    api_key = payload.get("api_key", "")
    model = payload.get("model", DEFAULT_MODEL)

    await _run_pipeline_base(
        ws,
        pipeline=get_idea_pipeline(),
        routing=get_idea_chat_routing_map(),
        state_payload={
            "api_key": api_key,
            "model": model,
            "user_request": payload.get("message", ""),
            "chat_history": payload.get("chat_history", []),
            "previous_result": payload.get("previous_result", {}),
        },
        pipeline_type="idea_chat",
        result_node="idea_chat",
        save=False,
        result_mutator=lambda shaped: shaped.update({"chat_reply": shaped.get("agent_reply", "")}),
    )


# ─── 스트리밍 ─────────────────────────────────────────────

async def stream_pipeline_updates(
    ws: WebSocket,
    pipeline,
    payload: dict,
    *,
    routing: dict,
) -> dict:
    """파이프라인 astream을 소비하며 WS로 실시간 상태를 브로드캐스트한다.

    Args:
        routing: get_pipeline_routing_map() 반환값
                 {"first_node": str, "next_nodes": dict, "start_message": str}
    """
    first_node: str = routing["first_node"]
    next_nodes: dict[str, list[str]] = routing["next_nodes"]
    start_message: str = routing.get("start_message", "파이프라인 시작...")
    action_type: str = payload.get("action_type", "unknown")

    aggregated: dict = {**payload}
    seen_thinking: set[tuple[str, str]] = set()

    await manager.send_json(ws, {
        "type": "status",
        "node": first_node,
        "data": {"status": "running", "message": start_message},
    })

    async for update in pipeline.astream(payload, stream_mode="updates"):
        if not isinstance(update, dict):
            continue

        for node_name, node_result in update.items():
            with track_node(node_name, action_type):
                ser = to_serializable(node_result)
                if not isinstance(ser, dict):
                    continue

                _merge_state(aggregated, ser)
                await _emit_thinking(ws, ser.get("thinking_log", []), seen_thinking)

                node_error = ser.get("error")
                if node_error:
                    await manager.send_json(ws, {
                        "type": "status",
                        "node": node_name,
                        "data": {"status": "error"},
                    })
                    aggregated["error"] = node_error
                    return aggregated

                await manager.send_json(ws, {
                    "type": "status",
                    "node": node_name,
                    "data": {"status": "done"},
                })

                for next_node in next_nodes.get(node_name, []):
                    await manager.send_json(ws, {
                        "type": "status",
                        "node": next_node,
                        "data": {"status": "running"},
                    })

                await asyncio.sleep(0)

    return aggregated


async def _emit_thinking(
    ws: WebSocket,
    thinking_log: list,
    seen: set[tuple[str, str]],
) -> None:
    for entry in thinking_log or []:
        if not isinstance(entry, dict):
            continue
        node_name = str(entry.get("node", "")) or "unknown"
        text = str(entry.get("thinking", ""))
        key = (node_name, text)
        if key in seen:
            continue
        seen.add(key)
        await manager.send_json(ws, {
            "type": "thinking",
            "node": node_name,
            "data": {"text": text},
        })


def _merge_state(target: dict, source: dict) -> None:
    for key, value in source.items():
        if key == "thinking_log":
            existing = target.get(key, [])
            if isinstance(existing, list) and isinstance(value, list):
                target[key] = existing + [e for e in value if e not in existing]
            else:
                target[key] = value
            continue
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            target[key] = {**target[key], **value}
            continue
        target[key] = value
