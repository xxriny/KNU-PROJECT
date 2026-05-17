"""
SA 설계 문서를 GitHub Issues (design-doc 라벨)로 퍼블리시.
result_data의 주요 아티팩트를 Markdown으로 변환 후 업로드.
"""
from __future__ import annotations

from typing import Any


def _components_md(components: list[dict]) -> str:
    if not components:
        return "> ⚠️ *현재 식별된 시스템 컴포넌트가 존재하지 않습니다.*\n"
    
    lines = [
        "### 📂 컴포넌트 레이아웃 및 책임 모델",
        "시스템은 기능의 격리 및 레이어드 아키텍처 패턴을 기반으로 하는 독립적인 모듈들로 설계되었습니다.",
        "",
        "| 컴포넌트 이름 | 레이어 / 도메인 | 주요 역할 및 의존 대상 컴포넌트 |",
        "| :--- | :--- | :--- |"
    ]
    for c in components[:20]:
        deps = ", ".join(f"`{d}`" for d in c.get("dependencies", [])[:5]) or "None (최상위 독립)"
        name = c.get('component_name') or c.get('name', '?')
        type_val = c.get('domain') or c.get('role') or c.get('type', '-')
        if isinstance(type_val, str):
            val_upper = type_val.upper().strip()
            if val_upper == 'B':
                type_val = 'Backend'
            elif val_upper == 'F':
                type_val = 'Frontend'
        lines.append(f"| **{name}** | `{type_val}` | {deps} |")
    return "\n".join(lines) + "\n"


def _apis_md(apis: list[dict]) -> str:
    if not apis:
        return "> ⚠️ *정의된 API 사양이 존재하지 않습니다.*\n"
    
    lines = [
        "### 🌐 웹 서비스 인터페이스 명세서 (REST API Reference)",
        "시스템 내부 및 외부와의 데이터 상호작용 및 통신 규약을 정의하는 API 사양입니다.",
        "",
        "| HTTP 메서드 | 엔드포인트 경로 | 인터페이스 정의 및 설명 |",
        "| :---: | :--- | :--- |"
    ]
    for a in apis[:20]:
        path = a.get("endpoint", a.get("path", "?"))
        method = a.get('method', 'GET').upper()
        desc = a.get('description', '-') or "세부 정의 예정"
        # Method별 뱃지 스타일 적용
        method_badge = f"`{method}`"
        lines.append(f"| {method_badge} | `{path}` | {desc} |")
    return "\n".join(lines) + "\n"


def _tables_md(tables: list[dict]) -> str:
    if not tables:
        return "> ⚠️ *구축된 데이터베이스 릴레이션이 없습니다.*\n"
    
    lines = [
        "### 💾 엔티티 관계 스키마 명세서 (Entity Schema)",
        "영속성 보존을 담당하는 시스템 데이터베이스 테이블 정의도입니다.",
        ""
    ]
    for t in tables[:10]:
        table_name = t.get('table_name') or t.get('name', '?')
        lines.append(f"#### 🏷️ 테이블 명세: `{table_name}`")
        lines.append("> * 비즈니스 도메인 영속성 확보를 담당하는 데이터 엔티티입니다.")
        lines.append("")
        
        fields = t.get('columns') or t.get('fields', [])
        if fields:
            lines.append("| 필드 속성 명 | 데이터 타입 | 제약 조건 및 특이사항 |")
            lines.append("| :--- | :---: | :--- |")
            for f in fields[:10]:
                col_name = f.get('column_name') or f.get('name', '?')
                constraint = f.get('constraint') or f.get('constraints') or '-'
                lines.append(f"| **{col_name}** | `{f.get('type', '?')}` | {constraint} |")
        lines.append("")
    return "\n".join(lines)


def build_design_doc_markdown(result_data: dict, project_name: str = "Project") -> str:
    """result_data에서 SA 설계 문서 Markdown 생성 (고급 보고서형 폴백)."""
    from datetime import datetime
    sa_data = (result_data.get("sa_output") or {})
    if isinstance(sa_data, dict) and "data" in sa_data:
        sa_data = sa_data["data"]

    components = sa_data.get("components", [])
    apis = sa_data.get("apis", [])
    tables = sa_data.get("tables", [])

    pm_data = result_data.get("pm_bundle", result_data.get("pm_output", {}))
    project_title = (
        pm_data.get("project_name") or
        result_data.get("project_name") or
        project_name
    )

    lines = [
        f"# 📋 {project_title} — 시스템 설계 및 소프트웨어 아키텍처 보고서",
        f"",
        f"> **발행 시각**: {datetime.now().strftime('%Y-%m-%d %H:%M')} | **분석 엔진**: NAVIGATOR Engine v2.0",
        f"",
        f"---",
        f"",
        f"## 1. 개요 (Executive Summary)",
        f"본 설계 보고서는 시스템의 확장성 및 결합 격리 수준을 극대화하여 장기적인 유지보수 비용을 단축하기 위해 분석된 **{project_title}**의 소프트웨어 아키텍처 명세서입니다.",
        f"비즈니스 도메인 및 요구사항의 변경 속도에 빠르게 대응하고 유연한 리팩토링 경로를 설정할 수 있도록 컴포넌트 레이아웃, 통신 인터페이스 규격서, 데이터 저장소 설계도면을 도식화하고 규격화하였습니다.",
        f"",
        f"---",
        f"",
        f"## 2. 도메인 모듈 및 컴포넌트 아키텍처",
        f"어플리케이션 레이어 간의 책임을 분명히 하고 유연한 확장을 보장하기 위해 분할 격리된 독립 컴포넌트 관계도입니다.",
        f"",
        _components_md(components),
        f"",
        f"---",
        f"",
        f"## 3. 웹 API 서비스 통신 사양",
        f"서비스 모듈 간 통신 및 클라이언트 요청을 효율적으로 안전하게 통제하기 위해 설계된 REST 인터페이스 규격입니다.",
        f"",
        _apis_md(apis),
        f"",
        f"---",
        f"",
        f"## 4. 데이터 영속성 레이어 구조",
        f"어플리케이션의 핵심 비즈니스 상태를 무결하게 영속적으로 보관하고 관리하기 위한 릴레이셔널 테이블 사양서입니다.",
        f"",
        _tables_md(tables),
        f"",
        f"---",
        f"",
        f"<footer>",
        f"<p align='center'><i>NAVIGATOR © 2026. All rights reserved. 본 아키텍처 산출물은 정합성 및 V-Model 요구사항 충족률 정방향 추적성을 확보하였습니다.</i></p>",
        f"</footer>"
    ]
    return "\n".join(lines)


def build_design_doc_markdown_llm(
    result_data: dict,
    project_name: str = "Project",
    api_key: str = "",
    model: str = "gemini-2.0-flash-lite",
) -> str:
    """LLM을 사용하여 result_data에서 격식 있는 고성능 소프트웨어 아키텍처 보고서를 생성."""
    import json
    import logging
    from langchain_google_genai import ChatGoogleGenerativeAI

    sa_data = result_data.get("sa_output") or {}
    if isinstance(sa_data, dict) and "data" in sa_data:
        sa_data = sa_data["data"]

    components_raw = sa_data.get("components", [])
    apis_raw = sa_data.get("apis", [])
    tables_raw = sa_data.get("tables", [])

    pm_data = result_data.get("pm_bundle", result_data.get("pm_output", {}))
    project_title = (
        pm_data.get("project_name") or
        result_data.get("project_name") or
        project_name
    )

    components = []
    for c in components_raw:
        type_val = c.get('domain') or c.get('role') or c.get('type', '-')
        if isinstance(type_val, str):
            val_upper = type_val.upper().strip()
            if val_upper == 'B':
                type_val = 'Backend'
            elif val_upper == 'F':
                type_val = 'Frontend'

        components.append({
            "name": c.get('component_name') or c.get('name', '?'),
            "domain": type_val,
            "role": c.get('role') or c.get('description', '-'),
            "dependencies": c.get("dependencies", [])
        })

    apis = []
    for a in apis_raw:
        apis.append({
            "endpoint": a.get("endpoint", a.get("path", "?")),
            "method": a.get('method', 'GET'),
            "description": a.get('description', '')
        })

    tables = []
    for t in tables_raw:
        columns = []
        for f in t.get('columns') or t.get('fields', []):
            columns.append({
                "name": f.get('column_name') or f.get('name', '?'),
                "type": f.get('type', '?'),
                "constraint": f.get('constraint') or f.get('constraints') or '-'
            })
        tables.append({
            "name": t.get('table_name') or t.get('name', '?'),
            "columns": columns
        })

    context = {
        "project_name": project_title,
        "components": components,
        "apis": apis,
        "tables": tables,
        "requirements_rtm": result_data.get("requirements_rtm", [])[:10],
    }

    system_prompt = (
        "# Role: Principal Software Architect & Expert Technical Writer\n\n"
        "당신은 전 세계적으로 손꼽히는 엔터프라이즈 시스템 설계를 총괄하는 수석 아키텍트이자 전문 Technical Writer입니다.\n"
        "제공되는 정밀한 소프트웨어 아키텍처 데이터를 분석하여 C-Level 임원들과 비즈니스 이해관계자, 개발 파트너사들이 극찬할 수준의 격식 있고 우아한 '시스템 아키텍처 설계 최종 명세 보고서'를 한국어(전문적인 존칭 어조)로 작성하십시오.\n\n"
        "## 작성 요구사항:\n"
        "1. **엄격하고 프로페셔널한 비즈니스 톤앤매너**를 문서 전체에 녹여내십시오.\n"
        "2. **단순 명세 표의 나열을 절대 지양하십시오**. 각 주요 챕터(컴포넌트, API, DB)마다 데이터 테이블을 삽입하기 전후에, 해당 설계의 목적, 아키텍처 관점에서의 패턴(Layered, Hexagonal 등), 이점 및 설계 고려 사항(성능, 보안, 확장성 등)을 줄글(Prose)로 최소 4~6문장 이상 깊이 있게 서술해야 진짜 보고서의 품격이 납니다.\n"
        "3. **Mermaid.js 다이어그램**을 활용하여 최소 1개 이상의 컴포넌트 상호작용 또는 데이터베이스 테이블 릴레이션을 마크다운 내에 포함시키십시오. (Mermaid 문법 오류가 생기지 않도록 정확히 구조화하여 작성하십시오.)\n"
        "4. GitHub-Flavored Markdown 스타일을 극한으로 사용하여 인용구(Blockquote), 요약 배너, 코드 스니펫 강조, 표 디자인 등을 수려하고 정밀하게 꾸미십시오.\n\n"
        "## 반드시 구현해야 할 문서 목차:\n"
        "1. **📋 문서 개요 (Executive Summary)**: 본 시스템의 핵심 비즈니스 지향점과 아키텍처 설계를 통한 리스크 최소화 방안을 서술식으로 조리 있게 작성하십시오.\n"
        "2. **📂 모듈 설계 및 컴포넌트 아키텍처 (Component Layout & Interactions)**: 컴포넌트들의 역할과 상호 격리성을 해설한 뒤 테이블 명세와 함께 시각화 다이어그램을 배치하십시오.\n"
        "3. **🌐 웹 인터페이스 및 통신 프로토콜 (REST API Specifications)**: 외부 시스템과의 확장 및 모듈 보안 연계를 고려하여 구축된 엔드포인트의 해설과 그룹핑 명세를 도출하십시오.\n"
        "4. **💾 영속성 저장소 데이터 모델 설계 (Database Relational Schema)**: 데이터의 안정성 및 영속을 위한 DB 테이블 스키마 제약 사항을 명세하고 각 릴레이션을 해설하십시오.\n"
        "5. **소프트웨어 요구사항 충족 및 추적성 (Traceability Summary)**: 아키텍처의 요구사항 정합성을 검토한 인사이트를 간략히 제공해 주십시오.\n\n"
        "## 절대 준수할 주의사항:\n"
        "- Markdown 코드블록 이외의 잡담, 서론, 결론(예: '네, 작성하겠습니다', '이상 명세입니다' 등)은 단 한 줄도 출력하지 마십시오. 오직 수려한 Markdown 본문만 뱉으십시오."
    )

    try:
        llm = ChatGoogleGenerativeAI(model=model, google_api_key=api_key, temperature=0.3)
        response = llm.invoke(f"{system_prompt}\n\n{json.dumps(context, ensure_ascii=False)}")
        content = response.content.strip()
        # 마크다운 백틱 래퍼 제거 처리
        if content.startswith("```markdown"):
            content = content[11:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        return content.strip()
    except Exception as e:
        logging.error(f"Error generating LLM markdown design doc: {e}. Falling back to standard markdown.")
        return build_design_doc_markdown(result_data, project_name)


def publish_to_github(
    result_data: dict,
    owner: str,
    repo: str,
    token: str,
    page_title: str = "SA 설계 문서",
    project_name: str = "Project",
    mode: str = "wiki",  # "wiki" | "issue"
    api_key: str = "",
    model: str = "gemini-2.0-flash-lite",
) -> dict:
    """SA 설계 문서를 GitHub Wiki 또는 Issue로 퍼블리시한다.

    mode="wiki" : GitHub Wiki Pages API 사용 (레포에서 Wiki 활성화 필요)
    mode="issue": GitHub Issues API 사용 (design-doc 라벨)
    """
    from connectors.github_connector import GitHubConnector
    
    if api_key:
        markdown = build_design_doc_markdown_llm(result_data, project_name, api_key, model)
    else:
        markdown = build_design_doc_markdown(result_data, project_name)

    connector = GitHubConnector(token)

    if mode == "issue":
        result = connector.publish_markdown_to_issue(owner, repo, page_title, markdown)
    else:
        try:
            result = connector.publish_markdown_to_wiki(owner, repo, page_title, markdown)
        except ValueError as e:
            err = str(e)
            # Wiki 비활성화(404) 시 프론트엔드가 안내 배너를 띄울 수 있도록 플래그 포함
            if "404" in err or "비활성화" in err:
                raise ValueError(
                    err + " | wiki_disabled=true"
                )
            raise

    result["markdown_length"] = len(markdown)
    result["mode"] = mode
    return result
