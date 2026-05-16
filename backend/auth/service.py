"""
인증 서비스: 사용자 생성, JWT 토큰 발급/검증, 비밀번호 해시
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.parse
import uuid
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
import bcrypt as _bcrypt_lib
from sqlalchemy.orm import Session

from auth.models import User, Team

_SECRET_KEY = os.environ.get("NAVIGATOR_JWT_SECRET", "navigator-dev-secret-change-in-production")
_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_DAYS = 7


# ── 비밀번호 ──────────────────────────────────────────────────

def hash_password(password: str) -> str:
    salt = _bcrypt_lib.gensalt(rounds=12)
    return _bcrypt_lib.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt_lib.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ── JWT ──────────────────────────────────────────────────────

def create_access_token(user_id: str, email: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(days=_ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, _SECRET_KEY, algorithm=_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
    except JWTError:
        return None


# ── 사용자 CRUD ──────────────────────────────────────────────

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def create_user(
    db: Session,
    name: str,
    email: str,
    password: str,
    role: str = "engineer",
    github_username: Optional[str] = None,
    team_name: Optional[str] = None,
) -> User:
    team: Optional[Team] = None
    if team_name:
        team = db.query(Team).filter(Team.name == team_name).first()
        if not team:
            team = Team(name=team_name)
            db.add(team)
            db.flush()

    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        role=role,
        github_username=github_username,
        team_id=team.id if team else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def count_users(db: Session) -> int:
    return db.query(User).count()


# ── GitHub OAuth Device Flow ─────────────────────────────────

def _github_post(url: str, data: dict, extra_headers: dict | None = None) -> dict:
    body = urllib.parse.urlencode(data).encode()
    headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def _github_get(url: str, token: str) -> dict | list:
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def start_github_device_flow(client_id: str) -> dict:
    """GitHub Device Flow 시작: user_code, verification_uri, device_code 반환."""
    return _github_post(
        "https://github.com/login/device/code",
        {"client_id": client_id, "scope": "user:email read:user"},
    )


def poll_github_device_token(client_id: str, client_secret: str, device_code: str) -> dict:
    """GitHub Device Flow 폴링: access_token 또는 error 반환."""
    return _github_post(
        "https://github.com/login/oauth/access_token",
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        },
    )


def get_github_user_info(access_token: str) -> dict:
    """GitHub OAuth 토큰으로 사용자 정보 조회."""
    user = _github_get("https://api.github.com/user", access_token)
    email = user.get("email")
    if not email:
        try:
            emails = _github_get("https://api.github.com/user/emails", access_token)
            primary = next((e for e in emails if isinstance(e, dict) and e.get("primary")), None)
            if primary:
                email = primary["email"]
        except Exception:
            pass
    return {
        "id": str(user["id"]),
        "login": user["login"],
        "name": user.get("name") or user["login"],
        "email": email or f"{user['login']}@github-noreply.com",
        "avatar_url": user.get("avatar_url", ""),
    }


def create_or_update_github_user(
    db: Session,
    github_id: str,
    github_login: str,
    email: str,
    name: str,
    oauth_token: str,
) -> User:
    """GitHub OAuth로 로그인 시 사용자 생성 또는 업데이트."""
    user = db.query(User).filter(User.github_id == github_id).first()
    if not user and email:
        user = db.query(User).filter(User.email == email).first()
    if user:
        user.github_id = github_id
        user.github_login = github_login
        user.github_oauth_token = oauth_token
        if not user.github_username:
            user.github_username = github_login
    else:
        user = User(
            name=name,
            email=email,
            password_hash=hash_password(str(uuid.uuid4())),
            role="engineer",
            github_username=github_login,
            github_id=github_id,
            github_login=github_login,
            github_oauth_token=oauth_token,
        )
        db.add(user)
    db.commit()
    db.refresh(user)
    return user


def build_user_response(user: User) -> dict:
    team_name = user.team.name if user.team else None
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "github_username": user.github_username,
        "team_id": user.team_id,
        "team_name": team_name,
    }
