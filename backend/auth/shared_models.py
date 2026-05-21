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


class DevPrAnalysis(Base):
    """PR 단위 Dev Tracking 분석 실행 이력"""
    __tablename__ = "dev_pr_analysis"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    team_id = Column(String(36), nullable=True)
    owner = Column(String(255), nullable=False, default="")
    repo = Column(String(255), nullable=False, default="")
    pr_number = Column(Integer, nullable=False, default=0)
    branch_name = Column(String(500), nullable=False, default="")
    base_branch = Column(String(500), nullable=True)
    head_sha = Column(String(128), nullable=True)
    source_dir = Column(Text, nullable=True)
    spec_snapshot_id = Column(String(36), nullable=True)
    approval_status = Column(String(64), nullable=False, default="PENDING_PM_APPROVAL")
    analysis_status = Column(String(64), nullable=False, default="complete")
    task_id = Column(String(36), nullable=True)
    pm_report = Column(Text, nullable=False, default="{}")
    timeline = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_dev_pr_analysis_team_pr", "team_id", "owner", "repo", "pr_number"),
        Index("ix_dev_pr_analysis_head_sha", "head_sha"),
    )


class DevGapItem(Base):
    """Dev Tracking 분석에서 발견한 GAP 항목"""
    __tablename__ = "dev_gap_items"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    analysis_id = Column(String(36), ForeignKey("dev_pr_analysis.id"), nullable=False)
    gap_id = Column(String(64), nullable=False)
    severity = Column(String(32), nullable=False, default="")
    type = Column(String(64), nullable=False, default="")
    spec_target = Column(Text, nullable=True)
    implementation_target = Column(Text, nullable=True)
    intent = Column(String(64), nullable=True)
    recommended_action = Column(String(64), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_dev_gap_items_analysis_id", "analysis_id"),
        Index("ix_dev_gap_items_gap_id", "gap_id"),
    )


class DevKnowledgeArtifact(Base):
    """Dev Tracking 후속 RAG/프롬프트 컨텍스트로 재사용할 지식 아티팩트"""
    __tablename__ = "dev_knowledge_artifacts"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    team_id = Column(String(36), nullable=True)
    artifact_type = Column(String(64), nullable=False, default="DEV_GAP_REPORT")
    source = Column(String(64), nullable=False, default="dev_tracking")
    owner = Column(String(255), nullable=False, default="")
    repo = Column(String(255), nullable=False, default="")
    pr_number = Column(Integer, nullable=False, default=0)
    branch_name = Column(String(500), nullable=True)
    task_id = Column(String(36), nullable=True)
    decision_status = Column(String(64), nullable=True)
    content_json = Column(Text, nullable=False, default="{}")
    searchable_text = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_dev_knowledge_team_repo_pr", "team_id", "owner", "repo", "pr_number"),
        Index("ix_dev_knowledge_artifact_type", "artifact_type"),
        Index("ix_dev_knowledge_task_id", "task_id"),
    )
