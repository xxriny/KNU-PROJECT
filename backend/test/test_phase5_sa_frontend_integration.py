"""
Phase 5 (SA 프론트엔드 탭 + result_shaper 패스스루): 통합 검증
- result_shaper.py sa_test_strategy / sa_project_structure 패스스루 확인
- SATestStrategyTab, ProjectStructureTab 컴포넌트 파일 존재 확인
- uiConstants.js 탭 등록 확인
- ResultViewer.jsx 탭 임포트 확인
"""

import os
import sys
import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(os.path.dirname(BACKEND_DIR), "src")
sys.path.insert(0, BACKEND_DIR)


class TestResultShaper:
    """result_shaper.py sa_test_strategy / sa_project_structure 패스스루"""

    def test_sa_test_strategy_passthrough(self):
        from result_shaping.result_shaper import shape_result

        test_strategy = {
            "test_philosophy": "단위 테스트 우선",
            "risk_zones": [{"component_name": "AuthService", "risk_level": "high", "reason": "인증", "mitigation": "Mock"}],
            "unit_specs": [],
            "integration_specs": [],
            "system_specs": [],
            "acceptance_specs": [],
            "test_data_strategy": "Faker",
            "automation_priority": ["단위 먼저"],
        }

        raw = {
            "sa_output": {
                "data": {
                    "components": [],
                    "apis": [],
                    "tables": [],
                    "test_strategy": test_strategy,
                }
            }
        }

        result = shape_result(raw)
        assert "sa_test_strategy" in result
        assert result["sa_test_strategy"]["test_philosophy"] == "단위 테스트 우선"

    def test_sa_project_structure_passthrough(self):
        from result_shaping.result_shaper import shape_result

        project_structure = {
            "tree": {"name": "project-root", "type_": "dir", "children": []},
            "component_mapping": {"AuthService": ["backend/auth.py"]},
            "conventions": ["snake_case 파일명"],
        }

        raw = {
            "sa_output": {
                "data": {
                    "components": [],
                    "apis": [],
                    "tables": [],
                    "project_structure": project_structure,
                }
            }
        }

        result = shape_result(raw)
        assert "sa_project_structure" in result
        assert "component_mapping" in result["sa_project_structure"]
        assert "AuthService" in result["sa_project_structure"]["component_mapping"]

    def test_shape_result_without_new_nodes_still_works(self):
        """신규 노드 데이터 없어도 shape_result가 정상 동작해야 함"""
        from result_shaping.result_shaper import shape_result
        raw = {
            "sa_output": {
                "data": {"components": [], "apis": [], "tables": []}
            }
        }
        result = shape_result(raw)
        assert "sa_test_strategy" not in result
        assert "sa_project_structure" not in result
        assert "sa_output" in result


class TestFrontendFiles:
    """프론트엔드 컴포넌트 파일 존재 확인"""

    def _frontend(self, *parts):
        return os.path.join(FRONTEND_DIR, *parts)

    def test_sa_test_strategy_tab_exists(self):
        path = self._frontend("components", "resultViewer", "SATestStrategyTab.jsx")
        assert os.path.exists(path), f"SATestStrategyTab.jsx 없음: {path}"

    def test_project_structure_tab_exists(self):
        path = self._frontend("components", "resultViewer", "ProjectStructureTab.jsx")
        assert os.path.exists(path), f"ProjectStructureTab.jsx 없음: {path}"

    def test_auth_login_screen_exists(self):
        path = self._frontend("components", "auth", "LoginScreen.jsx")
        assert os.path.exists(path), f"LoginScreen.jsx 없음: {path}"

    def test_auth_slice_exists(self):
        path = self._frontend("store", "slices", "authSlice.js")
        assert os.path.exists(path), f"authSlice.js 없음: {path}"

    def test_ui_constants_has_new_tabs(self):
        path = self._frontend("constants", "uiConstants.js")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "sa_test_strategy" in content, "sa_test_strategy 탭 등록 누락"
        assert "project_structure" in content, "project_structure 탭 등록 누락"
        assert "ShieldCheck" in content, "ShieldCheck 아이콘 누락"
        assert "FolderTree" in content, "FolderTree 아이콘 누락"

    def test_result_viewer_imports_new_tabs(self):
        path = self._frontend("components", "ResultViewer.jsx")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "SATestStrategyTab" in content, "SATestStrategyTab 임포트 누락"
        assert "ProjectStructureTab" in content, "ProjectStructureTab 임포트 누락"
        assert "sa_test_strategy" in content
        assert "project_structure" in content

    def test_app_jsx_has_login_screen(self):
        path = self._frontend("App.jsx")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "LoginScreen" in content
        assert "authToken" in content
        assert "authChecked" in content

    def test_use_app_store_has_auth_slice(self):
        path = self._frontend("store", "useAppStore.js")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "createAuthSlice" in content
        assert "authSlice" in content


class TestSATestStrategyTabContent:
    """SATestStrategyTab.jsx 내용 검증"""

    def _read_tab(self):
        path = os.path.join(FRONTEND_DIR, "components", "resultViewer", "SATestStrategyTab.jsx")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_has_subtabs(self):
        content = self._read_tab()
        assert "unit" in content
        assert "integration" in content
        assert "system" in content
        assert "acceptance" in content

    def test_reads_result_data(self):
        content = self._read_tab()
        assert "sa_test_strategy" in content
        assert "sa_output" in content

    def test_has_risk_zone_card(self):
        content = self._read_tab()
        assert "RiskZoneCard" in content or "risk_zones" in content


class TestProjectStructureTabContent:
    """ProjectStructureTab.jsx 내용 검증"""

    def _read_tab(self):
        path = os.path.join(FRONTEND_DIR, "components", "resultViewer", "ProjectStructureTab.jsx")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_has_tree_node(self):
        content = self._read_tab()
        assert "TreeNode" in content

    def test_has_component_mapping_view(self):
        content = self._read_tab()
        assert "component_mapping" in content
        assert "MappingCard" in content or "mapping" in content.lower()

    def test_has_conventions_section(self):
        content = self._read_tab()
        assert "conventions" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
