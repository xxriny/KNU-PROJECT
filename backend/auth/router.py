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

import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth.database import get_db
from auth.models import User, Team, DesignChangeRequest
from auth.schemas import (
    RegisterRequest, LoginRequest, TeamUpdateRequest,
    ChangeRequestCreate, ChangeRequestUpdate, DevicePollRequest,
)
from auth.service import (
    authenticate_user, create_user, build_user_response,
    create_access_token, count_users, get_user_by_email,
    start_github_device_flow, poll_github_device_token,
    get_github_user_info, create_or_update_github_user,
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


# ── GitHub OAuth Device Flow ─────────────────────────────────

@auth_router.post("/auth/github/device-start")
async def github_device_start():
    """GitHub Device Flow 시작. user_code와 verification_uri를 반환."""
    client_id = os.environ.get("GITHUB_OAUTH_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(
            status_code=503,
            detail="GitHub OAuth가 설정되지 않았습니다. GITHUB_OAUTH_CLIENT_ID 환경변수를 설정하세요.",
        )
    try:
        data = start_github_device_flow(client_id)
        if "error" in data:
            raise HTTPException(status_code=400, detail=data.get("error_description", data["error"]))
        return {
            "user_code": data["user_code"],
            "verification_uri": data.get("verification_uri", "https://github.com/login/device"),
            "device_code": data["device_code"],
            "expires_in": data.get("expires_in", 900),
            "interval": data.get("interval", 5),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GitHub 인증 시작 실패: {e}")


@auth_router.post("/auth/github/device-poll")
async def github_device_poll(req: DevicePollRequest, db: Session = Depends(get_db)):
    """GitHub Device Flow 폴링. 사용자가 승인하면 JWT + github_token 반환."""
    client_id = os.environ.get("GITHUB_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("GITHUB_OAUTH_CLIENT_SECRET", "")
    if not client_id:
        raise HTTPException(status_code=503, detail="GitHub OAuth 미설정")
    try:
        token_data = poll_github_device_token(client_id, client_secret, req.device_code)
        error = token_data.get("error")
        if error in ("authorization_pending", "slow_down"):
            return {"status": "pending", "error": error}
        if error:
            return {"status": "error", "error": token_data.get("error_description", error)}

        access_token = token_data.get("access_token")
        if not access_token:
            return {"status": "error", "error": "토큰 없음"}

        gh_info = get_github_user_info(access_token)
        user = create_or_update_github_user(
            db,
            github_id=gh_info["id"],
            github_login=gh_info["login"],
            email=gh_info["email"],
            name=gh_info["name"],
            oauth_token=access_token,
        )
        jwt_token = create_access_token(user.id, user.email, user.role)
        return {
            "status": "ok",
            "access_token": jwt_token,
            "token_type": "bearer",
            "user": build_user_response(user),
            "github_token": access_token,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GitHub 인증 폴링 실패: {e}")


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
