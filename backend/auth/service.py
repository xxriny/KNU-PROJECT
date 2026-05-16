"""
인증 서비스: 사용자 생성, JWT 토큰 발급/검증, 비밀번호 해시
"""

from __future__ import annotations

import os
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
