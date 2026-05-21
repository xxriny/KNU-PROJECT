"""
team_router — /api/teams/* /api/users/* 엔드포인트.

팀 정보 조회/수정, 팀원 목록, 역할 변경을 담당합니다.
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from auth.database import get_db, get_shared_db
from auth.shared_models import User, Team, Subscription
from auth.deps import get_current_user, require_pm
from auth.service import build_user_response

team_router = APIRouter()


# ── 팀 조회 / 수정 ───────────────────────────────────────────

@team_router.get("/api/teams/me")
async def get_my_team(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_shared_db),
):
    if not current_user.team_id:
        return {"team": None}
    team = db.query(Team).filter(Team.id == current_user.team_id).first()
    if not team:
        return {"team": None}
    sub = db.query(Subscription).filter(Subscription.team_id == team.id).first()
    return {
        "team": {
            "id": team.id,
            "name": team.name,
            "github_repo": team.github_repo,
            "github_client_id": team.github_client_id,
            "has_github_token": bool(team.github_token),
            "has_oauth_config": bool(team.github_client_id and team.github_client_secret),
            "plan": sub.plan if sub else "free",
            "subscription_status": sub.status if sub else "active",
        }
    }


class TeamOAuthConfigUpdate(BaseModel):
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    github_repo: Optional[str] = None
    github_token: Optional[str] = None


@team_router.patch("/api/teams/me/github")
async def update_team_github_config(
    req: TeamOAuthConfigUpdate,
    current_user: User = Depends(require_pm),
    db: Session = Depends(get_shared_db),
):
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


@team_router.patch("/api/teams/me")
async def update_team_name(
    req: TeamNameUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_shared_db),
):
    if not current_user.team_id:
        raise HTTPException(status_code=404, detail="팀 정보를 찾을 수 없습니다.")
    team = db.query(Team).filter(Team.id == current_user.team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="팀을 찾을 수 없습니다.")
    team.name = req.name.strip()
    db.commit()
    return {"status": "ok"}


# ── 팀원 목록 ────────────────────────────────────────────────

@team_router.get("/api/teams/me/members")
async def get_team_members(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_shared_db),
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


# ── 역할 변경 ────────────────────────────────────────────────

class UserRoleUpdate(BaseModel):
    role: str


@team_router.patch("/api/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    req: UserRoleUpdate,
    current_user: User = Depends(require_pm),
    db: Session = Depends(get_shared_db),
):
    if req.role not in ("pm", "software_engineer", "backend", "frontend", "devops"):
        raise HTTPException(status_code=400, detail="유효하지 않은 역할입니다.")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    if target.team_id != current_user.team_id:
        raise HTTPException(status_code=403, detail="같은 팀원의 권한만 변경할 수 있습니다.")
    target.role = req.role
    db.commit()
    return {"status": "ok", "user_id": user_id, "role": req.role}


# ── 팀 생성 (로그인 후 팀 없는 사용자용) ───────────────────────

class TeamCreateRequest(BaseModel):
    name: str


from auth.shared_models import TeamMember

@team_router.post("/api/teams")
async def create_team(
    req: TeamCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_shared_db),
):
    """새 팀을 생성합니다. 생성자는 자동으로 PM 역할을 받습니다."""
    team = Team(name=req.name.strip())
    db.add(team)
    db.flush()

    # N:M 관계 (team_members) 추가
    tm = TeamMember(user_id=current_user.id, team_id=team.id, role="pm")
    db.add(tm)

    # 활성 팀 문맥 전환
    current_user.team_id = team.id
    current_user.role = "pm"

    # 무료 플랜 자동 적용
    sub = Subscription(team_id=team.id, plan="free", status="active")
    db.add(sub)
    db.commit()
    db.refresh(current_user)

    return {
        "status": "ok",
        "user": build_user_response(current_user, plan="free"),
        "team": {"id": team.id, "name": team.name},
    }


# ── 다중 팀 조회 및 전환 (N:M) ───────────────────────────────

@team_router.get("/api/users/me/teams")
async def list_my_teams(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_shared_db),
):
    """사용자가 소속된 모든 팀 목록을 반환합니다."""
    memberships = db.query(TeamMember).filter(TeamMember.user_id == current_user.id).all()
    teams_data = []
    for tm in memberships:
        t = db.query(Team).filter(Team.id == tm.team_id).first()
        if t:
            teams_data.append({
                "id": t.id,
                "name": t.name,
                "role": tm.role,
                "is_active": (t.id == current_user.team_id)
            })
    return {"teams": teams_data}


class SwitchTeamRequest(BaseModel):
    team_id: str


@team_router.post("/api/users/me/teams/switch")
async def switch_active_team(
    req: SwitchTeamRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_shared_db),
):
    """현재 활성화된 팀을 변경합니다."""
    tm = db.query(TeamMember).filter(
        TeamMember.user_id == current_user.id,
        TeamMember.team_id == req.team_id
    ).first()
    
    if not tm:
        raise HTTPException(status_code=403, detail="해당 팀의 멤버가 아닙니다.")
        
    current_user.team_id = tm.team_id
    current_user.role = tm.role
    db.commit()
    db.refresh(current_user)
    
    # 플랜 조회 필요
    from auth.router import _get_plan
    plan = _get_plan(db, current_user.team_id)
    
    return {
        "status": "ok",
        "user": build_user_response(current_user, plan=plan)
    }

