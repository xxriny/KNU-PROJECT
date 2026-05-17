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

    def publish_markdown_to_issue(self, owner: str, repo: str, page_title: str, markdown: str, label: str = "design-doc") -> dict:
        """SA 설계 문서를 GitHub Issue로 퍼블리시한다.

        같은 제목의 열린 이슈가 있으면 본문을 업데이트하고,
        없으면 신규 생성한다.
        """
        self._ensure_label(owner, repo, label)
        try:
            # 같은 제목의 열린 이슈 탐색
            existing_issues = self._gh.rest.issues.list_for_repo(
                owner=owner, repo=repo, state="open", labels=label, per_page=50
            ).parsed_data
            target = next((i for i in existing_issues if i.title == page_title), None)

            if target:
                self._gh.rest.issues.update(
                    owner=owner, repo=repo, issue_number=target.number, body=markdown
                )
                return {"action": "updated", "number": target.number, "success": True}
            else:
                created = self._gh.rest.issues.create(
                    owner=owner, repo=repo, title=page_title, body=markdown, labels=[label]
                ).parsed_data
                return {"action": "created", "number": created.number, "success": True}
        except Exception as e:
            logger.exception(f"[GitHubConnector] publish_to_issue failed: {e}")
            raise ValueError(f"GitHub Issue 퍼블리시 실패: {str(e)}")

    def publish_markdown_to_wiki(self, owner: str, repo: str, page_title: str, markdown: str) -> dict:
        """GitHub Wiki Pages REST API로 설계 문서를 퍼블리시한다.

        GitHub Wiki는 {repo}.wiki Git 레포이지만, Contents API는 해당 레포에
        접근 불가(404). 대신 GitHub Wiki Pages API를 사용한다:
          POST  /repos/{owner}/{repo}/wiki/pages  (신규)
          PATCH /repos/{owner}/{repo}/wiki/pages/{slug} (수정)

        Wiki가 활성화되지 않은 레포는 GitHub UI에서 먼저 켜야 한다.
        """
        import re
        import requests

        api_base = "https://api.github.com"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        # page slug: GitHub가 title을 소문자+하이픈으로 변환하는 규칙
        slug = re.sub(r"[^a-zA-Z0-9가-힣]+", "-", page_title).strip("-").lower()

        try:
            # 기존 페이지 존재 여부 확인
            get_resp = requests.get(
                f"{api_base}/repos/{owner}/{repo}/wiki/pages/{slug}",
                headers=headers, timeout=15,
            )

            if get_resp.status_code == 200:
                # 기존 페이지 수정
                patch_resp = requests.patch(
                    f"{api_base}/repos/{owner}/{repo}/wiki/pages/{slug}",
                    headers=headers, timeout=15,
                    json={"title": page_title, "content": markdown, "format": "markdown"},
                )
                patch_resp.raise_for_status()
                return {"action": "updated", "page": slug, "success": True}
            else:
                # 신규 페이지 생성
                post_resp = requests.post(
                    f"{api_base}/repos/{owner}/{repo}/wiki/pages",
                    headers=headers, timeout=15,
                    json={"title": page_title, "content": markdown, "format": "markdown"},
                )
                post_resp.raise_for_status()
                return {"action": "created", "page": slug, "success": True}

        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            body = e.response.text[:300] if e.response is not None else ""
            logger.error(f"[GitHubConnector] wiki API {status}: {body}")
            if status == 404:
                raise ValueError(
                    f"GitHub Wiki 퍼블리시 실패(404): 레포 '{owner}/{repo}'의 Wiki가 비활성화 상태입니다. "
                    "GitHub 레포 Settings → Features → Wikis를 켜세요."
                )
            raise ValueError(f"GitHub Wiki 퍼블리시 실패({status}): {body}")
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
