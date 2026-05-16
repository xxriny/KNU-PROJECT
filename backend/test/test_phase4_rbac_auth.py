"""
Phase 4 (RBAC): 인증 시스템 검증 테스트
- auth 모듈 임포트 확인
- DB 모델 생성 확인
- JWT 토큰 발급/검증
- 사용자 CRUD 동작
- FastAPI 엔드포인트 라우트 존재 확인
"""

import os
import sys
import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)


class TestAuthImports:
    """auth 모듈 임포트 확인"""

    def test_database_importable(self):
        from auth.database import engine, SessionLocal, init_db, get_db
        assert engine is not None
        assert callable(init_db)

    def test_models_importable(self):
        from auth.models import User, Team, AnalysisSession, DesignChangeRequest
        assert User.__tablename__ == "users"
        assert Team.__tablename__ == "teams"
        assert AnalysisSession.__tablename__ == "analysis_sessions"
        assert DesignChangeRequest.__tablename__ == "design_change_requests"

    def test_service_importable(self):
        from auth.service import (
            hash_password, verify_password,
            create_access_token, decode_token,
            get_user_by_email, create_user, authenticate_user, count_users,
        )
        assert callable(hash_password)
        assert callable(create_access_token)

    def test_deps_importable(self):
        from auth.deps import get_current_user, require_pm, require_engineer
        assert callable(get_current_user)
        assert callable(require_pm)
        assert callable(require_engineer)

    def test_router_importable(self):
        from auth.router import auth_router
        assert auth_router is not None


class TestAuthDBInit:
    """DB 초기화 및 테이블 생성 확인"""

    def test_init_db_creates_tables(self):
        from auth.database import init_db, engine
        from sqlalchemy import inspect
        init_db()
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "users" in tables
        assert "teams" in tables
        assert "analysis_sessions" in tables
        assert "design_change_requests" in tables


class TestAuthService:
    """JWT + 비밀번호 해시 동작 확인"""

    def test_password_hash_and_verify(self):
        from auth.service import hash_password, verify_password
        hashed = hash_password("my-secret-pw")
        assert hashed != "my-secret-pw"
        assert verify_password("my-secret-pw", hashed)
        assert not verify_password("wrong-pw", hashed)

    def test_create_and_decode_token(self):
        from auth.service import create_access_token, decode_token
        token = create_access_token("user-123", "test@test.com", "engineer")
        assert isinstance(token, str)
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["email"] == "test@test.com"
        assert payload["role"] == "engineer"

    def test_decode_invalid_token_returns_none(self):
        from auth.service import decode_token
        result = decode_token("invalid.token.string")
        assert result is None


class TestAuthUserCRUD:
    """사용자 생성 및 인증 동작 확인 (임시 DB 사용)"""

    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path, monkeypatch):
        """각 테스트마다 격리된 임시 DB 사용"""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from auth.database import Base
        import auth.models  # noqa: F401

        db_path = tmp_path / "test.db"
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        TestSession = sessionmaker(bind=engine)
        self.db = TestSession()
        yield
        self.db.close()

    def test_create_user(self):
        from auth.service import create_user, get_user_by_email
        user = create_user(self.db, "테스트유저", "t@t.com", "password123", "pm")
        assert user.id is not None
        assert user.email == "t@t.com"
        assert user.role == "pm"

        fetched = get_user_by_email(self.db, "t@t.com")
        assert fetched is not None
        assert fetched.name == "테스트유저"

    def test_authenticate_success(self):
        from auth.service import create_user, authenticate_user
        create_user(self.db, "Auth유저", "auth@t.com", "pass1234", "engineer")
        user = authenticate_user(self.db, "auth@t.com", "pass1234")
        assert user is not None

    def test_authenticate_wrong_password(self):
        from auth.service import create_user, authenticate_user
        create_user(self.db, "Auth유저2", "auth2@t.com", "correct", "viewer")
        user = authenticate_user(self.db, "auth2@t.com", "wrong")
        assert user is None

    def test_count_users(self):
        from auth.service import create_user, count_users
        assert count_users(self.db) == 0
        create_user(self.db, "유저1", "u1@t.com", "pw", "pm")
        create_user(self.db, "유저2", "u2@t.com", "pw", "engineer")
        assert count_users(self.db) == 2

    def test_create_user_with_team(self):
        from auth.service import create_user
        user = create_user(self.db, "팀원", "team@t.com", "pw", "engineer", team_name="NAVIGATOR Team")
        assert user.team_id is not None
        assert user.team.name == "NAVIGATOR Team"


class TestAuthRouterRegistration:
    """main.py에 auth 라우터가 등록되었는지 확인"""

    def test_main_imports_auth_router(self):
        main_file = os.path.join(BACKEND_DIR, "main.py")
        with open(main_file, encoding="utf-8") as f:
            content = f.read()
        assert "auth_router" in content
        assert "init_db" in content
        assert "app.include_router(auth_router)" in content

    def test_rest_handler_has_user_team_fields(self):
        handler_file = os.path.join(BACKEND_DIR, "transport", "rest_handler.py")
        with open(handler_file, encoding="utf-8") as f:
            content = f.read()
        assert "user_id: Optional[str] = None" in content
        assert "team_id: Optional[str] = None" in content


class TestAuthEndpointPaths:
    """FastAPI 라우터 경로 확인"""

    def test_auth_routes_exist(self):
        from auth.router import auth_router
        paths = [r.path for r in auth_router.routes]
        assert "/auth/status" in paths
        assert "/auth/register" in paths
        assert "/auth/login" in paths
        assert "/auth/me" in paths
        assert "/api/teams/me" in paths
        assert "/api/change-requests" in paths


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
