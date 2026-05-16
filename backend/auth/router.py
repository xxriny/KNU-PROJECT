"""
RBAC 인증 라우터: /auth/*
동적 OAuth 구성 및 팀별 설정을 지원합니다.
"""

from __future__ import annotations

import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from auth.database import get_db
from auth.models import User, Team, DesignChangeRequest
from auth.schemas import (
    RegisterRequest, LoginRequest, TeamUpdateRequest, TeamNameUpdateRequest,
    ChangeRequestCreate, ChangeRequestUpdate, DevicePollRequest,
)
from auth.service import (
    authenticate_user, create_user, build_user_response,
    create_access_token, count_users, get_user_by_email,
    start_github_device_flow, poll_github_device_token,
    get_github_user_info, create_or_update_github_user,
)
from auth.deps import get_current_user, require_pm, require_engineer, get_current_user_optional
from auth.oauth_config import get_github_credentials

auth_router = APIRouter()


# ── 인증 ─────────────────────────────────────────────────────

@auth_router.get("/auth/status")
async def auth_status(db: Session = Depends(get_db)):
    """앱 최초 실행 여부 체크."""
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


# ── GitHub OAuth Device Flow (Dynamic) ───────────────────────

@auth_router.post("/auth/github/device-start")
async def github_device_start(db: Session = Depends(get_db)):
    """GitHub Device Flow 시작. DB 설정을 우선적으로 사용합니다."""
    from auth.oauth_config import get_github_credentials
    client_id, _ = get_github_credentials(db)
    
    # 미설정이거나 더미 값이 들어있는 경우 설정창 유도
    if not client_id or "your_" in client_id.lower() or "YOUR_" in client_id:
        raise HTTPException(
            status_code=503,
            detail="needs_oauth_setup",
        )
    try:
        data = start_github_device_flow(client_id)
        if "error" in data:
            raise HTTPException(status_code=400, detail=data.get("error_description", data["error"]))
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GitHub 인증 시작 실패: {e}")


@auth_router.post("/auth/github/device-poll")
async def github_device_poll(req: DevicePollRequest, db: Session = Depends(get_db)):
    """GitHub Device Flow 폴링 및 로그인 완료."""
    client_id, client_secret = get_github_credentials(db)
    
    if not client_id:
        raise HTTPException(status_code=503, detail="GitHub OAuth 구성 오류")

    try:
        token_data = poll_github_device_token(client_id, client_secret, req.device_code)
        error = token_data.get("error")
        if error in ("authorization_pending", "slow_down"):
            return {"status": "pending", "error": error}
        if error:
            return {"status": "error", "error": token_data.get("error_description", error)}

        access_token = token_data.get("access_token")
        if not access_token:
            return {"status": "error", "error": "토큰을 받지 못했습니다."}

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
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GitHub 인증 실패: {e}")


@auth_router.post("/auth/github/disconnect")
async def github_disconnect(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.github_id = None
    current_user.github_login = None
    current_user.github_oauth_token = None
    db.commit()
    return {"status": "ok"}


@auth_router.get("/auth/github/repos")
async def list_github_repos(current_user: User = Depends(get_current_user)):
    """현재 로그인한 GitHub 사용자의 레포 목록 반환."""
    if not current_user.github_oauth_token:
        raise HTTPException(status_code=400, detail="GitHub 연결이 필요합니다.")
    try:
        from githubkit import GitHub
        repos = []
        page = 1
        with GitHub(current_user.github_oauth_token) as gh:
            while True:
                resp = gh.rest.repos.list_for_authenticated_user(
                    sort="updated", per_page=100, page=page
                )
                batch = resp.parsed_data
                if not batch:
                    break
                for r in batch:
                    repos.append({
                        "full_name": r.full_name,
                        "name": r.name,
                        "owner": r.owner.login,
                        "description": getattr(r, "description", "") or "",
                        "private": r.private,
                        "language": getattr(r, "language", "") or "",
                        "pushed_at": str(getattr(r, "pushed_at", "") or ""),
                    })
                if len(batch) < 100:
                    break
                page += 1
        return {"status": "ok", "repos": repos}
    except Exception as e:
        return {"status": "scope_error", "error": str(e)}


class OauthSetupRequest(BaseModel):
    client_id: str
    client_secret: str

@auth_router.post("/auth/setup-oauth")
async def setup_initial_oauth(req: OauthSetupRequest, db: Session = Depends(get_db)):
    """최초 실행 시 로그인을 위한 OAuth 설정 엔드포인트"""
    if count_users(db) > 0:
        raise HTTPException(status_code=403, detail="이미 시스템이 초기화되었습니다. 설정 패널을 이용하세요.")
    
    team = db.query(Team).first()
    if not team:
        team = Team(name="Default Team")
        db.add(team)
        db.flush()
    
    team.github_client_id = req.client_id
    team.github_client_secret = req.client_secret
    db.commit()
    
    return {"status": "ok", "message": "초기 OAuth 설정이 완료되었습니다."}


# ── 팀 및 인증 설정 관리 ──────────────────────────────────────────

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
            "github_client_id": team.github_client_id,
            "has_github_token": bool(team.github_token),
            "has_oauth_config": bool(team.github_client_id and team.github_client_secret),
        }
    }


class TeamOAuthConfigUpdate(BaseModel):
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    github_repo: Optional[str] = None
    github_token: Optional[str] = None

@auth_router.patch("/api/teams/me/github")
async def update_team_github_config(
    req: TeamOAuthConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """팀의 GitHub OAuth 및 저장소 설정을 업데이트합니다."""
    if not current_user.team_id:
        raise HTTPException(status_code=404, detail="팀 정보를 찾을 수 없습니다.")
    
    team = db.query(Team).filter(Team.id == current_user.team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="팀을 찾을 수 없습니다.")
    
    if req.client_id is not None: team.github_client_id = req.client_id
    if req.client_secret is not None: team.github_client_secret = req.client_secret
    if req.github_repo is not None: team.github_repo = req.github_repo
    if req.github_token is not None: team.github_token = req.github_token
    
    db.commit()
    return {"status": "ok", "message": "GitHub 구성이 업데이트되었습니다."}


class TeamNameUpdate(BaseModel):
    name: str

@auth_router.patch("/api/teams/me")
async def update_team_name(
    req: TeamNameUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.team_id:
        raise HTTPException(status_code=404, detail="팀 정보를 찾을 수 없습니다.")
    team = db.query(Team).filter(Team.id == current_user.team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="팀을 찾을 수 없습니다.")
    team.name = req.name.strip()
    db.commit()
    return {"status": "ok"}


@auth_router.get("/api/teams/me/members")
async def get_team_members(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.team_id:
        return {"members": []}
    members = db.query(User).filter(User.team_id == current_user.team_id).all()
    return {
        "members": [
            {
                "id": m.id,
                "name": m.name,
                "email": m.email,
                "role": m.role,
                "github_login": m.github_login,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in members
        ]
    }


class UserRoleUpdate(BaseModel):
    role: str

@auth_router.patch("/api/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    req: UserRoleUpdate,
    current_user: User = Depends(require_pm),
    db: Session = Depends(get_db),
):
    if req.role not in ("pm", "engineer", "viewer"):
        raise HTTPException(status_code=400, detail="유효하지 않은 역할입니다. pm / engineer / viewer 중 선택하세요.")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    if target.team_id != current_user.team_id:
        raise HTTPException(status_code=403, detail="같은 팀원의 권한만 변경할 수 있습니다.")
    target.role = req.role
    db.commit()
    return {"status": "ok", "user_id": user_id, "role": req.role}


# ── 설계 변경 요청 (Agile) ─────────────────────────────────────

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
