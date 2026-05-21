"""
/auth/* 라우터 — 사용자·팀 관리, JWT 발급, GitHub OAuth.
"""

from __future__ import annotations

import os
import secrets
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional

import bcrypt as _bcrypt
import httpx
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import get_db
from models import Team, User, Subscription
from schemas import (
    LoginRequest, RegisterRequest, TokenResponse, UserResponse,
    TeamResponse, TeamCreateRequest, TeamUpdateRequest, DevicePollRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# ── JWT 설정 ────────────────────────────────────────────────

_SECRET_KEY = os.environ.get("JWT_SECRET", "navigator-server-dev-secret-change-in-prod")
_ALGORITHM  = "HS256"
_TOKEN_DAYS = 7


def _make_token(user_id: str, email: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(days=_TOKEN_DAYS)
    return jwt.encode(
        {"sub": user_id, "email": email, "role": role, "exp": expire},
        _SECRET_KEY, algorithm=_ALGORITHM,
    )


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
    except JWTError:
        return None


# ── 비밀번호 ─────────────────────────────────────────────────

def _hash(pw: str) -> str:
    return _bcrypt.hashpw(pw.encode(), _bcrypt.gensalt(12)).decode()


def _verify(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ── 공통 의존성 ───────────────────────────────────────────────

def _token_from_header(authorization: Optional[str] = Header(default=None)) -> Optional[str]:
    if not authorization:
        return None
    parts = authorization.split()
    return parts[1] if len(parts) == 2 and parts[0].lower() == "bearer" else None


def get_current_user(
    token: Optional[str] = Depends(_token_from_header),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_token(token or "")
    if not payload:
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다.")
    return user


# ── 팀 플랜 조회 헬퍼 ─────────────────────────────────────────

def _team_plan(db: Session, team_id: Optional[str]) -> str:
    if not team_id:
        return "free"
    sub = db.query(Subscription).filter(Subscription.team_id == team_id).first()
    return sub.plan if sub else "free"


def _build_user_response(db: Session, user: User) -> UserResponse:
    team_name = user.team.name if user.team else None
    plan = _team_plan(db, user.team_id)
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        github_username=user.github_username,
        team_id=user.team_id,
        team_name=team_name,
        plan=plan,
    )


# ── 엔드포인트 ───────────────────────────────────────────────

@router.get("/status")
async def auth_status(db: Session = Depends(get_db)):
    """앱 최초 실행 여부 체크."""
    count = db.query(User).count()
    return {"has_users": count > 0, "user_count": count}


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=409, detail="이미 등록된 이메일입니다.")

    # 팀 처리
    team: Optional[Team] = None
    if req.team_name:
        team = db.query(Team).filter(Team.name == req.team_name).first()
        if not team:
            team = Team(name=req.team_name)
            db.add(team)
            db.flush()
            # 팀 생성 시 free 구독 자동 생성
            db.add(Subscription(team_id=team.id, plan="free", status="active"))

    user = User(
        name=req.name,
        email=req.email,
        password_hash=_hash(req.password),
        role=req.role,
        github_username=req.github_username,
        team_id=team.id if team else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = _make_token(user.id, user.email, user.role)
    return TokenResponse(token_type="bearer", access_token=token, user=_build_user_response(db, user))


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not _verify(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
    token = _make_token(user.id, user.email, user.role)
    return TokenResponse(token_type="bearer", access_token=token, user=_build_user_response(db, user))


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _build_user_response(db, user)


# ── 팀 CRUD ─────────────────────────────────────────────────

@router.post("/teams", response_model=TeamResponse)
async def create_team(
    req: TeamCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if db.query(Team).filter(Team.name == req.name).first():
        raise HTTPException(status_code=409, detail="이미 존재하는 팀 이름입니다.")
    team = Team(name=req.name)
    db.add(team)
    db.flush()
    db.add(Subscription(team_id=team.id, plan="free", status="active"))
    user.team_id = team.id
    db.commit()
    db.refresh(team)
    return TeamResponse(id=team.id, name=team.name, plan="free")


@router.get("/teams/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.team_id != team_id:
        raise HTTPException(status_code=403, detail="해당 팀에 접근 권한이 없습니다.")
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="팀을 찾을 수 없습니다.")
    plan = _team_plan(db, team_id)
    return TeamResponse(id=team.id, name=team.name, github_repo=team.github_repo, plan=plan)


@router.patch("/teams/{team_id}")
async def update_team(
    team_id: str,
    req: TeamUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role != "pm":
        raise HTTPException(status_code=403, detail="PM 권한이 필요합니다.")
    if user.team_id != team_id:
        raise HTTPException(status_code=403, detail="자신의 팀만 수정할 수 있습니다.")
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="팀을 찾을 수 없습니다.")
    if req.github_repo is not None:
        team.github_repo = req.github_repo
    if req.github_token is not None:
        team.github_token = req.github_token
    if req.github_client_id is not None:
        team.github_client_id = req.github_client_id
    if req.github_client_secret is not None:
        team.github_client_secret = req.github_client_secret
    db.commit()
    return {"status": "ok"}


@router.get("/teams/{team_id}/members")
async def list_members(
    team_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.team_id != team_id:
        raise HTTPException(status_code=403, detail="해당 팀에 접근 권한이 없습니다.")
    members = db.query(User).filter(User.team_id == team_id).all()
    return {"members": [
        {"id": u.id, "name": u.name, "email": u.email, "role": u.role}
        for u in members
    ]}


# ── GitHub OAuth Device Flow ──────────────────────────────────

_DEVICE_SCOPE = "repo user:email read:user read:org workflow"

_oauth_sessions: dict = {}


@router.post("/github/device/start")
async def github_device_start(db: Session = Depends(get_db)):
    client_id = os.environ.get("GITHUB_CLIENT_ID", "")
    if not client_id:
        raise HTTPException(status_code=503, detail="GitHub Client ID가 설정되지 않았습니다.")
    payload = {"client_id": client_id, "scope": _DEVICE_SCOPE}
    headers = {"Accept": "application/json", "User-Agent": "Navigator-Server/1.0"}
    with httpx.Client() as c:
        resp = c.post(
            "https://github.com/login/device/code",
            content=urllib.parse.urlencode(payload),
            headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
        )
    return resp.json()


@router.post("/github/device/poll")
async def github_device_poll(req: DevicePollRequest, db: Session = Depends(get_db)):
    client_id = os.environ.get("GITHUB_CLIENT_ID", "")
    payload = {
        "client_id": client_id,
        "device_code": req.device_code,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
    }
    with httpx.Client() as c:
        resp = c.post(
            "https://github.com/login/oauth/access_token",
            json=payload,
            headers={"Accept": "application/json", "User-Agent": "Navigator-Server/1.0"},
        )
    data = resp.json()
    if "access_token" not in data:
        return data  # authorization_pending 등

    # GitHub 유저 정보 조회 → DB upsert
    token = data["access_token"]
    with httpx.Client() as c:
        gh = c.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "Navigator-Server/1.0",
            },
        ).json()

    github_id = str(gh.get("id", ""))
    email = gh.get("email") or f"{gh.get('login', 'unknown')}@github.local"
    name  = gh.get("name") or gh.get("login", "GitHub User")

    user = db.query(User).filter(User.github_id == github_id).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()

    if not user:
        user = User(
            name=name, email=email, password_hash="",
            role="engineer",
            github_id=github_id,
            github_login=gh.get("login"),
            github_username=gh.get("login"),
            github_oauth_token=token,
        )
        db.add(user)
    else:
        user.github_id           = github_id
        user.github_login        = gh.get("login")
        user.github_oauth_token  = token
        user.github_username     = gh.get("login")

    db.commit()
    db.refresh(user)
    jwt_token = _make_token(user.id, user.email, user.role)
    return {
        "access_token": jwt_token,
        "token_type": "bearer",
        "user": _build_user_response(db, user).model_dump(),
    }
