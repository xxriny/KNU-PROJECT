"""
SQLAlchemy ORM 모델: User, Team, AnalysisSession, DesignChangeRequest
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, ForeignKey, DateTime, Text, CheckConstraint, Boolean, Index, Integer
from sqlalchemy.orm import relationship

from auth.database import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Team(Base):
    __tablename__ = "teams"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    name = Column(String(255), nullable=False)
    github_repo = Column(String(500), nullable=True)
    github_token = Column(String(500), nullable=True)
    
    # 동적 OAuth 구성을 위한 필드
    github_client_id = Column(String(255), nullable=True)
    github_client_secret = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="team", cascade="all, delete-orphan")
    sessions = relationship("AnalysisSession", back_populates="team")


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    team_id = Column(String(36), ForeignKey("teams.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    role = Column(
        String(20),
        CheckConstraint("role IN ('pm', 'engineer', 'viewer', 'backend', 'frontend', 'devops')"),
        nullable=False,
        default="engineer",
    )
    github_username = Column(String(255), nullable=True)
    github_id = Column(String(64), unique=True, nullable=True)
    github_login = Column(String(255), nullable=True)
    github_oauth_token = Column(String(500), nullable=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    team = relationship("Team", back_populates="users")
    sessions_created = relationship("AnalysisSession", back_populates="creator")
    change_requests = relationship(
        "DesignChangeRequest",
        foreign_keys="DesignChangeRequest.requested_by",
        back_populates="requester",
    )


class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"

    run_id = Column(String(255), primary_key=True)
    team_id = Column(String(36), ForeignKey("teams.id"), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    title = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    team = relationship("Team", back_populates="sessions")
    creator = relationship("User", back_populates="sessions_created")
    change_requests = relationship("DesignChangeRequest", back_populates="session")


class DesignChangeRequest(Base):
    __tablename__ = "design_change_requests"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    session_id = Column(String(255), ForeignKey("analysis_sessions.run_id"), nullable=True)
    requested_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    approved_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    target_section = Column(String(500), nullable=True)
    description = Column(Text, nullable=False)
    status = Column(
        String(20),
        CheckConstraint("status IN ('pending', 'approved', 'rejected')"),
        default="pending",
    )
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("AnalysisSession", back_populates="change_requests")
    requester = relationship(
        "User",
        foreign_keys=[requested_by],
        back_populates="change_requests",
    )


class MemoItem(Base):
    """사용자 메모 — ChromaDB memo_db 대체 (팀 DB 단일화)."""
    __tablename__ = "memo_items"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    session_id = Column(String(255), nullable=False)
    team_id = Column(String(36), ForeignKey("teams.id"), nullable=True)
    text = Column(Text, nullable=False)
    selected_text = Column(Text, default="")
    section = Column(String(255), default="Global")
    detail = Column(Text, default="")
    applied = Column(Boolean, default=False)
    applied_at = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_memo_items_session_id", "session_id"),
    )


class AnalysisResult(Base):
    """로컬 분석 결과 저장 — 파이프라인 완료 시 자동 저장."""
    __tablename__ = "analysis_results"

    run_id = Column(String(255), ForeignKey("analysis_sessions.run_id", ondelete="CASCADE"), primary_key=True)
    shaped_result = Column(Text, nullable=False)  # JSON
    saved_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("AnalysisSession")


class PublishedSnapshot(Base):
    """공유 DB 스냅샷 — GitHub 커밋과 동일 개념."""
    __tablename__ = "published_snapshots"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    run_id = Column(String(255), nullable=True)           # 원본 run_id
    team_id = Column(String(36), ForeignKey("teams.id"), nullable=True)
    published_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    title = Column(String(500), nullable=False)            # "커밋 메시지" 역할
    description = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)  # 팀 내 자동 증가
    snapshot_data = Column(Text, nullable=False)           # JSON (PM + SA 산출물)
    published_at = Column(DateTime, default=datetime.utcnow)

    team = relationship("Team")
    publisher = relationship("User", foreign_keys=[published_by])

    __table_args__ = (
        Index("ix_published_snapshots_team_id", "team_id"),
    )
