"""
SA 설계 문서를 GitHub Issues (design-doc 라벨)로 퍼블리시.
result_data의 주요 아티팩트를 Markdown으로 변환 후 업로드.
"""
from __future__ import annotations

from typing import Any


def _components_md(components: list[dict]) -> str:
    if not components:
        return "_컴포넌트 없음_\n"
    lines = ["| 컴포넌트 | 타입 | 의존성 |", "|---|---|---|"]
    for c in components[:20]:
        deps = ", ".join(c.get("dependencies", [])[:5]) or "-"
        lines.append(f"| {c.get('name', '?')} | {c.get('type', '?')} | {deps} |")
    return "\n".join(lines) + "\n"


def _apis_md(apis: list[dict]) -> str:
    if not apis:
        return "_API 없음_\n"
    lines = ["| 메서드 | 경로 | 설명 |", "|---|---|---|"]
    for a in apis[:20]:
        path = a.get("endpoint", a.get("path", "?"))
        lines.append(f"| {a.get('method', 'GET')} | {path} | {a.get('description', '')} |")
    return "\n".join(lines) + "\n"


def _tables_md(tables: list[dict]) -> str:
    if not tables:
        return "_테이블 없음_\n"
    lines = []
    for t in tables[:10]:
        lines.append(f"**{t.get('name', '?')}**")
        fields = t.get("fields", [])
        if fields:
            lines.append("| 필드 | 타입 |")
            lines.append("|---|---|")
            for f in fields[:10]:
                lines.append(f"| {f.get('name', '?')} | {f.get('type', '?')} |")
        lines.append("")
    return "\n".join(lines)


def build_design_doc_markdown(result_data: dict, project_name: str = "Project") -> str:
    """result_data에서 SA 설계 문서 Markdown 생성."""
    from datetime import datetime
    sa_data = (result_data.get("sa_output") or {})
    if isinstance(sa_data, dict) and "data" in sa_data:
        sa_data = sa_data["data"]

    components = sa_data.get("components", [])
    apis = sa_data.get("apis", [])
    tables = sa_data.get("tables", [])

    overview = result_data.get("sa_output", {})
    pm_data = result_data.get("pm_bundle", result_data.get("pm_output", {}))
    project_title = (
        pm_data.get("project_name") or
        result_data.get("project_name") or
        project_name
    )

    lines = [
        f"# {project_title} — SA 설계 문서",
        f"",
        f"> 자동 생성: {datetime.now().strftime('%Y-%m-%d %H:%M')} (NAVIGATOR)",
        f"",
        f"---",
        f"",
        f"## 컴포넌트 구조",
        f"",
        _components_md(components),
        f"",
        f"## API 명세",
        f"",
        _apis_md(apis),
        f"",
        f"## 데이터베이스 스키마",
        f"",
        _tables_md(tables),
    ]
    return "\n".join(lines)


def publish_to_github(
    result_data: dict,
    owner: str,
    repo: str,
    token: str,
    page_title: str = "SA 설계 문서",
    project_name: str = "Project",
) -> dict:
    from connectors.github_connector import GitHubConnector
    markdown = build_design_doc_markdown(result_data, project_name=project_name)
    connector = GitHubConnector(token)
    result = connector.publish_markdown_to_wiki(owner, repo, page_title, markdown)
    result["markdown_length"] = len(markdown)
    return result
