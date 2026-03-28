"""
Connection Manager — WebSocket 연결 풀 관리 (REQ-001)
transport 계층의 단일 진실 연결 관리자.
"""

from __future__ import annotations

from fastapi import WebSocket
from observability.logger import get_logger


class ConnectionManager:
    def __init__(self):
        self.active_connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def send_json(self, websocket: WebSocket, data: dict):
        try:
            await websocket.send_json(data)
        except Exception as e:
            get_logger().warning("ws_send_failed", error=str(e))
            self.disconnect(websocket)


manager = ConnectionManager()
