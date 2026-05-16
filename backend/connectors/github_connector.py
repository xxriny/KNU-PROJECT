"""
GitHub Connector: githubkit (Octokit-style Python SDK) 래퍼.
get_repo, get_commits, get_issues, get_contributors,
publish_markdown_to_wiki 지원.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from githubkit import GitHub
from observability.logger import get_logger

logger = get_logger()

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
        self._token = token
        self._gh = GitHub(token)

    def get_commits(self, owner: str, repo: str, branch: str = "main", limit: int = 20) -> list[CommitInfo]:
        """최신 커밋 목록 조회."""
        try:
            commits_data = self._gh.rest.repos.list_commits(
                owner=owner, repo=repo, sha=branch, per_page=limit
            ).parsed_data
            
            results = []
            for c in commits_data:
                results.append(CommitInfo(
                    sha=c.sha[:7],
                    message=c.commit.message.split("\n")[0],
                    author=c.commit.author.name if c.commit.author else "Unknown",
                    date=c.commit.author.date if c.commit.author else "",
                    url=c.html_url,
                    files_changed=0, # 상세 통계는 추가 호출 필요하므로 생략
                ))
            return results
        except Exception as e:
            logger.error(f"[GitHubConnector] get_commits failed: {e}")
            return []

    def get_issues(self, owner: str, repo: str, state: str = "open", limit: int = 30) -> list[IssueInfo]:
        """이슈 목록 조회."""
        try:
            issues_data = self._gh.rest.issues.list_for_repo(
                owner=owner, repo=repo, state=state, per_page=limit
            ).parsed_data
            
            results = []
            for issue in issues_data:
                # pull_request가 포함될 수 있으므로 필터링 (issue 객체에 pull_request 필드가 있으면 PR임)
                if getattr(issue, "pull_request", None):
                    continue
                    
                results.append(IssueInfo(
                    number=issue.number,
                    title=issue.title,
                    state=issue.state,
                    author=issue.user.login if issue.user else "Unknown",
                    created_at=issue.created_at.isoformat(),
                    labels=[lbl.name for lbl in issue.labels if hasattr(lbl, 'name')] if isinstance(issue.labels, list) else [],
                    body=(issue.body or "")[:300],
                    url=issue.html_url,
                ))
            return results
        except Exception as e:
            logger.error(f"[GitHubConnector] get_issues failed: {e}")
            return []

    def get_contributors(self, owner: str, repo: str, limit: int = 20) -> list[ContributorInfo]:
        """기여자 목록 조회."""
        try:
            contributors = self._gh.rest.repos.list_contributors(
                owner=owner, repo=repo, per_page=limit
            ).parsed_data
            
            results = []
            for c in contributors:
                results.append(ContributorInfo(
                    login=c.login if c.login else "Unknown",
                    contributions=c.contributions,
                    avatar_url=c.avatar_url if hasattr(c, 'avatar_url') else "",
                ))
            return results
        except Exception as e:
            logger.error(f"[GitHubConnector] get_contributors failed: {e}")
            return []

    def _ensure_label(self, owner: str, repo: str, label_name: str) -> None:
        """라벨이 없으면 자동 생성."""
        try:
            self._gh.rest.issues.get_label(owner=owner, repo=repo, name=label_name)
        except Exception:
            try:
                self._gh.rest.issues.create_label(
                    owner=owner, repo=repo, name=label_name, color="0075ca"
                )
            except Exception as e:
                logger.warning(f"[GitHubConnector] Failed to create label {label_name}: {e}")

    def publish_markdown_to_wiki(self, owner: str, repo: str, page_title: str, markdown: str) -> dict:
        """Issues 방식으로 설계 문서를 퍼블리시 (Wiki 대용)."""
        try:
            # 1. 토큰 유효성 및 사용자 확인
            user = self._gh.rest.users.get_authenticated().parsed_data
            
            # 2. 라벨 확인/생성
            self._ensure_label(owner, repo, "design-doc")
            
            # 3. 기존 이슈 탐색
            issues = self._gh.rest.issues.list_for_repo(
                owner=owner, repo=repo, state="open", labels="design-doc"
            ).parsed_data
            
            existing_issue = next((i for i in issues if i.title == page_title), None)
            
            body = f"<!-- navigator-design-doc -->\n\n{markdown}"
            
            if existing_issue:
                # 업데이트
                self._gh.rest.issues.update(
                    owner=owner, repo=repo, issue_number=existing_issue.number, body=body
                )
                return {"action": "updated", "number": existing_issue.number, "success": True}
            else:
                # 신규 생성
                new_issue = self._gh.rest.issues.create(
                    owner=owner, repo=repo, title=page_title, body=body, labels=["design-doc"]
                ).parsed_data
                return {"action": "created", "number": new_issue.number, "success": True}
                
        except Exception as e:
            logger.exception(f"[GitHubConnector] publish_markdown_to_wiki failed: {e}")
            raise ValueError(f"GitHub 퍼블리시 실패: {str(e)}")


def verify_token(token: str) -> dict:
    """토큰 유효성 확인."""
    try:
        with GitHub(token) as gh:
            user = gh.rest.users.get_authenticated().parsed_data
            return {"valid": True, "login": user.login, "name": getattr(user, "name", user.login) or user.login}
    except Exception as e:
        return {"valid": False, "error": str(e)}
