"""
통합 품질 테스트: 실제 구동 가능성 및 품질 체크
- FastAPI 앱 시작 가능성 검증
- 모든 REST 엔드포인트 등록 확인
- SA 파이프라인 체인 무결성 검증
- 스키마 직렬화/역직렬화 라운드트립 테스트
"""
import os
import sys
import json
import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)


class TestFastAPIApp:
    """FastAPI 앱 시작 가능성 검증"""

    def test_main_app_importable(self):
        """main.py가 임포트 에러 없이 로드되어야 함"""
        import main
        assert hasattr(main, "app")

    def test_rest_router_registered(self):
        """REST 라우터가 앱에 등록되어야 함"""
        import main
        routes = [r.path for r in main.app.routes]
        assert "/health" in routes
        assert "/api/analyze" in routes
        assert "/api/rag/ingest" in routes
        assert "/api/rag/query" in routes
        # dev 엔드포인트는 없어야 함
        assert "/api/develop" not in routes

    def test_websocket_endpoint_registered(self):
        """WebSocket 엔드포인트가 등록되어야 함"""
        import main
        ws_routes = [r.path for r in main.app.routes if hasattr(r, "path") and "ws" in r.path]
        assert len(ws_routes) > 0, "WebSocket 엔드포인트가 등록되지 않았습니다"


class TestSAPipelineIntegrity:
    """SA 파이프라인 체인 무결성 검증"""

    def test_sa_pipeline_builds_without_error(self):
        """SA 파이프라인 컴파일이 에러 없이 완료되어야 함"""
        from pipeline.orchestration.graph import get_sa_pipeline
        pipeline = get_sa_pipeline()
        assert pipeline is not None

    def test_analysis_pipeline_builds_without_error(self):
        """전체 분석 파이프라인 컴파일이 에러 없이 완료되어야 함"""
        from pipeline.orchestration.graph import get_analysis_pipeline
        pipeline = get_analysis_pipeline()
        assert pipeline is not None

    def test_rag_ingest_pipeline_builds(self):
        """RAG ingest 파이프라인 컴파일이 에러 없이 완료되어야 함"""
        from pipeline.orchestration.facade import get_rag_ingest_pipeline
        pipeline = get_rag_ingest_pipeline()
        assert pipeline is not None

    def test_sa_chain_is_linear(self):
        """SA 체인의 각 노드가 유일해야 함 (중복 없음)"""
        from pipeline.orchestration.graph import _SA_CHAIN
        assert len(_SA_CHAIN) == len(set(_SA_CHAIN)), "SA 체인에 중복 노드가 있습니다"

    def test_sa_chain_has_6_nodes(self):
        """SA 체인이 정확히 6개 노드를 가져야 함"""
        from pipeline.orchestration.graph import _SA_CHAIN
        assert len(_SA_CHAIN) == 6, f"SA 체인 노드 수 오류: {len(_SA_CHAIN)} (예상: 6)"
        expected = (
            "sa_merge_project",
            "component_scheduler",
            "sa_unified_modeler",
            "sa_test_analysis",
            "sa_project_structure",
            "sa_embedding",
        )
        assert _SA_CHAIN == expected, f"SA 체인 순서 오류: {_SA_CHAIN}"


class TestSchemaRoundTrip:
    """스키마 직렬화/역직렬화 라운드트립 테스트"""

    def test_sa_test_analysis_output_roundtrip(self):
        """SATestAnalysisOutput JSON 직렬화 → 역직렬화가 무결해야 함"""
        from pipeline.domain.sa.schemas import SATestAnalysisOutput

        data = {
            "th": "인증 서비스가 가장 높은 위험도",
            "tp": "단위 테스트 우선, 통합 테스트 TestContainers",
            "rz": [{"cn": "AuthService", "rl": "critical", "rs": "외부 연동", "mt": "Circuit Breaker"}],
            "us": [{"cn": "AuthService", "ki": ["토큰 만료→401"], "mt": ["UserRepo Stub"], "ec": ["경계값"]}],
            "is_": [{"ep": "POST /api/login", "db": "TestContainers", "ts": "롤백 검증", "cp": ""}],
            "ss": [{"cp": "User→Auth→DB", "sl": "p99<200ms", "cs": ["DB 단절"]}],
            "as_": [{"fi": "FEAT_001", "gv": "유효 계정", "wh": "로그인", "tn": "성공", "ec": ""}],
            "td": "Faker + 트랜잭션 롤백",
            "ap": ["단위 먼저", "CI 통합"],
        }
        obj = SATestAnalysisOutput.model_validate(data)
        serialized = obj.model_dump()
        re_obj = SATestAnalysisOutput(**serialized)
        assert re_obj.test_philosophy == obj.test_philosophy
        assert len(re_obj.risk_zones) == 1
        assert re_obj.risk_zones[0].component_name == "AuthService"

    def test_sa_project_structure_output_roundtrip(self):
        """SAProjectStructureOutput JSON 직렬화 → 역직렬화가 무결해야 함"""
        from pipeline.domain.sa.schemas import SAProjectStructureOutput

        data = {
            "th": "FastAPI 표준 구조",
            "tr": {
                "nm": "project-root",
                "tp": "dir",
                "ch": [
                    {"nm": "backend", "tp": "dir", "ch": []},
                ],
            },
            "cm": {"AuthService": ["backend/app/api/v1/auth.py"]},
            "cv": ["snake_case"],
        }
        obj = SAProjectStructureOutput.model_validate(data)
        assert obj.tree.name == "project-root"
        assert len(obj.tree.children) == 1
        assert "AuthService" in obj.component_mapping

    def test_directory_node_deep_nesting(self):
        """DirectoryNode 3단계 이상 중첩이 가능해야 함"""
        from pipeline.domain.sa.schemas import DirectoryNode

        node = DirectoryNode.model_validate({
            "nm": "project",
            "tp": "dir",
            "ch": [{
                "nm": "backend",
                "tp": "dir",
                "ch": [{
                    "nm": "app",
                    "tp": "dir",
                    "ch": [{"nm": "main.py", "tp": "file"}]
                }]
            }]
        })
        assert node.children[0].children[0].children[0].name == "main.py"


class TestEndpointResponseModels:
    """REST 엔드포인트 응답 모델 무결성 확인"""

    def test_analysis_request_model(self):
        from transport.rest_handler import AnalysisRequest
        req = AnalysisRequest(idea="테스트 프로젝트")
        assert req.idea == "테스트 프로젝트"
        assert req.action_type == "CREATE"
        assert req.model is not None

    def test_rag_ingest_request_model(self):
        from transport.rest_handler import RAGIngestRequest
        req = RAGIngestRequest(source_dir="/tmp/test", session_id="test_session")
        assert req.source_dir == "/tmp/test"
        assert req.version == "v1.0"

    def test_rag_query_request_model(self):
        from transport.rest_handler import RAGQueryRequest
        req = RAGQueryRequest(query="인증 서비스 로직")
        assert req.n_results == 10
        assert req.session_id is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
