from __future__ import annotations

import py_compile
import subprocess
from pathlib import Path
from types import SimpleNamespace

from orchestration.executor import execute_pipeline
from pipeline.domain.dev.nodes.backend_agent import develop_backend_agent_node
from pipeline.domain.dev.nodes.backend_codegen import develop_backend_codegen_node
from pipeline.domain.dev.nodes.backend_codegen_verifier import (
    _extract_failed_file_paths,
    _semantic_slices,
    develop_backend_codegen_repair_node,
    develop_backend_codegen_verifier_node,
    develop_backend_runtime_blocker_node,
)
from pipeline.domain.dev.nodes.backend_qa_agent import develop_backend_qa_agent_node
from pipeline.domain.dev.nodes.branch_pr_orchestrator import develop_branch_pr_orchestrator_node
from pipeline.domain.dev.nodes.domain_gates import develop_backend_domain_gate_node
from pipeline.domain.dev.nodes.feature_completion import develop_feature_completion_node
from pipeline.domain.dev.nodes.fallback_handler import develop_fallback_handler_node
from pipeline.domain.dev.nodes.feature_queue_controller import develop_feature_queue_controller_node
from pipeline.domain.dev.nodes.frontend_agent import develop_frontend_agent_node
from pipeline.domain.dev.nodes.frontend_codegen import develop_frontend_codegen_node
from pipeline.domain.dev.nodes.frontend_codegen_verifier import (
    develop_frontend_codegen_repair_node,
    develop_frontend_codegen_reverifier_node,
    develop_frontend_codegen_verifier_node,
    develop_frontend_runtime_blocker_node,
)
from pipeline.domain.dev.nodes.frontend_qa_agent import develop_frontend_qa_agent_node
from pipeline.domain.dev.nodes.fullstack_runtime_verifier import develop_fullstack_runtime_verifier_node
from pipeline.domain.dev.nodes.global_sync_gate import develop_global_fe_sync_gate_node
from pipeline.domain.dev.nodes.integration_qa_gate import develop_integration_qa_gate_node
from pipeline.domain.dev.nodes.loop_controller import develop_loop_controller_node
from pipeline.domain.dev.nodes.main_agent import develop_main_agent_node
from pipeline.domain.dev.nodes.uiux_agent import develop_uiux_agent_node
from pipeline.domain.dev.nodes.uiux_qa_agent import develop_uiux_qa_agent_node
from pipeline.domain.dev.schemas import DevTask
from pipeline.orchestration.dev_graphs import (
    _develop_rework_dispatcher,
    _route_backend_codegen_verification,
    _route_frontend_codegen_verification,
    _route_integration_qa_gate,
    _route_rework_dispatcher,
    get_develop_pipeline,
)

# --- 유틸리티 함수: Git 작업 및 환경 초기화 ---
def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "README.md").write_text("# fixture\n", encoding="utf-8")
    _git(["init"], path)
    _git(["config", "user.email", "test@example.com"], path)
    _git(["config", "user.name", "Test User"], path)
    _git(["add", "README.md"], path)
    _git(["commit", "-m", "initial"], path)
    _git(["branch", "develop"], path)
    return path


def _base_state(source_dir: Path) -> dict:
    """테스트에 사용될 기본 파이프라인 상태(State) 정의"""
    return {
        "run_id": "20260504_000000",
        "source_dir": str(source_dir),
        "development_request": "사용자 로그인 API와 화면을 추가한다",
        "previous_result": {"metadata": {"session_id": "source_session"}},
        "requirements_rtm": [ # PM Layer에서 전달된 요구사항 (FEAT_XXX)
            {
                "id": "FEAT_001",
                "description": "사용자는 이메일과 비밀번호로 로그인할 수 있어야 한다.",
                "priority": "must-have",
            }
        ],
        "components": [ # SA Layer에서 설계된 컴포넌트 목록
            {"name": "LoginPage", "domain": "frontend"},
            {"name": "AuthService", "domain": "backend"},
        ],
        "apis": [{"endpoint": "POST /api/auth/login"}], # SA 설계 API 명세
        "tables": [{"table_name": "users"}], # SA 설계 DB 테이블 명세
        "project_overview": {"summary": "로그인 기능이 필요한 서비스"},
        "pm_overview": {},
        "sa_overview": {},
        "sa_artifacts": {},
    }


# Test modules import this fixture module with `import *`. Python excludes
# underscore-prefixed helpers by default, so export them explicitly.
__all__ = [name for name in globals() if not name.startswith("__")]

# --- 단위 테스트: 각 도메인 및 노드별 로직 검증 ---
