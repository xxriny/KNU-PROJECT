"""
공유 DB (shared.db) 모델 — NAVIGATOR-SERVER가 소유하는 테이블.

User, Team, Subscription, PublishedSnapshot 모두 SharedBase를 사용하므로
shared_engine에 바인딩됩니다.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, ForeignKey, DateTime, Text, Integer, Boolean,
    CheckConstraint, Index,
)
from sqlalchemy.orm import relationship

from auth.database import SharedBase


def _new_uuid() -> str:
    return str(uuid.uuid4())


class Team(SharedBase):
    __tablename__ = "teams"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    name = Column(String(255), nullable=False)
    github_repo = Column(String(500), nullable=True)
    github_token = Column(String(500), nullable=True)
    github_client_id = Column(String(255), nullable=True)
    github_client_secret = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="team", cascade="all, delete-orphan")
    subscription = relationship("Subscription", back_populates="team", uselist=False)


class User(SharedBase):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    team_id = Column(String(36), ForeignKey("teams.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    role = Column(
        String(20),
        CheckConstraint("role IN ('pm', 'engineer', 'backend', 'frontend', 'devops')"),
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


class Subscription(SharedBase):
    __tablename__ = "subscriptions"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    team_id = Column(String(36), ForeignKey("teams.id", ondelete="CASCADE"), unique=True, nullable=False)
    plan = Column(
        String(20),
        CheckConstraint("plan IN ('free', 'pro', 'enterprise')"),
        nullable=False,
        default="free",
    )
    status = Column(
        String(20),
        CheckConstraint("status IN ('active', 'canceled', 'past_due', 'trialing')"),
        nullable=False,
        default="active",
    )
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    team = relationship("Team", back_populates="subscription")


class PublishedSnapshot(SharedBase):
    """팀 산출물 공유 단위."""
    __tablename__ = "published_snapshots"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    run_id = Column(String(255), nullable=True)
    team_id = Column(String(36), nullable=True)
    published_by = Column(String(36), nullable=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    snapshot_data = Column(Text, nullable=False)
    published_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_published_snapshots_team_id", "team_id"),
    )
