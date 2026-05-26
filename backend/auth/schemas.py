"""
Pydantic 스키마: 인증 요청/응답 모델
"""

from typing import Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime


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


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    github_username: Optional[str] = None
    team_id: Optional[str] = None
    team_name: Optional[str] = None

    model_config = {"from_attributes": True}


class TeamResponse(BaseModel):
    id: str
    name: str
    github_repo: Optional[str] = None

    model_config = {"from_attributes": True}


class TeamUpdateRequest(BaseModel):
    github_repo: Optional[str] = None
    github_token: Optional[str] = None


class TeamNameUpdateRequest(BaseModel):
    name: str


class ChangeRequestCreate(BaseModel):
    session_id: str
    target_section: str
    description: str


class ChangeRequestResponse(BaseModel):
    id: str
    session_id: Optional[str]
    requested_by: Optional[str]
    target_section: Optional[str]
    description: str
    status: str
    created_at: str

    model_config = {"from_attributes": True}


class ChangeRequestUpdate(BaseModel):
    status: str


class DevicePollRequest(BaseModel):
    device_code: str


class TeamInviteCreateRequest(BaseModel):
    role: str = "engineer"
    max_uses: int = 1
    expires_in_days: int = 7


class TeamInviteResponse(BaseModel):
    id: str
    team_id: str
    code: str
    creator_id: str
    role: str
    max_uses: int
    used_count: int
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
