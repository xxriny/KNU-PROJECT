import os
import sys
import types

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from auth.database import Base
from auth.shared_models import DevKnowledgeArtifact, ensure_dev_tracking_schema
from pipeline.domain.dev_tracking.test.dev_tracking_test_utils import _fake_user


@pytest.fixture
def dev_knowledge_db_session():
    # author: xxrin
    # DevKnowledgeArtifact 단일 테이블이 필요한 테스트는 동일한 in-memory DB 세션 fixture를 재사용한다.
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[DevKnowledgeArtifact.__table__])
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def dev_analysis_db_session():
    # author: xxrin
    # DevPrAnalysis/DevGapItem 스키마가 필요한 테스트는 schema migration helper까지 포함해서 준비한다.
    engine = create_engine("sqlite:///:memory:")
    ensure_dev_tracking_schema(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def pm_user():
    return _fake_user("pm", "pm-1")


@pytest.fixture
def admin_user():
    return _fake_user("admin", "admin-1")


@pytest.fixture
def engineer_user():
    return _fake_user("engineer", "eng-1")


@pytest.fixture
def github_oauth_user():
    # author: xxrin
    # GitHub connector endpoint 테스트에서 OAuth token 보유 사용자를 반복 생성하지 않도록 고정 fixture로 제공한다.
    return types.SimpleNamespace(github_oauth_token="token-123")
