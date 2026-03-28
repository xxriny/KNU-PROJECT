"""
PM Agent Pipeline v2 — FastAPI Backend Sidecar v2.2
앱 초기화 + 라우터 등록만 담당. (REQ-001 ~ REQ-007 리팩토링)

계층 구조:
  transport/      — WebSocket 연결 관리, REST APIRouter
  orchestration/  — 파이프라인 실행 로직
  result_shaping/ — raw 결과 정형화 (schema-driven)
  observability/  — structlog 기반 로깅, Prometheus 메트릭

Usage:
    python main.py --port 8765
    (Electron main.js가 빈 포트를 할당하여 인자로 전달)
"""

import os
import sys
import argparse
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from version import APP_VERSION

# ── 경로 설정 ────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# .env 로드 (UTF-8 강제)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, ".env"), encoding="utf-8")
except ImportError:
    pass

# ── 계층 임포트 ──────────────────────────────────────────
from transport.rest_handler import rest_router
from transport.ws_handler import websocket_pipeline
from observability.metrics import make_metrics_app
from observability.logger import get_logger

ALLOWED_ORIGIN_REGEX = r"^(null|https?://(127\.0\.0\.1|localhost)(:\d+)?)$"


# ── App Lifespan ─────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    get_logger().info(f"[Backend] PM Agent Pipeline v2.2 starting on PID {os.getpid()}...")
    yield
    get_logger().info(f"[Backend] Shutting down...")


# ── FastAPI 앱 생성 ──────────────────────────────────────
app = FastAPI(
    title="PM Agent Pipeline Backend",
    version=APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=ALLOWED_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 라우터 등록 ──────────────────────────────────────────
app.include_router(rest_router)
app.add_api_websocket_route("/ws/pipeline", websocket_pipeline)

# ── Prometheus 메트릭 엔드포인트 (prometheus_client 설치 시 활성화) ──
_metrics_app = make_metrics_app()
if _metrics_app is not None:
    app.mount("/metrics", _metrics_app)


# ── Entry Point ──────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description="PM Agent Pipeline Backend")
    parser.add_argument("--port", type=int, default=8765, help="Server port")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Server host")
    args = parser.parse_args()

    get_logger().info(f"[Backend] Starting on {args.host}:{args.port}")
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
        ws_ping_interval=30,
        ws_ping_timeout=30,
    )
