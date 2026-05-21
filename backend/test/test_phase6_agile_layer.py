"""
Phase 3 (Agile Layer): 통합 검증
- schemas.py 임포트 및 모델 검증
- verifier.py V-001~V-005 규칙 검증 (LLM 없이)
- impact.py 키워드 폴백 검증
- REST endpoint 등록 확인
- 프론트엔드 파일 존재 확인
"""

import os
import sys
import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(os.path.dirname(BACKEND_DIR), "src")
sys.path.insert(0, BACKEND_DIR)


# ── Schemas ───────────────────────────────────────────────────────────────────

class TestAgileSchemas:
    def test_import_schemas(self):
        from pipeline.domain.agile.schemas import (
            VerifierResult, ViolationItem, ImpactResult, ImpactedComponent,
            Severity,
        )

    def test_verifier_result_defaults(self):
        from pipeline.domain.agile.schemas import VerifierResult
        r = VerifierResult(coherence_score=0.8, passed=True)
        assert r.violations == []
        assert r.summary == ""

    def test_violation_item(self):
        from pipeline.domain.agile.schemas import ViolationItem, Severity
        v = ViolationItem(
            rule_id="V-001",
            rule_name="테스트",
            severity=Severity.major,
            description="테스트 위반",
        )
        assert v.rule_id == "V-001"
        assert v.severity == Severity.major

    def test_impact_result(self):
        from pipeline.domain.agile.schemas import ImpactResult, ImpactedComponent
        ic = ImpactedComponent(name="AuthService", impact_type="modify", description="변경됨")
        r = ImpactResult(
            change_description="OAuth 추가",
            impacted_components=[ic],
            risk_level="high",
        )
        assert len(r.impacted_components) == 1
        assert r.risk_level == "high"


# ── Verifier Rules ────────────────────────────────────────────────────────────

class TestVerifierRules:
    """LLM 없이 V-001~V-005 규칙만 검증"""

    def _run(self, sa_data):
        from pipeline.domain.agile.nodes.verifier import run_verifier
        return run_verifier(sa_data, api_key="", use_llm=False)

    def test_clean_data_passes(self):
        sa_data = {
            "components": [{"name": "AuthService", "type": "service", "dependencies": []}],
            "apis": [{"endpoint": "/api/health", "method": "GET", "owner_component": "AuthService"}],
            "tables": [{"name": "users", "fields": [{"name": "id"}, {"name": "created_at"}, {"name": "email"}]}],
        }
        result = self._run(sa_data)
        assert result.passed
        assert result.coherence_score >= 0.7

    def test_v001_missing_owner_component(self):
        sa_data = {
            "components": [{"name": "ServiceA", "type": "service"}],
            "apis": [{"endpoint": "/api/test", "method": "GET", "owner_component": "NonExistentService"}],
            "tables": [],
        }
        result = self._run(sa_data)
        violation_ids = [v.rule_id for v in result.violations]
        assert "V-001" in violation_ids

    def test_v002_circular_dependency(self):
        sa_data = {
            "components": [
                {"name": "A", "type": "service", "dependencies": ["B"]},
                {"name": "B", "type": "service", "dependencies": ["A"]},
            ],
            "apis": [],
            "tables": [],
        }
        result = self._run(sa_data)
        violation_ids = [v.rule_id for v in result.violations]
        assert "V-002" in violation_ids

    def test_v003_missing_table_fields(self):
        sa_data = {
            "components": [],
            "apis": [],
            "tables": [{"name": "orders", "fields": [{"name": "product_id"}]}],
        }
        result = self._run(sa_data)
        violation_ids = [v.rule_id for v in result.violations]
        assert "V-003" in violation_ids

    def test_v004_security_layer_missing(self):
        sa_data = {
            "components": [{"name": "ProductService", "type": "service"}],
            "apis": [
                {"endpoint": "/api/login", "method": "POST", "owner_component": "ProductService"},
                {"endpoint": "/api/users", "method": "GET", "owner_component": "ProductService"},
            ],
            "tables": [],
        }
        result = self._run(sa_data)
        violation_ids = [v.rule_id for v in result.violations]
        assert "V-004" in violation_ids

    def test_v005_external_interface_missing(self):
        sa_data = {
            "components": [
                {"name": "ExternalGateway", "type": "external", "dependencies": []},
            ],
            "apis": [],
            "tables": [],
        }
        result = self._run(sa_data)
        violation_ids = [v.rule_id for v in result.violations]
        assert "V-005" in violation_ids

    def test_score_range(self):
        result = self._run({"components": [], "apis": [], "tables": []})
        assert 0.0 <= result.coherence_score <= 1.0

    def test_empty_sa_data_no_crash(self):
        result = self._run({})
        assert isinstance(result.violations, list)


# ── Impact Analyzer (Fallback) ────────────────────────────────────────────────

class TestImpactAnalyzer:
    def test_fallback_no_api_key(self):
        from pipeline.domain.agile.nodes.impact import run_impact_analyzer
        sa_data = {
            "components": [
                {"name": "AuthService", "type": "service"},
                {"name": "UserRepository", "type": "repository"},
            ],
            "apis": [],
            "tables": [],
        }
        result = run_impact_analyzer(
            change_description="AuthService에 OAuth 통합 추가",
            sa_data=sa_data,
            api_key="",
        )
        assert result.change_description == "AuthService에 OAuth 통합 추가"
        assert isinstance(result.impacted_components, list)
        assert any(c.name == "AuthService" for c in result.impacted_components)

    def test_empty_description_fallback(self):
        from pipeline.domain.agile.nodes.impact import run_impact_analyzer
        result = run_impact_analyzer(
            change_description="unknown change xyz",
            sa_data={"components": [], "apis": [], "tables": []},
            api_key="",
        )
        assert result.risk_level == "medium"

    def test_impact_result_structure(self):
        from pipeline.domain.agile.nodes.impact import run_impact_analyzer
        result = run_impact_analyzer("DB 스키마 변경", {"components": [], "apis": [], "tables": []}, api_key="")
        assert hasattr(result, "impacted_components")
        assert hasattr(result, "impacted_apis")
        assert hasattr(result, "impacted_tables")
        assert hasattr(result, "risk_level")
        assert hasattr(result, "summary")


# ── REST Endpoint Registration ────────────────────────────────────────────────

class TestRESTEndpoints:
    def test_agile_endpoints_registered(self):
        from transport.rest_handler import rest_router
        paths = [r.path for r in rest_router.routes]
        assert "/api/agile/verify" in paths, f"/api/agile/verify 누락. 등록된 경로: {paths}"
        assert "/api/agile/impact" in paths, f"/api/agile/impact 누락. 등록된 경로: {paths}"

    def test_agile_verify_request_model(self):
        from transport.rest_handler import AgileVerifyRequest
        req = AgileVerifyRequest(sa_data={"components": []})
        assert req.use_llm is True
        assert req.api_key == ""

    def test_agile_impact_request_model(self):
        from transport.rest_handler import AgileImpactRequest
        req = AgileImpactRequest(change_description="테스트 변경", sa_data={})
        assert req.change_description == "테스트 변경"
        assert req.session_id is None


# ── Frontend Files ────────────────────────────────────────────────────────────

class TestFrontendFiles:
    def _fe(self, *parts):
        return os.path.join(FRONTEND_DIR, *parts)

    def test_agile_verifier_tab_exists(self):
        path = self._fe("components", "resultViewer", "AgileVerifierTab.jsx")
        assert os.path.exists(path), f"AgileVerifierTab.jsx 없음: {path}"

    def test_agile_impact_tab_exists(self):
        path = self._fe("components", "resultViewer", "AgileImpactTab.jsx")
        assert os.path.exists(path), f"AgileImpactTab.jsx 없음: {path}"

    def test_result_viewer_imports_agile_tabs(self):
        path = self._fe("components", "ResultViewer.jsx")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "AgileVerifierTab" in content
        assert "AgileImpactTab" in content
        assert "agile_verify" in content
        assert "agile_impact" in content

    def test_ui_constants_has_agile_tabs(self):
        path = self._fe("constants", "uiConstants.js")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "agile_verify" in content, "agile_verify 탭 등록 누락"
        assert "agile_impact" in content, "agile_impact 탭 등록 누락"

    def test_memo_manager_has_rbac(self):
        path = self._fe("components", "resultViewer", "MemoManager.jsx")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "userRole" in content
        assert "canEdit" in content

    def test_agile_verifier_content(self):
        path = self._fe("components", "resultViewer", "AgileVerifierTab.jsx")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "coherence_score" in content
        assert "/api/agile/verify" in content
        assert "violations" in content

    def test_agile_impact_content(self):
        path = self._fe("components", "resultViewer", "AgileImpactTab.jsx")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "change_description" in content or "changeDesc" in content
        assert "/api/agile/impact" in content
        assert "impacted_components" in content or "impactedComps" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
