"""
RBAC 인증 라우터: /auth/*
POST /auth/register  — 회원가입
POST /auth/login     — 로그인 → JWT
GET  /auth/me        — 현재 사용자 정보
GET  /auth/status    — 사용자 존재 여부 (첫 실행 체크)

팀 관리:
GET  /api/teams/me       — 내 팀 정보
PATCH /api/teams/me/github — GitHub 연동 설정

설계 변경 요청:
POST  /api/change-requests        — 요청 제출
GET   /api/change-requests        — 목록 조회
PATCH /api/change-requests/{id}   — 승인/거절
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth.database import get_db
from auth.models import User, Team, DesignChangeRequest
from auth.schemas import (
    RegisterRequest, LoginRequest, TeamUpdateRequest,
    ChangeRequestCreate, ChangeRequestUpdate,
)
from auth.service import (
    authenticate_user, create_user, build_user_response,
    create_access_token, count_users, get_user_by_email,
)
from auth.deps import get_current_user, require_pm, require_engineer, get_current_user_optional

auth_router = APIRouter()


# ── 인증 ─────────────────────────────────────────────────────

@auth_router.get("/auth/status")
async def auth_status(db: Session = Depends(get_db)):
    """앱 최초 실행 여부 체크. 사용자가 없으면 회원가입 화면 표시."""
    total = count_users(db)
    return {"has_users": total > 0, "user_count": total}


@auth_router.post("/auth/register")
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if get_user_by_email(db, req.email):
        raise HTTPException(status_code=409, detail="이미 등록된 이메일입니다.")
    try:
        user = create_user(
            db,
            name=req.name,
            email=req.email,
            password=req.password,
            role=req.role,
            github_username=req.github_username,
            team_name=req.team_name,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    token = create_access_token(user.id, user.email, user.role)
    return {"access_token": token, "token_type": "bearer", "user": build_user_response(user)}


@auth_router.post("/auth/login")
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, req.email, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
    token = create_access_token(user.id, user.email, user.role)
    return {"access_token": token, "token_type": "bearer", "user": build_user_response(user)}


@auth_router.get("/auth/me")
async def me(current_user: User = Depends(get_current_user)):
    return build_user_response(current_user)


# ── 팀 관리 ──────────────────────────────────────────────────

@auth_router.get("/api/teams/me")
async def get_my_team(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.team_id:
        return {"team": None}
    team = db.query(Team).filter(Team.id == current_user.team_id).first()
    if not team:
        return {"team": None}
    return {
        "team": {
            "id": team.id,
            "name": team.name,
            "github_repo": team.github_repo,
            "has_github_token": bool(team.github_token),
        }
    }


@auth_router.patch("/api/teams/me/github")
async def update_team_github(
    req: TeamUpdateRequest,
    current_user: User = Depends(require_pm),
    db: Session = Depends(get_db),
):
    if not current_user.team_id:
        raise HTTPException(status_code=404, detail="팀이 없습니다.")
    team = db.query(Team).filter(Team.id == current_user.team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="팀을 찾을 수 없습니다.")
    if req.github_repo is not None:
        team.github_repo = req.github_repo
    if req.github_token is not None:
        team.github_token = req.github_token
    db.commit()
    return {"status": "ok", "github_repo": team.github_repo}


# ── 설계 변경 요청 ─────────────────────────────────────────────

@auth_router.post("/api/change-requests")
async def create_change_request(
    req: ChangeRequestCreate,
    current_user: User = Depends(require_engineer),
    db: Session = Depends(get_db),
):
    cr = DesignChangeRequest(
        session_id=req.session_id,
        requested_by=current_user.id,
        target_section=req.target_section,
        description=req.description,
        status="pending",
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)
    return {
        "status": "ok",
        "id": cr.id,
        "description": cr.description,
        "request_status": cr.status,
    }


@auth_router.get("/api/change-requests")
async def list_change_requests(
    session_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(DesignChangeRequest)
    if session_id:
        q = q.filter(DesignChangeRequest.session_id == session_id)
    items = q.order_by(DesignChangeRequest.created_at.desc()).limit(50).all()
    return {
        "status": "ok",
        "items": [
            {
                "id": it.id,
                "session_id": it.session_id,
                "target_section": it.target_section,
                "description": it.description,
                "status": it.status,
                "created_at": str(it.created_at),
            }
            for it in items
        ],
    }


@auth_router.patch("/api/change-requests/{cr_id}")
async def update_change_request(
    cr_id: str,
    req: ChangeRequestUpdate,
    current_user: User = Depends(require_pm),
    db: Session = Depends(get_db),
):
    cr = db.query(DesignChangeRequest).filter(DesignChangeRequest.id == cr_id).first()
    if not cr:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다.")
    if req.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="status는 approved 또는 rejected여야 합니다.")
    cr.status = req.status
    cr.approved_by = current_user.id
    db.commit()
    return {"status": "ok", "new_status": cr.status}
