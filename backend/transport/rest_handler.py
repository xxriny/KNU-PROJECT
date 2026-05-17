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

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordBearer
from auth.deps import get_current_user, get_current_user_optional
from auth.database import get_db
from sqlalchemy.orm import Session
from auth.models import User
from pydantic import BaseModel
from version import APP_VERSION, DEFAULT_MODEL
from observability.logger import get_logger
from pipeline.core.action_type import normalize_action_type
from pipeline.orchestration.facade import (
    get_analysis_pipeline,
    get_idea_pipeline,
    get_rag_ingest_pipeline,
)
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
    user_id: Optional[str] = None
    team_id: Optional[str] = None


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
    detail: str = ""


class MemoApplyRequest(BaseModel):
    memo_ids: list = []


class RAGIngestRequest(BaseModel):
    source_dir: str
    session_id: str
    version: str = "v1.0"


class RAGQueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    n_results: int = 10


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


def _compact_result_value(value, *, depth: int = 0):
    if depth > 4:
        return "<truncated>"
    if isinstance(value, str):
        return value if len(value) <= 4000 else value[:4000] + "\n<truncated>"
    if isinstance(value, list):
        return [_compact_result_value(item, depth=depth + 1) for item in value[:25]]
    if isinstance(value, dict):
        compact = {}
        for key, item in value.items():
            if key in {
                "content",
                "source",
                "raw",
                "stdout",
                "stderr",
                "stdout_tail",
                "stderr_tail",
                "prompt",
                "user_msg",
                "system_msg",
                "messages",
                "semantic_slices",
            }:
                compact[key] = _compact_result_value(item, depth=depth + 1)
            elif key in {"files", "generated_files"} and isinstance(item, list):
                compact[key] = [
                    {
                        sub_key: _compact_result_value(sub_value, depth=depth + 1)
                        for sub_key, sub_value in file_item.items()
                        if sub_key not in {"content", "source"}
                    }
                    for file_item in item[:50]
                    if isinstance(file_item, dict)
                ]
            else:
                compact[key] = _compact_result_value(item, depth=depth + 1)
        return compact
    return value


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


@rest_router.post("/api/rag/ingest")
async def rag_ingest(req: RAGIngestRequest):
    """소스 디렉터리를 청킹·임베딩하여 project_code_knowledge에 저장합니다."""
    if not req.source_dir or not os.path.isdir(req.source_dir):
        return {"status": "error", "error": f"유효하지 않은 source_dir: {req.source_dir}"}
    try:
        result = execute_pipeline(
            get_rag_ingest_pipeline(),
            {
                "source_dir": req.source_dir,
                "run_id": req.session_id,
                "api_key": "",
                "model": "",
            },
            "rag_ingest",
        )
        if not result.success:
            return {"status": "error", "error": result.error}
        ingest_output = result.data.get("rag_ingest_output", {})
        return {"status": "ok", **ingest_output}
    except Exception as e:
        get_logger().exception("rag_ingest endpoint failed")
        return {"status": "error", "error": str(e)}


@rest_router.post("/api/rag/query")
async def rag_query(req: RAGQueryRequest):
    """project_code_knowledge에서 유사 코드 청크를 검색합니다."""
    if not req.query.strip():
        return {"status": "error", "error": "query가 비어있습니다."}
    try:
        from pipeline.domain.rag.nodes.code_retriever import retrieve_project_code
        results = retrieve_project_code(req.query, session_id=req.session_id, n_results=req.n_results)
        return {"status": "ok", "results": results}
    except Exception as e:
        get_logger().exception("rag_query endpoint failed")
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
        from pipeline.domain.rag.nodes.project_db import delete_project_knowledge

        pm_deleted = delete_pm_knowledge(run_id)
        sa_deleted = delete_sa_knowledge(run_id)
        stack_deleted = delete_session_knowledge(run_id)
        project_deleted = delete_project_knowledge(run_id)

        return {
            "status": "ok",
            "message": f"Session {run_id} deleted from RAG",
            "pm_docs_deleted": pm_deleted,
            "sa_docs_deleted": sa_deleted,
            "stack_docs_deleted": stack_deleted,
            "project_docs_deleted": project_deleted,
        }
    except Exception as e:
        get_logger().exception(f"delete_session failed for run_id={run_id}")
        return {
            "status": "error",
            "error": str(e),
            "message": f"Partial deletion for {run_id}",
        }


@rest_router.get("/api/session/{run_id}/restore")
async def restore_session(run_id: str):
    """RAG DB에서 특정 세션의 모든 아티팩트를 수집하여 복원합니다."""
    try:
        from pipeline.domain.pm.nodes.pm_db import _get_collection
        coll = _get_collection()
        
        # 해당 세션의 모든 데이터 조회
        results = coll.get(where={"session_id": run_id})
        
        if not results["ids"]:
            return {"status": "error", "error": "해당 세션의 데이터를 찾을 수 없습니다."}
            
        # 데이터를 LangGraph Raw State처럼 조립
        raw_state = {
            "run_id": run_id,
            "metadata": {"session_id": run_id, "project_name": "Restored Project", "status": "Completed"}
        }
        
        for i in range(len(results["ids"])):
            artifact_type = results["metadatas"][i].get("artifact_type")
            doc_str = results["documents"][i]
            
            try:
                import json
                parsed_content = json.loads(doc_str)
            except:
                try:
                    import ast
                    parsed_content = ast.literal_eval(doc_str)
                except:
                    parsed_content = doc_str
                
            if artifact_type == "PM_BUNDLE":
                raw_state["pm_bundle"] = parsed_content
            elif artifact_type == "SA_ARCH_BUNDLE":
                raw_state["sa_advisor_output"] = parsed_content
                # Legacy 호환을 위해 sa_output으로도 저장
                raw_state["sa_output"] = parsed_content
            elif "API" in artifact_type.upper():
                raw_state["sa_unified_modeler_output"] = parsed_content
            elif "TABLE" in artifact_type.upper() or "DB" in artifact_type.upper():
                # 이미 SA_ARCH_BUNDLE이나 Unified에 포함되어 있을 확률이 높음
                if "sa_unified_modeler_output" not in raw_state:
                    raw_state["sa_unified_modeler_output"] = parsed_content
            elif artifact_type == "RTM_STACK_BUNDLE":
                raw_state["requirements_rtm"] = parsed_content

        # ── 핵심: 새로운 Shaper를 적용하여 UI용 데이터로 변환 ──
        from result_shaping.result_shaper import shape_result
        final_data = shape_result(raw_state)
        
        return {"status": "ok", "data": final_data}
        
    except Exception as e:
        get_logger().error(f"Restore failed: {e}")
        return {"status": "error", "error": str(e)}


@rest_router.get("/api/memos")
async def get_memos_endpoint(session_id: Optional[str] = None):
    from auth.database import get_db as _get_db
    from auth.models import MemoItem
    try:
        db = next(_get_db())
        q = db.query(MemoItem)
        if session_id:
            q = q.filter(MemoItem.session_id == session_id)
        items = q.order_by(MemoItem.created_at.asc()).all()
        memos = [
            {
                "id": m.id,
                "session_id": m.session_id,
                "text": m.text,
                "metadata": {
                    "selected_text": m.selected_text,
                    "section": m.section,
                    "detail": m.detail,
                    "applied": m.applied,
                    "applied_at": m.applied_at,
                },
            }
            for m in items
        ]
        return {"status": "ok", "memos": memos}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@rest_router.post("/api/memos")
async def add_memo_endpoint(req: MemoRequest):
    from auth.database import get_db as _get_db
    from auth.models import MemoItem
    try:
        db = next(_get_db())
        memo = MemoItem(
            session_id=req.session_id,
            text=req.text,
            selected_text=req.selected_text,
            section=req.section,
            detail=req.detail,
        )
        db.add(memo)
        db.commit()
        db.refresh(memo)
        return {"status": "ok", "memo_id": memo.id}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@rest_router.delete("/api/memos/{memo_id}")
async def delete_memo_endpoint(memo_id: str):
    from auth.database import get_db as _get_db
    from auth.models import MemoItem
    try:
        db = next(_get_db())
        memo = db.query(MemoItem).filter(MemoItem.id == memo_id).first()
        if memo:
            db.delete(memo)
            db.commit()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@rest_router.post("/api/memos/apply")
async def apply_memos_endpoint(req: MemoApplyRequest):
    from auth.database import get_db as _get_db
    from auth.models import MemoItem
    from datetime import datetime as _dt
    try:
        db = next(_get_db())
        ts = _dt.utcnow().isoformat()
        updated = (
            db.query(MemoItem)
            .filter(MemoItem.id.in_(req.memo_ids))
            .all()
        )
        for m in updated:
            m.applied = True
            m.applied_at = ts
        db.commit()
        return {"status": "ok", "updated": len(updated)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ── Agile Layer ───────────────────────────────────────────

class AgileVerifyRequest(BaseModel):
    sa_data: dict
    api_key: str = ""
    model: str = DEFAULT_MODEL
    use_llm: bool = True
    use_deep_llm: bool = False  # V-007~V-009 추가 LLM 검증


class AgileImpactRequest(BaseModel):
    change_description: str
    sa_data: dict
    api_key: str = ""
    model: str = DEFAULT_MODEL
    session_id: Optional[str] = None
    use_llm: bool = True


@rest_router.post("/api/agile/verify")
async def agile_verify(req: AgileVerifyRequest):
    """SA 결과물 일관성 검증 (V-001~V-009, 하이브리드)."""
    try:
        from pipeline.domain.agile.nodes.verifier import run_verifier
        result = run_verifier(
            sa_data=req.sa_data,
            api_key=req.api_key,
            model=req.model,
            use_llm=req.use_llm,
            use_deep_llm=req.use_deep_llm,
        )
        return {"status": "ok", "data": result.model_dump()}
    except Exception as e:
        get_logger().exception("agile_verify endpoint failed")
        return {"status": "error", "error": str(e)}


@rest_router.post("/api/agile/impact")
async def agile_impact(req: AgileImpactRequest):
    """변경 영향 분석 (RAG + LLM 2-stage)."""
    if not req.change_description.strip():
        return {"status": "error", "error": "change_description이 비어있습니다."}
    try:
        from pipeline.domain.agile.nodes.impact import run_impact_analyzer
        result = run_impact_analyzer(
            change_description=req.change_description,
            sa_data=req.sa_data,
            api_key=req.api_key,
            model=req.model,
            session_id=req.session_id,
            use_llm=req.use_llm,
        )
        return {"status": "ok", "data": result.model_dump()}
    except Exception as e:
        get_logger().exception("agile_impact endpoint failed")
        return {"status": "error", "error": str(e)}


# ── GitHub Integration ────────────────────────────────────

class GitHubVerifyRequest(BaseModel):
    token: str
    owner: str
    repo: str


class GitHubPublishRequest(BaseModel):
    token: Optional[str] = None  # 호환성 유지 (deprecated, JWT 우선)
    owner: str
    repo: str
    result_data: dict
    page_title: str = "SA 설계 문서"
    project_name: str = "Project"


class GitHubAnalyticsRequest(BaseModel):
    token: Optional[str] = None  # deprecated
    owner: str
    repo: str
    branch: str = "main"
    limit: int = 30


class GitHubIssuesRequest(BaseModel):
    token: Optional[str] = None  # deprecated
    owner: str
    repo: str
    state: str = "open"


@rest_router.post("/api/github/verify")
async def github_verify(req: GitHubVerifyRequest):
    """GitHub 토큰 + 레포지토리 접근 확인."""
    try:
        from connectors.github_connector import verify_token, GitHubConnector
        token_info = verify_token(req.token)
        if not token_info["valid"]:
            return {"status": "error", "error": token_info.get("error", "Invalid token")}
        connector = GitHubConnector(req.token)
        repo_obj = connector.get_repo(req.owner, req.repo)
        return {
            "status": "ok",
            "user": token_info["login"],
            "repo": repo_obj.full_name,
            "private": repo_obj.private,
            "default_branch": repo_obj.default_branch,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@rest_router.post("/api/github/publish")
async def github_publish(
    req: GitHubPublishRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """SA 설계 문서를 GitHub Issues(design-doc)에 퍼블리시."""
    # JWT로 인증한 사용자의 DB OAuth 토큰 우선, 없으면 body.token 폴백
    token = (current_user.github_oauth_token if current_user else None) or req.token
    if not token:
        return {"status": "error", "error": "GitHub OAuth 토큰이 없습니다. GitHub 연결 후 다시 시도하세요."}
    try:
        from pipeline.domain.agile.wiki_publisher import publish_to_github
        result = publish_to_github(
            result_data=req.result_data,
            owner=req.owner,
            repo=req.repo,
            token=token,
            page_title=req.page_title,
            project_name=req.project_name,
        )
        return {"status": "ok", **result}
    except Exception as e:
        get_logger().exception("github_publish endpoint failed")
        return {"status": "error", "error": str(e)}


@rest_router.post("/api/github/analytics")
async def github_analytics(
    req: GitHubAnalyticsRequest,
    current_user: User = Depends(get_current_user),
):
    """커밋 히스토리 분석."""
    token = (current_user.github_oauth_token if current_user else None) or req.token
    if not token:
        return {"status": "error", "error": "GitHub OAuth 토큰이 필요합니다."}
    try:
        from connectors.github_connector import GitHubConnector
        from pipeline.domain.agile.commit_analyzer import analyze_commits
        connector = GitHubConnector(token)
        commits = connector.get_commits(req.owner, req.repo, req.branch, req.limit)
        analytics = analyze_commits(commits)
        return {
            "status": "ok",
            "data": {
                "total_commits": analytics.total_commits,
                "by_author": analytics.by_author,
                "by_date": analytics.by_date,
                "top_keywords": analytics.top_keywords,
                "recent_commits": analytics.recent_commits,
                "activity_trend": analytics.activity_trend,
                "contributors": [
                    c.__dict__ for c in connector.get_contributors(req.owner, req.repo)
                ],
            },
        }
    except Exception as e:
        get_logger().exception("github_analytics endpoint failed")
        return {"status": "error", "error": str(e)}


@rest_router.post("/api/github/branches")
async def github_branches(
    req: GitHubAnalyticsRequest,
    current_user: User = Depends(get_current_user),
):
    """GitHub 브랜치 목록 조회."""
    token = (current_user.github_oauth_token if current_user else None) or req.token
    if not token:
        return {"status": "error", "error": "GitHub OAuth 토큰이 필요합니다."}
    try:
        from connectors.github_connector import GitHubConnector
        connector = GitHubConnector(token)
        branches = connector.list_branches(req.owner, req.repo)
        return {"status": "ok", "data": branches}
    except Exception as e:
        get_logger().exception("github_branches endpoint failed")
        return {"status": "error", "error": str(e)}


@rest_router.post("/api/github/issues")
async def github_issues(
    req: GitHubIssuesRequest,
    current_user: User = Depends(get_current_user),
):
    """GitHub Issues 목록 조회."""
    token = (current_user.github_oauth_token if current_user else None) or req.token
    if not token:
        return {"status": "error", "error": "GitHub OAuth 토큰이 필요합니다."}
    try:
        from connectors.github_connector import GitHubConnector
        connector = GitHubConnector(token)
        issues = connector.get_issues(req.owner, req.repo, req.state)
        return {"status": "ok", "data": [i.__dict__ for i in issues]}
    except Exception as e:
        get_logger().exception("github_issues endpoint failed")
        return {"status": "error", "error": str(e)}


# ── Phase 5: Task Coordinator + Doc Sync ────────────────────

class TaskCreateRequest(BaseModel):
    task_type: str
    title: str
    description: str = ""
    area: str = ""       # backend | frontend | fullstack | devops
    assignee: str = ""
    payload: dict = {}
    created_by: str = ""
    team_id: str = ""


class TaskUpdateRequest(BaseModel):
    status: str
    reviewed_by: str = ""
    result: str = ""


class DocSyncRequest(BaseModel):
    result_data: dict
    github_token: str
    owner: str
    repo: str
    previous_hash: str = ""
    page_title: str = "SA 설계 문서"
    project_name: str = "Project"


class GitHubIssuesImportRequest(BaseModel):
    token: str
    owner: str
    repo: str
    api_key: str = ""
    model: str = DEFAULT_MODEL


@rest_router.post("/api/tasks")
async def create_task_endpoint(req: TaskCreateRequest):
    """새 태스크 생성 (PM 승인 대기)."""
    try:
        from pipeline.domain.agile.task_coordinator import create_task, init_tasks_db
        init_tasks_db()
        task = create_task(
            task_type=req.task_type,
            title=req.title,
            description=req.description,
            area=req.area,
            assignee=req.assignee,
            payload=req.payload,
            created_by=req.created_by,
            team_id=req.team_id,
        )
        return {"status": "ok", "data": task}
    except Exception as e:
        get_logger().exception("create_task endpoint failed")
        return {"status": "error", "error": str(e)}


@rest_router.get("/api/tasks")
async def list_tasks_endpoint(status: Optional[str] = None, team_id: Optional[str] = None):
    """태스크 목록 조회."""
    try:
        from pipeline.domain.agile.task_coordinator import list_tasks, init_tasks_db
        init_tasks_db()
        tasks = list_tasks(status=status, team_id=team_id or None)
        return {"status": "ok", "data": tasks}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@rest_router.patch("/api/tasks/{task_id}")
async def update_task_endpoint(task_id: str, req: TaskUpdateRequest):
    """태스크 상태 업데이트 (승인/거절/완료)."""
    allowed_statuses = {"pending", "approved", "rejected", "completed", "failed"}
    if req.status not in allowed_statuses:
        return {"status": "error", "error": f"Invalid status. Allowed: {allowed_statuses}"}
    try:
        from pipeline.domain.agile.task_coordinator import update_task_status, get_task, execute_approved_task, init_tasks_db
        init_tasks_db()
        task = update_task_status(task_id, req.status, req.reviewed_by, req.result)
        if not task:
            return {"status": "error", "error": "Task not found"}

        # 승인 시 자동 실행
        if req.status == "approved":
            exec_result = execute_approved_task(task)
            update_task_status(task_id, "completed", result=exec_result)
            task["status"] = "completed"
            task["result"] = exec_result

        return {"status": "ok", "data": task}
    except Exception as e:
        get_logger().exception(f"update_task endpoint failed for {task_id}")
        return {"status": "error", "error": str(e)}


@rest_router.delete("/api/tasks/{task_id}")
async def delete_task_endpoint(task_id: str):
    """완료/거절된 태스크 삭제."""
    try:
        from pipeline.domain.agile.task_coordinator import delete_task, init_tasks_db
        init_tasks_db()
        deleted = delete_task(task_id)
        if not deleted:
            return {"status": "error", "error": "Task not found"}
        return {"status": "ok"}
    except Exception as e:
        get_logger().exception(f"delete_task endpoint failed for {task_id}")
        return {"status": "error", "error": str(e)}


@rest_router.post("/api/doc-sync")
async def doc_sync_endpoint(req: DocSyncRequest):
    """SA 결과물을 GitHub에 자동 동기화."""
    try:
        from pipeline.domain.agile.nodes.doc_sync import sync_docs
        result = sync_docs(
            result_data=req.result_data,
            github_token=req.github_token,
            owner=req.owner,
            repo=req.repo,
            previous_hash=req.previous_hash,
            page_title=req.page_title,
            project_name=req.project_name,
        )
        return {"status": "ok", "data": result}
    except Exception as e:
        get_logger().exception("doc_sync endpoint failed")
        return {"status": "error", "error": str(e)}


# ── Publish / Shared Snapshots ────────────────────────────────

class PublishRequest(BaseModel):
    run_id: str
    title: str
    description: str = ""
    team_id: Optional[str] = None


@rest_router.get("/api/local-results")
async def list_local_results_endpoint(
    limit: int = 50,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Publish 대상 선택을 위한 로컬 분석 결과 목록."""
    try:
        from storage.publish_service import list_local_results
        return {"status": "ok", "data": list_local_results(db, limit=limit)}
    except Exception as e:
        get_logger().exception("list_local_results failed")
        return {"status": "error", "error": str(e)}


@rest_router.post("/api/publish")
async def publish_snapshot_endpoint(
    req: PublishRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """로컬 분석 결과를 공유 DB에 Publish."""
    try:
        from storage.publish_service import publish_snapshot
        team_id = req.team_id or (current_user.team_id if current_user else None)
        user_id = current_user.id if current_user else None
        snap = publish_snapshot(
            db,
            run_id=req.run_id,
            title=req.title,
            description=req.description,
            team_id=team_id,
            user_id=user_id,
        )
        return {"status": "ok", "data": snap}
    except ValueError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        get_logger().exception("publish_snapshot failed")
        return {"status": "error", "error": str(e)}


@rest_router.get("/api/snapshots")
async def list_snapshots_endpoint(
    team_id: Optional[str] = None,
    limit: int = 30,
    offset: int = 0,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """팀 공유 스냅샷 목록."""
    try:
        from storage.publish_service import list_snapshots
        resolved_team = team_id or (current_user.team_id if current_user else None)
        snaps = list_snapshots(db, team_id=resolved_team, limit=limit, offset=offset)
        return {"status": "ok", "data": snaps}
    except Exception as e:
        get_logger().exception("list_snapshots failed")
        return {"status": "error", "error": str(e)}


@rest_router.get("/api/snapshots/{snapshot_id}")
async def get_snapshot_endpoint(
    snapshot_id: str,
    db: Session = Depends(get_db),
):
    """스냅샷 상세 조회 (데이터 포함)."""
    try:
        from storage.publish_service import get_snapshot
        snap = get_snapshot(db, snapshot_id)
        if not snap:
            return {"status": "error", "error": "스냅샷을 찾을 수 없습니다."}
        return {"status": "ok", "data": snap}
    except Exception as e:
        get_logger().exception("get_snapshot failed")
        return {"status": "error", "error": str(e)}


@rest_router.delete("/api/snapshots/{snapshot_id}")
async def delete_snapshot_endpoint(
    snapshot_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """스냅샷 삭제 (게시자 본인 또는 PM만)."""
    try:
        from storage.publish_service import get_snapshot, delete_snapshot
        snap = get_snapshot(db, snapshot_id)
        if not snap:
            return {"status": "error", "error": "스냅샷을 찾을 수 없습니다."}
        if current_user:
            is_owner = snap["published_by"] == current_user.id
            is_pm = current_user.role == "pm"
            if not (is_owner or is_pm):
                return {"status": "error", "error": "삭제 권한이 없습니다."}
        delete_snapshot(db, snapshot_id)
        return {"status": "ok"}
    except Exception as e:
        get_logger().exception("delete_snapshot failed")
        return {"status": "error", "error": str(e)}


class PullRequest(BaseModel):
    run_id: str


@rest_router.post("/api/snapshots/{snapshot_id}/pull")
async def pull_snapshot_endpoint(
    snapshot_id: str,
    req: PullRequest,
    db: Session = Depends(get_db),
):
    """공유 스냅샷 데이터를 지정된 로컬 run_id 세션에 덮어써 저장(Pull)."""
    try:
        from storage.publish_service import pull_snapshot
        result = pull_snapshot(db, snapshot_id=snapshot_id, run_id=req.run_id)
        return {"status": "ok", "data": result}
    except ValueError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        get_logger().exception("pull_snapshot failed")
        return {"status": "error", "error": str(e)}



@rest_router.post("/api/github/issues/import")
async def github_issues_import(req: GitHubIssuesImportRequest):
    """GitHub Issues를 requirements로 변환하는 태스크 생성."""
    try:
        from connectors.github_connector import GitHubConnector
        from pipeline.domain.agile.task_coordinator import create_task, init_tasks_db
        init_tasks_db()
        connector = GitHubConnector(req.token)
        issues = connector.get_issues(req.owner, req.repo, state="open")
        issue_list = [i.__dict__ for i in issues]

        task = create_task(
            task_type="import_issues",
            title=f"GitHub Issues Import ({req.owner}/{req.repo})",
            description=f"{len(issue_list)}개 이슈를 요구사항으로 변환",
            payload={
                "issues": issue_list,
                "owner": req.owner,
                "repo": req.repo,
                "api_key": req.api_key,
            },
        )
        return {
            "status": "ok",
            "task_id": task["id"],
            "issue_count": len(issue_list),
            "message": "태스크가 생성되었습니다. PM 승인 후 실행됩니다.",
        }
    except Exception as e:
        get_logger().exception("github_issues_import endpoint failed")
        return {"status": "error", "error": str(e)}
