"""
WebSocket 엔드포인트 (REQ-001)
연결 관리와 메시지 dispatch를 담당하며,
실제 파이프라인 실행은 orchestration 계층에 위임한다.
"""

from __future__ import annotations

import json

from fastapi import WebSocket, WebSocketDisconnect

from transport.connection_manager import manager
from orchestration.pipeline_runner import run_analysis, run_revision, run_idea_chat


async def websocket_pipeline(websocket: WebSocket):
    """
    WebSocket 파이프라인 엔드포인트.

    Client → Server:
        {"type": "analyze"|"revise"|"idea_chat"|"ping", "payload": {...}}

    Server → Client:
        {"type": "status"|"thinking"|"result"|"error"|"pong", "node": "...", "data": {...}}
    """
    await manager.connect(websocket)
    print(f"[WS] Client connected. Active: {len(manager.active_connections)}")

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
                await run_analysis(websocket, payload)
            elif msg_type == "revise":
                await run_revision(websocket, payload)
            elif msg_type == "idea_chat":
                await run_idea_chat(websocket, payload)
            elif msg_type == "ping":
                await manager.send_json(websocket, {"type": "pong"})
            else:
                await manager.send_json(websocket, {
                    "type": "error",
                    "data": {"message": f"Unknown type: {msg_type}"},
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"[WS] Client disconnected. Active: {len(manager.active_connections)}")
    except Exception as e:
        manager.disconnect(websocket)
        print(f"[WS Error] {e}")
