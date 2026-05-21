"""
변경 영향 분석기: SA 데이터 기반 LLM 영향 범위 추론.
"""
from __future__ import annotations

import json
import os
import re

from pipeline.domain.agile.schemas import ImpactedComponent, ImpactResult


def _get_llm(api_key: str, model: str):
    from pipeline.core.utils import get_llm
    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    return get_llm(key, model=model, temperature=0)


def _parse_impact_json(text: str) -> dict:
    """LLM 응답에서 JSON 추출."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return {}


def run_impact_analyzer(
    change_description: str,
    sa_data: dict,
    api_key: str = "",
    model: str = "gemini-1.5-flash",
    session_id: str | None = None,
    use_llm: bool = True,
) -> ImpactResult:
    """SA 데이터와 LLM을 사용한 변경 영향 분석."""
    # SA 데이터 요약
    sa_summary = json.dumps({
        "components": [
            {"name": c.get("name"), "type": c.get("type"), "dependencies": c.get("dependencies", [])}
            for c in sa_data.get("components", [])[:15]
        ],
        "apis": [
            {"path": a.get("endpoint", a.get("path")), "method": a.get("method"), "owner": a.get("owner_component")}
            for a in sa_data.get("apis", [])[:15]
        ],
        "tables": [{"name": t.get("name"), "fields": [f.get("name") for f in t.get("fields", [])[:5]]}
                   for t in sa_data.get("tables", [])[:10]],
    }, ensure_ascii=False)

    prompt = f"""당신은 소프트웨어 아키텍처 변경 영향 분석 전문가입니다.

## 변경 사항
{change_description}

## 현재 SA 구조 요약
{sa_summary}

위 변경 사항이 시스템에 미치는 영향을 분석하여 다음 JSON 형식으로 반환하세요:

{{
  "impacted_components": [
    {{
      "name": "컴포넌트명",
      "impact_type": "modify|add|delete|interface_change",
      "description": "영향 설명",
      "affected_apis": ["관련 API 경로 목록"],
      "affected_tables": ["관련 테이블 목록"]
    }}
  ],
  "impacted_apis": ["영향받는 API 경로 목록"],
  "impacted_tables": ["영향받는 테이블 목록"],
  "risk_level": "low|medium|high|critical",
  "migration_notes": "마이그레이션 시 주의사항",
  "summary": "영향 분석 요약 (1-2문장)"
}}

JSON만 반환:"""

    try:
        if not use_llm or (not api_key and not os.environ.get("GEMINI_API_KEY", "")):
            return _fallback_impact(change_description, sa_data)

        llm = _get_llm(api_key, model)
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else response
        if isinstance(content, list):
            text = " ".join(
                item.get("text", str(item)) if isinstance(item, dict) else str(item)
                for item in content
            )
        else:
            text = str(content)
        parsed = _parse_impact_json(text)

        components = [
            ImpactedComponent(**c)
            for c in parsed.get("impacted_components", [])
            if isinstance(c, dict) and "name" in c
        ]

        return ImpactResult(
            change_description=change_description,
            impacted_components=components,
            impacted_apis=parsed.get("impacted_apis", []),
            impacted_tables=parsed.get("impacted_tables", []),
            risk_level=parsed.get("risk_level", "medium"),
            migration_notes=parsed.get("migration_notes", ""),
            summary=parsed.get("summary", ""),
        )
    except Exception as e:
        return _fallback_impact(change_description, sa_data, error=str(e))


def _fallback_impact(change_description: str, sa_data: dict, error: str = "") -> ImpactResult:
    """LLM 없이 키워드 기반 단순 분석."""
    desc_lower = change_description.lower()
    keywords = [kw.strip(".,;:!?") for kw in desc_lower.split() if len(kw) > 1]
    impacted_comps: list[ImpactedComponent] = []

    for comp in sa_data.get("components", []):
        name = comp.get("name", "")
        name_lower = name.lower()
        # 컴포넌트명이 설명에 포함되거나, 키워드가 컴포넌트명에 포함되면 매칭
        matched = name_lower in desc_lower or any(kw in name_lower for kw in keywords)
        if matched:
            impacted_comps.append(ImpactedComponent(
                name=name,
                impact_type="modify",
                description="변경 설명의 키워드와 매칭된 컴포넌트입니다.",
                affected_apis=[],
                affected_tables=[],
            ))

    summary = (
        f"키워드 기반 분석: {len(impacted_comps)}개 컴포넌트 영향 감지."
        + (f" (LLM 오류: {error})" if error else "")
    )
    return ImpactResult(
        change_description=change_description,
        impacted_components=impacted_comps,
        risk_level="medium",
        summary=summary,
    )
