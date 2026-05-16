"""
Phase 4 (GitHub 통합): 통합 검증
- github_connector.py verify_token (mock) 구조 확인
- wiki_publisher.py build_design_doc_markdown 검증
- commit_analyzer.py analyze_commits 검증
- REST endpoint 등록 확인
- 프론트엔드 파일 존재 확인
"""

import os
import sys
import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(os.path.dirname(BACKEND_DIR), "src")
sys.path.insert(0, BACKEND_DIR)


# ── GitHub Connector (구조 확인, 실제 API 미호출) ─────────────────────────────

class TestGitHubConnectorStructure:
    def test_import_connector(self):
        from connectors.github_connector import GitHubConnector, verify_token, CommitInfo, IssueInfo, ContributorInfo

    def test_commit_info_dataclass(self):
        from connectors.github_connector import CommitInfo
        c = CommitInfo(sha="abc1234", message="init commit", author="dev", date="2026-01-01", url="http://x")
        assert c.sha == "abc1234"
        assert c.files_changed == 0

    def test_issue_info_dataclass(self):
        from connectors.github_connector import IssueInfo
        i = IssueInfo(number=1, title="Bug fix", state="open", author="alice", created_at="2026-01-01")
        assert i.number == 1
        assert i.labels == []

    def test_contributor_info_dataclass(self):
        from connectors.github_connector import ContributorInfo
        c = ContributorInfo(login="alice", contributions=42)
        assert c.contributions == 42
        assert c.avatar_url == ""


# ── Wiki Publisher ────────────────────────────────────────────────────────────

class TestWikiPublisher:
    def test_build_design_doc_markdown_basic(self):
        from pipeline.domain.agile.wiki_publisher import build_design_doc_markdown
        result_data = {
            "sa_output": {
                "data": {
                    "components": [{"name": "AuthService", "type": "service", "dependencies": ["DB"]}],
                    "apis": [{"endpoint": "/api/login", "method": "POST", "description": "로그인"}],
                    "tables": [{"name": "users", "fields": [{"name": "id", "type": "uuid"}, {"name": "email", "type": "text"}]}],
                }
            }
        }
        md = build_design_doc_markdown(result_data, project_name="TestProject")
        assert "TestProject" in md
        assert "AuthService" in md
        assert "/api/login" in md
        assert "users" in md

    def test_build_design_doc_markdown_empty(self):
        from pipeline.domain.agile.wiki_publisher import build_design_doc_markdown
        md = build_design_doc_markdown({})
        assert isinstance(md, str)
        assert len(md) > 0

    def test_markdown_has_sections(self):
        from pipeline.domain.agile.wiki_publisher import build_design_doc_markdown
        md = build_design_doc_markdown({"sa_output": {"data": {"components": [], "apis": [], "tables": []}}})
        assert "컴포넌트 구조" in md
        assert "API 명세" in md
        assert "데이터베이스" in md


# ── Commit Analyzer ────────────────────────────────────────────────────────────

class TestCommitAnalyzer:
    def _make_commits(self):
        from connectors.github_connector import CommitInfo
        return [
            CommitInfo(sha="aaa", message="feat: add login", author="alice", date="2026-01-01", url=""),
            CommitInfo(sha="bbb", message="fix: auth bug", author="bob", date="2026-01-02", url=""),
            CommitInfo(sha="ccc", message="feat: user profile", author="alice", date="2026-01-03", url=""),
            CommitInfo(sha="ddd", message="refactor: cleanup", author="charlie", date="2026-01-04", url=""),
        ]

    def test_analyze_commits_basic(self):
        from pipeline.domain.agile.commit_analyzer import analyze_commits
        commits = self._make_commits()
        analytics = analyze_commits(commits)
        assert analytics.total_commits == 4
        assert "alice" in analytics.by_author
        assert analytics.by_author["alice"] == 2

    def test_analyze_commits_by_date(self):
        from pipeline.domain.agile.commit_analyzer import analyze_commits
        analytics = analyze_commits(self._make_commits())
        assert "2026-01-01" in analytics.by_date

    def test_analyze_commits_keywords(self):
        from pipeline.domain.agile.commit_analyzer import analyze_commits
        analytics = analyze_commits(self._make_commits())
        assert len(analytics.top_keywords) > 0

    def test_analyze_commits_empty(self):
        from pipeline.domain.agile.commit_analyzer import analyze_commits
        analytics = analyze_commits([])
        assert analytics.total_commits == 0
        assert analytics.by_author == {}

    def test_analyze_commits_recent(self):
        from pipeline.domain.agile.commit_analyzer import analyze_commits
        analytics = analyze_commits(self._make_commits())
        assert len(analytics.recent_commits) <= 10
        assert analytics.recent_commits[0]["author"] in {"alice", "bob", "charlie"}


# ── REST Endpoints ────────────────────────────────────────────────────────────

class TestGitHubRESTEndpoints:
    def test_github_endpoints_registered(self):
        from transport.rest_handler import rest_router
        paths = [r.path for r in rest_router.routes]
        assert "/api/github/verify" in paths, f"/api/github/verify 누락"
        assert "/api/github/publish" in paths, f"/api/github/publish 누락"
        assert "/api/github/analytics" in paths, f"/api/github/analytics 누락"
        assert "/api/github/issues" in paths, f"/api/github/issues 누락"

    def test_github_verify_request_model(self):
        from transport.rest_handler import GitHubVerifyRequest
        req = GitHubVerifyRequest(token="tok", owner="alice", repo="myrepo")
        assert req.owner == "alice"

    def test_github_publish_request_defaults(self):
        from transport.rest_handler import GitHubPublishRequest
        req = GitHubPublishRequest(token="tok", owner="alice", repo="myrepo", result_data={})
        assert req.page_title == "SA 설계 문서"
        assert req.project_name == "Project"

    def test_github_analytics_request_defaults(self):
        from transport.rest_handler import GitHubAnalyticsRequest
        req = GitHubAnalyticsRequest(token="tok", owner="alice", repo="myrepo")
        assert req.branch == "main"
        assert req.limit == 30


# ── Frontend Files ────────────────────────────────────────────────────────────

class TestGitHubFrontendFiles:
    def _fe(self, *parts):
        return os.path.join(FRONTEND_DIR, *parts)

    def test_github_dashboard_exists(self):
        path = self._fe("components", "github", "GitHubDashboard.jsx")
        assert os.path.exists(path), f"GitHubDashboard.jsx 없음: {path}"

    def test_github_slice_exists(self):
        path = self._fe("store", "slices", "githubSlice.js")
        assert os.path.exists(path), f"githubSlice.js 없음: {path}"

    def test_settings_panel_has_github(self):
        path = self._fe("components", "SettingsPanel.jsx")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "githubToken" in content
        assert "githubOwner" in content
        assert "githubRepo" in content
        assert "setGithubSettings" in content

    def test_result_viewer_has_github_dashboard(self):
        path = self._fe("components", "ResultViewer.jsx")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "GitHubDashboard" in content
        assert "github_dashboard" in content

    def test_ui_constants_has_github(self):
        path = self._fe("constants", "uiConstants.js")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "github_dashboard" in content
        assert "Github" in content

    def test_github_dashboard_content(self):
        path = self._fe("components", "github", "GitHubDashboard.jsx")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "/api/github/analytics" in content
        assert "/api/github/issues" in content
        assert "/api/github/publish" in content
        assert "githubToken" in content

    def test_use_app_store_has_github_slice(self):
        path = self._fe("store", "useAppStore.js")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "createGithubSlice" in content
        assert "githubSlice" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
