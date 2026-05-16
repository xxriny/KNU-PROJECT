"""
변경 영향 분석기: RAG 1단계 + LLM 2단계.

Step 1: ChromaDB에서 관련 SA 아티팩트 검색
Step 2: LLM으로 영향 범위 추론
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from pipeline.domain.agile.schemas import ImpactedComponent, ImpactResult


def _get_llm(api_key: str, model: str):
    from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore
    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    return ChatGoogleGenerativeAI(model=model, google_api_key=key, temperature=0)


def _rag_retrieve(change_description: str, session_id: str | None) -> str:
    """ChromaDB pm_sa_vector_db에서 변경 설명과 관련된 SA 아티팩트 검색."""
    try:
        import chromadb  # type: ignore
        from chromadb.config import Settings  # type: ignore

        storage_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )))),
            "storage",
        )
        client = chromadb.PersistentClient(
            path=os.path.join(storage_dir, "pm_sa_vector_db"),
            settings=Settings(anonymized_telemetry=False),
        )
        try:
            collection = client.get_collection("pm_sa_knowledge")
        except Exception:
            return ""

        where: dict[str, Any] = {}
        if session_id:
            where["session_id"] = session_id

        results = collection.query(
            query_texts=[change_description],
            n_results=5,
            where=where if where else None,
        )
        docs = results.get("documents", [[]])[0]
        return "\n\n".join(docs[:3])
    except Exception:
        return ""


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
) -> ImpactResult:
    """
    변경 영향 분석.

    Args:
        change_description: 변경 사항 설명 (자연어)
        sa_data: SA 분석 결과 (components, apis, tables)
        api_key: Gemini API 키
        model: 사용할 모델
        session_id: RAG 필터링용 세션 ID
    """
    # Step 1: RAG 컨텍스트 수집
    rag_context = _rag_retrieve(change_description, session_id)

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

    rag_section = f"## 관련 RAG 컨텍스트\n{rag_context}" if rag_context else ""
    prompt = f"""당신은 소프트웨어 아키텍처 변경 영향 분석 전문가입니다.

## 변경 사항
{change_description}

## 현재 SA 구조 요약
{sa_summary}

{rag_section}

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
        if not api_key and not os.environ.get("GEMINI_API_KEY", ""):
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
