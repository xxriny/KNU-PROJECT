"""
WebSocket 엔드포인트 (REQ-001)
연결 관리와 메시지 dispatch를 담당하며,
실제 파이프라인 실행은 orchestration 계층에 위임한다.
"""

from __future__ import annotations

import json

from fastapi import WebSocket, WebSocketDisconnect

from transport.connection_manager import manager
from observability.logger import get_logger

# pipeline_runner는 langgraph를 포함하므로 첫 WS 연결 시 지연 로드
_run_analysis = None
_run_idea_chat = None

def _ensure_ws_pipeline():
    global _run_analysis, _run_idea_chat
    if _run_analysis is not None:
        return
    from orchestration.pipeline_runner import run_analysis, run_idea_chat
    _run_analysis = run_analysis
    _run_idea_chat = run_idea_chat


async def websocket_pipeline(websocket: WebSocket):
    """
    WebSocket 파이프라인 엔드포인트.

    Client → Server:
        {"type": "analyze"|"idea_chat"|"ping", "payload": {...}}

    Server → Client:
        {"type": "status"|"thinking"|"result"|"error"|"pong", "node": "...", "data": {...}}
    """
    await manager.connect(websocket)
    get_logger().info(f"[WS] Client connected. Active: {len(manager.active_connections)}")

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await manager.send_json(websocket, {
                    "type": "error",
                    "data": {"message": "Invalid JSON"},
                })
                continue

            msg_type = msg.get("type", "")
            payload = msg.get("payload", {})

            if msg_type == "analyze":
                _ensure_ws_pipeline()
                await _run_analysis(websocket, payload)
            elif msg_type == "idea_chat":
                _ensure_ws_pipeline()
                await _run_idea_chat(websocket, payload)
            elif msg_type == "ping":
                await manager.send_json(websocket, {"type": "pong"})
            else:
                await manager.send_json(websocket, {
                    "type": "error",
                    "data": {"message": f"Unknown type: {msg_type}"},
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        get_logger().info(f"[WS] Client disconnected. Active: {len(manager.active_connections)}")
    except Exception as e:
        manager.disconnect(websocket)
        get_logger().error(f"[WS Error] {e}")
