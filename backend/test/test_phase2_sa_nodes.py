"""
Phase 2: SA 신규 노드 검증 테스트
- sa_test_analysis 노드 임포트 및 스키마 확인
- sa_project_structure 노드 임포트 및 스키마 확인
- graph.py SA 체인에 두 노드 포함 여부 확인
- Mock 상태로 노드 실행 시 정상 반환 확인
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)


class TestSANodeImports:
    """SA 노드 임포트 및 구조 확인"""

    def test_sa_test_analysis_importable(self):
        from pipeline.domain.sa.nodes.sa_test_analysis import sa_test_analysis_node
        assert callable(sa_test_analysis_node)

    def test_sa_project_structure_importable(self):
        from pipeline.domain.sa.nodes.sa_project_structure import sa_project_structure_node
        assert callable(sa_project_structure_node)

    def test_sa_test_analysis_schema_importable(self):
        from pipeline.domain.sa.schemas import (
            SATestAnalysisOutput,
            RiskZone,
            UnitTestSpec,
            IntegrationTestSpec,
            SystemTestSpec,
            AcceptanceTestSpec,
        )
        # 스키마 필드 확인
        fields = SATestAnalysisOutput.model_fields
        assert "thinking" in fields
        assert "risk_zones" in fields
        assert "unit_specs" in fields
        assert "integration_specs" in fields
        assert "system_specs" in fields
        assert "acceptance_specs" in fields
        assert "test_data_strategy" in fields
        assert "automation_priority" in fields

    def test_sa_project_structure_schema_importable(self):
        from pipeline.domain.sa.schemas import SAProjectStructureOutput, DirectoryNode
        fields = SAProjectStructureOutput.model_fields
        assert "tree" in fields
        assert "component_mapping" in fields
        assert "conventions" in fields

    def test_directory_node_recursive(self):
        """DirectoryNode가 재귀 구조를 지원해야 함"""
        from pipeline.domain.sa.schemas import DirectoryNode
        root = DirectoryNode.model_validate({
            "nm": "root",
            "tp": "dir",
            "ch": [
                {"nm": "src", "tp": "dir", "ch": []},
                {"nm": "main.py", "tp": "file"},
            ]
        })
        assert root.name == "root"
        assert len(root.children) == 2


class TestSAChainRegistration:
    """graph.py SA 체인에 노드 등록 확인"""

    def test_sa_chain_includes_new_nodes(self):
        from pipeline.orchestration import graph
        chain = graph._SA_CHAIN
        assert "sa_test_analysis" in chain, "sa_test_analysis가 SA 체인에 없습니다"
        assert "sa_project_structure" in chain, "sa_project_structure가 SA 체인에 없습니다"

    def test_sa_chain_order(self):
        """체인 순서: sa_unified_modeler → sa_test_analysis → sa_project_structure → sa_embedding"""
        from pipeline.orchestration import graph
        chain = list(graph._SA_CHAIN)
        unified_idx = chain.index("sa_unified_modeler")
        test_idx = chain.index("sa_test_analysis")
        struct_idx = chain.index("sa_project_structure")
        embed_idx = chain.index("sa_embedding")
        assert unified_idx < test_idx < struct_idx < embed_idx, (
            f"SA 체인 순서 오류: unified={unified_idx}, test={test_idx}, "
            f"struct={struct_idx}, embed={embed_idx}"
        )


class TestSANodeExecution:
    """실제 state dict로 SA 노드 실행 검증

    @pipeline_node 데코레이터는 state dict를 받아 NodeContext를 생성하므로
    테스트도 state dict를 직접 전달해야 함.
    """

    def _make_state(self, overrides: dict) -> dict:
        """기본 state dict 생성 헬퍼"""
        base = {
            "run_id": "test_20260516_000000",
            "api_key": "",
            "model": "gemini-2.0-flash",
            "action_type": "CREATE",
            "thinking_log": [],
        }
        base.update(overrides)
        return base

    def test_sa_test_analysis_empty_bundle_returns_gracefully(self):
        """sa_arch_bundle이 없을 때 노드가 gracefully 종료해야 함"""
        from pipeline.domain.sa.nodes.sa_test_analysis import sa_test_analysis_node
        state = self._make_state({"sa_arch_bundle": None})
        result = sa_test_analysis_node(state)
        assert "current_step" in result
        assert result["current_step"] == "sa_test_analysis_done"

    def test_sa_project_structure_empty_bundle_returns_gracefully(self):
        """sa_arch_bundle이 없을 때 노드가 gracefully 종료해야 함"""
        from pipeline.domain.sa.nodes.sa_project_structure import sa_project_structure_node
        state = self._make_state({"sa_arch_bundle": None})
        result = sa_project_structure_node(state)
        assert "current_step" in result
        assert result["current_step"] == "sa_project_structure_done"

    def test_sa_test_analysis_with_mock_llm(self):
        """Mock LLM으로 sa_test_analysis 정상 실행 확인"""
        from pipeline.domain.sa.nodes.sa_test_analysis import sa_test_analysis_node
        from pipeline.domain.sa.schemas import SATestAnalysisOutput

        mock_output = SATestAnalysisOutput.model_validate({
            "th": "테스트 전략 분석",
            "tp": "단위 테스트 우선 전략",
            "rz": [{"cn": "AuthService", "rl": "critical", "rs": "인증 핵심", "mt": "Circuit Breaker"}],
            "us": [{"cn": "AuthService", "ki": ["토큰 만료 → 401"], "mt": ["UserRepo Stub"], "ec": ["경계값"]}],
            "is_": [{"ep": "POST /api/login", "db": "TestContainers", "ts": "롤백 검증", "cp": ""}],
            "ss": [{"cp": "User→Auth→DB", "sl": "p99<200ms", "cs": ["DB 단절"]}],
            "as_": [{"fi": "FEAT_001", "gv": "유효 계정 존재", "wh": "로그인 시도", "tn": "성공 응답", "ec": ""}],
            "td": "Faker + 트랜잭션 롤백",
            "ap": ["단위 먼저", "통합 CI 연동"],
        })

        mock_res = MagicMock()
        mock_res.parsed = mock_output

        sa_bundle = {
            "data": {
                "components": [{"name": "AuthService", "role": "인증"}],
                "apis": [{"endpoint": "POST /api/login"}],
                "tables": [{"table_name": "users"}],
            }
        }

        state = self._make_state({
            "sa_arch_bundle": sa_bundle,
            "merged_project": {"plan": {"requirements_rtm": [{"id": "FEAT_001"}]}},
        })

        with patch("pipeline.domain.sa.nodes.sa_test_analysis.call_structured", return_value=mock_res):
            result = sa_test_analysis_node(state)

        assert "sa_test_analysis_output" in result
        assert "sa_arch_bundle" in result
        assert "test_strategy" in result["sa_arch_bundle"]["data"]
        assert result["current_step"] == "sa_test_analysis_done"

    def test_sa_project_structure_with_mock_llm(self):
        """Mock LLM으로 sa_project_structure 정상 실행 확인"""
        from pipeline.domain.sa.nodes.sa_project_structure import sa_project_structure_node
        from pipeline.domain.sa.schemas import SAProjectStructureOutput

        mock_output = SAProjectStructureOutput.model_validate({
            "th": "FastAPI 표준 구조 적용",
            "tr": {
                "nm": "project-root",
                "tp": "dir",
                "ch": [
                    {"nm": "backend", "tp": "dir", "ch": []},
                    {"nm": "frontend", "tp": "dir", "ch": []},
                ]
            },
            "cm": {
                "AuthService": ["backend/app/api/v1/auth.py", "backend/app/services/auth_service.py"]
            },
            "cv": ["snake_case 파일명", "도메인별 디렉토리"],
        })

        mock_res = MagicMock()
        mock_res.parsed = mock_output

        sa_bundle = {"data": {"components": [{"name": "AuthService"}]}}
        state = self._make_state({
            "sa_arch_bundle": sa_bundle,
            "pm_bundle": {"data": {"tech_stacks": [{"name": "FastAPI"}]}},
            "merged_project": {"plan": {"requirements_rtm": []}},
        })

        with patch("pipeline.domain.sa.nodes.sa_project_structure.call_structured", return_value=mock_res):
            result = sa_project_structure_node(state)

        assert "sa_project_structure_output" in result
        assert "sa_arch_bundle" in result
        assert "project_structure" in result["sa_arch_bundle"]["data"]
        assert result["current_step"] == "sa_project_structure_done"

        # component_mapping 확인
        proj_struct = result["sa_project_structure_output"]
        assert "component_mapping" in proj_struct
        assert "AuthService" in proj_struct["component_mapping"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
