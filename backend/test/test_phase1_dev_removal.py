"""
Phase 1: dev 파이프라인 제거 검증 테스트
- dev 디렉토리/파일 삭제 확인
- 참조 임포트 정상 동작 확인
- REST/WS 핸들러에서 dev 엔드포인트 제거 확인
"""
import os
import sys
import importlib
import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)


class TestDevRemoval:
    """dev 파이프라인 제거 검증"""

    def test_dev_domain_directory_deleted(self):
        """backend/pipeline/domain/dev/ 디렉토리가 없어야 함"""
        dev_dir = os.path.join(BACKEND_DIR, "pipeline", "domain", "dev")
        assert not os.path.exists(dev_dir), f"dev/ 디렉토리가 아직 존재합니다: {dev_dir}"

    def test_dev_graphs_file_deleted(self):
        """backend/pipeline/orchestration/dev_graphs.py가 없어야 함"""
        dev_graphs = os.path.join(BACKEND_DIR, "pipeline", "orchestration", "dev_graphs.py")
        assert not os.path.exists(dev_graphs), "dev_graphs.py가 아직 존재합니다"

    def test_facade_imports_without_dev(self):
        """facade.py가 dev 없이 정상 임포트되어야 함"""
        from pipeline.orchestration import facade
        assert hasattr(facade, "get_analysis_pipeline")
        assert hasattr(facade, "get_rag_ingest_pipeline")
        assert not hasattr(facade, "get_develop_pipeline"), "get_develop_pipeline이 아직 facade에 있습니다"
        assert not hasattr(facade, "get_develop_routing_map"), "get_develop_routing_map이 아직 facade에 있습니다"

    def test_rest_handler_no_develop_endpoint(self):
        """rest_handler에 /api/develop 엔드포인트가 없어야 함"""
        from transport.rest_handler import rest_router
        routes = [r.path for r in rest_router.routes]
        assert "/api/develop" not in routes, "/api/develop 라우트가 아직 존재합니다"

    def test_rest_handler_no_develop_request_model(self):
        """rest_handler에 DevelopRequest 모델이 없어야 함"""
        import transport.rest_handler as rh
        assert not hasattr(rh, "DevelopRequest"), "DevelopRequest 모델이 아직 존재합니다"

    def test_ws_handler_no_develop_type(self):
        """ws_handler 소스에 develop 타입 핸들러가 없어야 함"""
        ws_file = os.path.join(BACKEND_DIR, "transport", "ws_handler.py")
        with open(ws_file, encoding="utf-8") as f:
            content = f.read()
        assert "run_develop" not in content, "ws_handler에 run_develop 참조가 남아있습니다"
        assert "develop_pipeline" not in content, "ws_handler에 develop_pipeline 참조가 남아있습니다"

    def test_pipeline_runner_no_develop(self):
        """pipeline_runner에 develop 관련 코드가 없어야 함"""
        runner_file = os.path.join(BACKEND_DIR, "orchestration", "pipeline_runner.py")
        with open(runner_file, encoding="utf-8") as f:
            content = f.read()
        assert "get_develop_pipeline" not in content
        assert "run_develop" not in content

    def test_core_pipelines_still_work(self):
        """dev 제거 후에도 핵심 파이프라인 함수가 임포트 가능해야 함"""
        from pipeline.orchestration.facade import (
            get_analysis_pipeline,
            get_pm_pipeline,
            get_sa_pipeline,
            get_rag_ingest_pipeline,
            get_idea_pipeline,
        )
        # 모두 callable이어야 함
        assert callable(get_analysis_pipeline)
        assert callable(get_pm_pipeline)
        assert callable(get_sa_pipeline)
        assert callable(get_rag_ingest_pipeline)
        assert callable(get_idea_pipeline)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
