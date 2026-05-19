"""
공유 DB (shared.db) 모델 — 향후 팀 배포용 스냅샷 저장소.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, ForeignKey, DateTime, Text, Integer, Index

from auth.database import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


class PublishedSnapshot(Base):
    """공유 DB 스냅샷 — 팀 산출물 공유 단위."""
    __tablename__ = "published_snapshots"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    run_id = Column(String(255), nullable=True)
    team_id = Column(String(36), nullable=True)        # shared.db는 FK 없이 단순 저장
    published_by = Column(String(36), nullable=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    snapshot_data = Column(Text, nullable=False)
    published_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_published_snapshots_team_id", "team_id"),
    )
