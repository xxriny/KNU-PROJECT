"""
REST API 엔드포인트 (REQ-001)
/health, /api/* 엔드포인트를 APIRouter로 분리.
main.py에서 app.include_router(rest_router) 호출.
"""

from __future__ import annotations

from datetime import datetime
import os
import re
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from version import APP_VERSION, DEFAULT_MODEL
from observability.logger import get_logger
from pipeline.core.action_type import normalize_action_type
from pipeline.orchestration.facade import get_analysis_pipeline, get_revision_pipeline, get_idea_pipeline
from orchestration.executor import execute_pipeline
from orchestration.pipeline_runner import (
    validate_analysis_inputs,
    build_reverse_context,
    analysis_pipeline_type,
)

# ── 상수 ─────────────────────────────────────────────────
AVAILABLE_MODELS = [
    DEFAULT_MODEL,
    # "gemini-3.0-flash",  # not available yet
    # "gemini-3.0-pro",    # not available yet
]


# ── 경로 보안 헬퍼 ────────────────────────────────────────
_allowed_project_roots: set[str] = set()


def _normalize_path(path: str) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def _is_within_root(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def register_project_root(root_path: str):
    _allowed_project_roots.add(_normalize_path(root_path))


def is_allowed_project_file(path: str) -> bool:
    normalized = _normalize_path(path)
    return any(_is_within_root(normalized, root) for root in _allowed_project_roots)


# ── Pydantic 모델 ─────────────────────────────────────────
class AnalysisRequest(BaseModel):
    idea: str
    context: str = ""
    api_key: str = ""
    model: str = DEFAULT_MODEL
    action_type: str = "CREATE"
    source_dir: str = ""


class RevisionRequest(BaseModel):
    user_request: str
    previous_result: dict = {}
    chat_history: list = []
    api_key: str = ""
    model: str = DEFAULT_MODEL


class IdeaChatRequest(BaseModel):
    message: str
    chat_history: list = []
    previous_result: dict = {}
    api_key: str = ""
    model: str = DEFAULT_MODEL


class ScanRequest(BaseModel):
    path: str
    max_depth: int = 3


class ReadFileRequest(BaseModel):
    path: str


class DeleteSessionRequest(BaseModel):
    pass


class MemoRequest(BaseModel):
    session_id: str
    text: str
    selected_text: str = ""
    section: str = "Global"


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = APP_VERSION


# ── Router ───────────────────────────────────────────────
rest_router = APIRouter()


@rest_router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse()


@rest_router.get("/api/config")
async def get_config():
    has_key = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    return {
        "has_api_key": has_key,
        "default_model": DEFAULT_MODEL,
        "available_models": AVAILABLE_MODELS,
    }


@rest_router.post("/api/scan-folder")
async def scan_folder_endpoint(req: ScanRequest):
    from connectors.folder_connector import scan_folder
    if not req.path:
        return {"status": "error", "error": "폴더 경로가 비어있습니다."}

    normalized_root = _normalize_path(req.path)
    if not os.path.isdir(normalized_root):
        return {"status": "error", "error": f"유효하지 않은 폴더: {req.path}"}

    try:
        register_project_root(normalized_root)
        result = scan_folder(normalized_root, max_depth=req.max_depth)
        return {"status": "ok", **result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@rest_router.post("/api/read-file")
async def read_file_endpoint(req: ReadFileRequest):
    if not req.path:
        return {"status": "error", "error": "파일 경로가 비어있습니다."}

    normalized_path = _normalize_path(req.path)
    if not os.path.isfile(normalized_path):
        return {"status": "error", "error": f"유효하지 않은 파일: {req.path}"}
    if not _allowed_project_roots:
        return {"status": "error", "error": "먼저 프로젝트 폴더를 스캔하세요."}
    if not is_allowed_project_file(normalized_path):
        return {"status": "error", "error": "선택한 프로젝트 폴더 밖의 파일은 읽을 수 없습니다."}

    try:
        with open(normalized_path, "r", encoding="utf-8", errors="replace") as handle:
            content = handle.read()
        return {"status": "ok", "path": normalized_path, "content": content}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _to_response(result) -> dict:
    """PipelineResult → REST JSON 응답 변환."""
    if result.success:
        return {"status": "ok", "data": result.data}
    return {"status": "error", "error": result.error}


@rest_router.post("/api/analyze")
async def analyze(req: AnalysisRequest):
    try:
        api_key = req.api_key
        action_type = normalize_action_type(req.action_type)
        validation_error = validate_analysis_inputs(action_type, req.idea, req.source_dir)
        if validation_error:
            return {"status": "error", "error": validation_error}

        context = req.context
        if action_type == "REVERSE_ENGINEER" and not (context or "").strip():
            context = build_reverse_context(req.source_dir)
            if not context:
                return {
                    "status": "error",
                    "error": "선택한 폴더에서 분석 가능한 함수/메서드를 찾지 못했습니다.",
                }

        return _to_response(execute_pipeline(
            get_analysis_pipeline(action_type),
            {
                "api_key": api_key,
                "model": req.model,
                "input_idea": req.idea,
                "project_context": context,
                "source_dir": req.source_dir,
                "action_type": action_type,
                "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            },
            analysis_pipeline_type(action_type),
        ))
    except Exception as e:
        get_logger().exception("analyze endpoint failed")
        return {"status": "error", "error": str(e)}


@rest_router.post("/api/revise")
async def revise(req: RevisionRequest):
    try:
        api_key = req.api_key
        return _to_response(execute_pipeline(
            get_revision_pipeline(),
            {
                "api_key": api_key,
                "model": req.model,
                "user_request": req.user_request,
                "previous_result": req.previous_result,
                "chat_history": req.chat_history,
            },
            "revision",
        ))
    except Exception as e:
        get_logger().exception("revise endpoint failed")
        return {"status": "error", "error": str(e)}


@rest_router.post("/api/idea-chat")
async def idea_chat(req: IdeaChatRequest):
    try:
        api_key = req.api_key
        return _to_response(execute_pipeline(
            get_idea_pipeline(),
            {
                "api_key": api_key,
                "model": req.model,
                "user_request": req.message,
                "chat_history": req.chat_history,
                "previous_result": req.previous_result,
            },
            "idea_chat",
            result_mutator=lambda s: s.update({"chat_reply": s.get("agent_reply", "")}),
        ))
    except Exception as e:
        get_logger().exception("idea_chat endpoint failed")
        return {"status": "error", "error": str(e)}


@rest_router.delete("/api/session/{run_id}")
async def delete_session(run_id: str, req: Optional[DeleteSessionRequest] = None):
    if not re.match(r"^\d{8}_\d{6}$", run_id):
        return {"status": "error", "error": "Invalid run_id format. Expected YYYYMMDD_HHMMSS"}

    try:
        # DB 지식 삭제
        from pipeline.domain.pm.nodes.pm_db import delete_pm_knowledge
        from pipeline.domain.sa.nodes.sa_db import delete_sa_knowledge
        from pipeline.domain.pm.nodes.stack_db import delete_session_knowledge
        
        pm_deleted = delete_pm_knowledge(run_id)
        sa_deleted = delete_sa_knowledge(run_id)
        stack_deleted = delete_session_knowledge(run_id)

        return {
            "status": "ok",
            "message": f"Session {run_id} deleted from RAG",
            "pm_docs_deleted": pm_deleted,
            "sa_docs_deleted": sa_deleted,
            "stack_docs_deleted": stack_deleted,
        }
    except Exception as e:
        get_logger().exception(f"delete_session failed for run_id={run_id}")
        return {
            "status": "error",
            "error": str(e),
            "message": f"Partial deletion for {run_id}",
        }


@rest_router.get("/api/memos")
async def get_memos_endpoint(session_id: Optional[str] = None):
    from pipeline.domain.pm.nodes.memo_db import get_memos
    try:
        memos = get_memos(session_id)
        return {"status": "ok", "memos": memos}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@rest_router.post("/api/memos")
async def add_memo_endpoint(req: MemoRequest):
    from pipeline.domain.pm.nodes.memo_db import add_memo
    try:
        memo_id = add_memo(req.session_id, req.text, req.selected_text, req.section)
        return {"status": "ok", "memo_id": memo_id}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@rest_router.delete("/api/memos/{memo_id}")
async def delete_memo_endpoint(memo_id: str):
    from pipeline.domain.pm.nodes.memo_db import delete_memo
    try:
        delete_memo(memo_id)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
