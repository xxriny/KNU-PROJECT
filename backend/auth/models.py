"""
SQLAlchemy ORM 모델 — 로컬 DB (local.db) 전용.

User, Team은 shared.db로 이전되었으므로 auth.shared_models를 사용하세요.
여기서는 cross-DB FK를 plain String으로 저장합니다 (SQLite는 DB 간 FK 불가).
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, ForeignKey, DateTime, Text, CheckConstraint, Boolean, Index
from sqlalchemy.orm import relationship

from auth.database import Base
# author: xxrin
# transport/auth 경로에서 auth.models.User를 계속 사용하므로 호환성을 위해 재노출합니다.
from auth.shared_models import User


def _new_uuid() -> str:
    return str(uuid.uuid4())


class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"

    run_id = Column(String(255), primary_key=True)
    # team_id / created_by는 shared.db의 teams/users를 참조하므로 FK 없이 plain string
    team_id = Column(String(36), nullable=True)
    created_by = Column(String(36), nullable=True)
    title = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    change_requests = relationship("DesignChangeRequest", back_populates="session")


class DesignChangeRequest(Base):
    __tablename__ = "design_change_requests"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    session_id = Column(String(255), ForeignKey("analysis_sessions.run_id"), nullable=True)
    # requested_by / approved_by: shared.db users.id를 plain string으로 저장
    requested_by = Column(String(36), nullable=True)
    approved_by = Column(String(36), nullable=True)
    target_section = Column(String(500), nullable=True)
    description = Column(Text, nullable=False)
    status = Column(
        String(20),
        CheckConstraint("status IN ('pending', 'approved', 'rejected')"),
        default="pending",
    )
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("AnalysisSession", back_populates="change_requests")


class MemoItem(Base):
    """사용자 메모 — 로컬 DB 저장."""
    __tablename__ = "memo_items"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    session_id = Column(String(255), nullable=False)
    # team_id: shared.db teams.id를 plain string으로 저장
    team_id = Column(String(36), nullable=True)
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
