"""
Pydantic 스키마: 인증 요청/응답 모델
"""

from typing import Optional
from pydantic import BaseModel, EmailStr


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
