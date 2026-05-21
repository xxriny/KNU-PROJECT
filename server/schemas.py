"""Pydantic 스키마 — 요청/응답 모델."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ── Auth ────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    role: str = "engineer"
    github_username: Optional[str] = None
    team_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    github_username: Optional[str] = None
    team_id: Optional[str] = None
    team_name: Optional[str] = None
    plan: str = "free"           # 팀 구독 플랜 (조회 시 합성)

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TeamResponse(BaseModel):
    id: str
    name: str
    github_repo: Optional[str] = None
    plan: str = "free"

    model_config = {"from_attributes": True}


class TeamCreateRequest(BaseModel):
    name: str


class TeamUpdateRequest(BaseModel):
    github_repo: Optional[str] = None
    github_token: Optional[str] = None
    github_client_id: Optional[str] = None
    github_client_secret: Optional[str] = None


class DevicePollRequest(BaseModel):
    device_code: str


# ── Team Invite ─────────────────────────────────────────────

class TeamInviteCreateRequest(BaseModel):
    role: str = "engineer"
    max_uses: int = 1
    expires_in_days: int = 7


class TeamInviteResponse(BaseModel):
    id: str
    team_id: str
    code: str
    creator_id: Optional[str] = None
    role: str
    max_uses: int
    used_count: int
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Billing ─────────────────────────────────────────────────

class PlanInfo(BaseModel):
    id: str
    name: str
    price_usd: int
    features: list[str]


class SubscriptionResponse(BaseModel):
    team_id: str
    plan: str
    status: str
    current_period_end: Optional[datetime] = None
    stripe_subscription_id: Optional[str] = None


class CheckoutRequest(BaseModel):
    team_id: str
    plan: str                    # "pro" | "enterprise"
    success_url: str = ""
    cancel_url: str = ""


# ── Gemini Keys ──────────────────────────────────────────────

class KeyRegisterRequest(BaseModel):
    api_key: str
    label: Optional[str] = None
    team_id: Optional[str] = None   # NULL = 서버 전역 키


class KeyResponse(BaseModel):
    id: str
    label: Optional[str]
    team_id: Optional[str]
    is_active: bool
    usage_count: int
