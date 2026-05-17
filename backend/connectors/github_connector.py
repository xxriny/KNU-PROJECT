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
                    date=c.commit.author.date.isoformat() if (c.commit.author and c.commit.author.date) else "",
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

    def list_branches(self, owner: str, repo: str, limit: int = 50) -> list[dict]:
        """브랜치 목록 조회."""
        try:
            branches = self._gh.rest.repos.list_branches(
                owner=owner, repo=repo, per_page=limit
            ).parsed_data
            return [{"name": b.name, "protected": getattr(b, "protected", False)} for b in branches]
        except Exception as e:
            logger.error(f"[GitHubConnector] list_branches failed: {e}")
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
        """GitHub Wiki에 설계 문서를 퍼블리시한다.

        Wiki는 별도 git 레포({owner}/{repo}.wiki)로 관리된다.
        Git Data API로 파일을 생성/업데이트해 Wiki 페이지를 추가한다.
        Wiki가 활성화되지 않은 레포는 먼저 GitHub UI에서 Wiki를 켜야 한다.
        """
        import base64

        safe_title = page_title.replace("/", "-").replace(" ", "-")
        filename = f"{safe_title}.md"
        wiki_owner = owner
        wiki_repo = f"{repo}.wiki"

        try:
            content_b64 = base64.b64encode(markdown.encode("utf-8")).decode("ascii")

            # 기존 파일 확인 (SHA 필요)
            existing_sha = None
            try:
                existing = self._gh.rest.repos.get_content(
                    owner=wiki_owner, repo=wiki_repo, path=filename
                ).parsed_data
                if hasattr(existing, "sha"):
                    existing_sha = existing.sha
            except Exception:
                pass  # 새 파일

            kwargs = dict(
                owner=wiki_owner,
                repo=wiki_repo,
                path=filename,
                message=f"docs: {'update' if existing_sha else 'add'} {page_title}",
                content=content_b64,
            )
            if existing_sha:
                kwargs["sha"] = existing_sha
            self._gh.rest.repos.create_or_update_file_contents(**kwargs)
            action = "updated" if existing_sha else "created"
            return {"action": action, "page": filename, "success": True}

        except Exception as e:
            logger.exception(f"[GitHubConnector] publish_to_wiki failed: {e}")
            raise ValueError(f"GitHub Wiki 퍼블리시 실패: {str(e)}")


def verify_token(token: str) -> dict:
    """토큰 유효성 확인."""
    try:
        with GitHub(token) as gh:
            user = gh.rest.users.get_authenticated().parsed_data
            return {"valid": True, "login": user.login, "name": getattr(user, "name", user.login) or user.login}
    except Exception as e:
        return {"valid": False, "error": str(e)}
