"""
GitHub Connector: PyGithub 래퍼.
get_repo, get_commits, get_issues, get_contributors, get_wiki_pages,
create_or_update_wiki_page 지원.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class CommitInfo:
    sha: str
    message: str
    author: str
    date: str
    url: str
    files_changed: int = 0


@dataclass
class IssueInfo:
    number: int
    title: str
    state: str
    author: str
    created_at: str
    labels: list[str] = field(default_factory=list)
    body: str = ""
    url: str = ""


@dataclass
class ContributorInfo:
    login: str
    contributions: int
    avatar_url: str = ""


class GitHubConnector:
    def __init__(self, token: str):
        from github import Github  # type: ignore
        self._gh = Github(token)
        self._token = token

    def get_repo(self, owner: str, repo: str):
        return self._gh.get_repo(f"{owner}/{repo}")

    def get_commits(self, owner: str, repo: str, branch: str = "main", limit: int = 20) -> list[CommitInfo]:
        repo_obj = self.get_repo(owner, repo)
        commits = []
        for c in repo_obj.get_commits(sha=branch)[:limit]:
            commits.append(CommitInfo(
                sha=c.sha[:7],
                message=c.commit.message.split("\n")[0],
                author=c.commit.author.name,
                date=c.commit.author.date.isoformat(),
                url=c.html_url,
                files_changed=c.stats.total if c.stats else 0,
            ))
        return commits

    def get_issues(self, owner: str, repo: str, state: str = "open", limit: int = 30) -> list[IssueInfo]:
        repo_obj = self.get_repo(owner, repo)
        issues = []
        for issue in repo_obj.get_issues(state=state)[:limit]:
            issues.append(IssueInfo(
                number=issue.number,
                title=issue.title,
                state=issue.state,
                author=issue.user.login if issue.user else "",
                created_at=issue.created_at.isoformat(),
                labels=[lbl.name for lbl in issue.labels],
                body=(issue.body or "")[:300],
                url=issue.html_url,
            ))
        return issues

    def get_contributors(self, owner: str, repo: str, limit: int = 20) -> list[ContributorInfo]:
        repo_obj = self.get_repo(owner, repo)
        contributors = []
        for c in repo_obj.get_contributors()[:limit]:
            contributors.append(ContributorInfo(
                login=c.login,
                contributions=c.contributions,
                avatar_url=c.avatar_url,
            ))
        return contributors

    def get_wiki_pages(self, owner: str, repo: str) -> list[dict]:
        """Wiki 페이지 목록 (git clone 방식이 필요해 제목만 추출)."""
        import requests
        headers = {"Authorization": f"token {self._token}", "Accept": "application/json"}
        url = f"https://api.github.com/repos/{owner}/{repo}/pages"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return [resp.json()]
        return []

    def create_or_update_wiki_page(self, owner: str, repo: str, title: str, content: str) -> bool:
        """GitHub Wiki 페이지 생성/업데이트 (Git API 방식)."""
        import base64
        import requests

        headers = {
            "Authorization": f"token {self._token}",
            "Accept": "application/vnd.github.v3+json",
        }
        # Wiki는 별도 git repo로 접근: {owner}/{repo}.wiki.git
        wiki_api = f"https://api.github.com/repos/{owner}/{repo}/wiki/{title.replace(' ', '-')}"
        payload = {"message": f"Update {title}", "content": base64.b64encode(content.encode()).decode()}

        # PUT (생성/수정)
        resp = requests.put(wiki_api, json=payload, headers=headers, timeout=15)
        return resp.status_code in (200, 201)

    def _ensure_label(self, owner: str, repo: str, label: str, headers: dict) -> None:
        """라벨이 없으면 자동 생성."""
        import requests
        labels_url = f"https://api.github.com/repos/{owner}/{repo}/labels"
        resp = requests.get(f"{labels_url}/{label}", headers=headers, timeout=10)
        if resp.status_code == 404:
            requests.post(labels_url, json={"name": label, "color": "0075ca"}, headers=headers, timeout=10)

    def publish_markdown_to_wiki(self, owner: str, repo: str, page_title: str, markdown: str) -> dict:
        """Issues 방식으로 설계 문서를 퍼블리시 (wiki API 제한 우회용)."""
        import requests
        headers = {
            "Authorization": f"token {self._token}",
            "Accept": "application/vnd.github.v3+json",
        }

        # 토큰 유효성 사전 확인
        me_resp = requests.get("https://api.github.com/user", headers=headers, timeout=10)
        if me_resp.status_code == 401:
            raise ValueError("GitHub 토큰이 유효하지 않습니다. 설정에서 토큰을 확인하세요.")
        if me_resp.status_code not in (200, 304):
            raise ValueError(f"GitHub API 오류: HTTP {me_resp.status_code}")

        # design-doc 라벨 자동 생성
        self._ensure_label(owner, repo, "design-doc", headers)

        # 기존 issue에서 같은 제목 탐색 후 업데이트, 없으면 생성
        list_url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        resp = requests.get(list_url, headers=headers, params={"state": "open", "labels": "design-doc"}, timeout=10)
        if resp.status_code not in (200, 304):
            raise ValueError(f"이슈 목록 조회 실패: HTTP {resp.status_code} — {resp.text[:200]}")

        existing_number = None
        for issue in resp.json():
            if issue.get("title") == page_title:
                existing_number = issue["number"]
                break

        body = f"<!-- navigator-design-doc -->\n\n{markdown}"
        if existing_number:
            patch_url = f"{list_url}/{existing_number}"
            r = requests.patch(patch_url, json={"body": body}, headers=headers, timeout=10)
            if r.status_code not in (200, 201):
                raise ValueError(f"이슈 업데이트 실패: HTTP {r.status_code} — {r.text[:200]}")
            return {"action": "updated", "number": existing_number, "success": True}
        else:
            r = requests.post(list_url, json={"title": page_title, "body": body, "labels": ["design-doc"]}, headers=headers, timeout=10)
            if r.status_code not in (200, 201):
                raise ValueError(f"이슈 생성 실패: HTTP {r.status_code} — {r.text[:200]}")
            data = r.json()
            return {"action": "created", "number": data.get("number"), "success": True}


def verify_token(token: str) -> dict:
    """토큰 유효성 확인."""
    try:
        from github import Github, GithubException  # type: ignore
        gh = Github(token)
        user = gh.get_user()
        return {"valid": True, "login": user.login, "name": user.name or user.login}
    except Exception as e:
        return {"valid": False, "error": str(e)}
