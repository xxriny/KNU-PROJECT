"""
NAVIGATOR-SERVER — 공유 인증·빌링·API 키 관리 서버.

배포 시 이 서버가 shared.db를 소유하고
NAVIGATOR 데스크탑 앱은 이 서버를 통해 인증/빌링/Gemini 키를 관리합니다.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routers import auth, billing, gemini


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="NAVIGATOR Server",
    description="공유 인증 · 빌링 · Gemini API 키 관리",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — 데스크탑 앱(Electron)과 개발 서버 허용
_ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000,app://.",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(billing.router)
app.include_router(gemini.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "navigator-server"}
