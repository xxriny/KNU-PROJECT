"""
SA 결과물 일관성 검증기 (V-001 ~ V-009).

V-001~V-005: 휴리스틱 규칙 (빠른 사전 필터)
V-006~V-009: LLM 기반 의미론적 검증

coherence_score: 통과 규칙 비율 (0.0 ~ 1.0)
passed: score >= 0.7 이면 True
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from pipeline.domain.agile.schemas import (
    ImpactedComponent,
    Severity,
    VerifierResult,
    ViolationItem,
)

# ── 필드명 호환성 헬퍼 ───────────────────────────────────────
# result_shaper: table_name / columns / column_name / component_name
# 레거시:        name      / fields  / name         / name

def _cname(c: dict) -> str:
    return c.get("component_name") or c.get("name", "")

def _tname(t: dict) -> str:
    return t.get("table_name") or t.get("name", "?")

def _tcols(t: dict) -> list:
    return t.get("columns") or t.get("fields", [])

def _colname(col: dict) -> str:
    return col.get("column_name") or col.get("name", "")


# ── LLM 의존성 (지연 임포트) ─────────────────────────────────

def _get_llm(api_key: str, model: str):
    from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore
    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    return ChatGoogleGenerativeAI(model=model, google_api_key=key, temperature=0)


# ── V-001: API 엔드포인트 컴포넌트 참조 검사 ──────────────────

def _v001_api_component_ref(sa_data: dict) -> list[ViolationItem]:
    violations: list[ViolationItem] = []
    components = {_cname(c) for c in sa_data.get("components", [])}
    components.discard("")
    for api in sa_data.get("apis", []):
        owner = api.get("owner_component", "")
        if owner and owner not in components:
            violations.append(ViolationItem(
                rule_id="V-001",
                rule_name="API 컴포넌트 참조",
                severity=Severity.major,
                description=f"API '{api.get('endpoint', api.get('path', '?'))}' 의 owner_component '{owner}' 가 컴포넌트 목록에 없습니다.",
                location=f"API: {api.get('endpoint', api.get('path', ''))}",
                suggestion=f"컴포넌트 '{owner}'를 SA 컴포넌트 목록에 추가하거나 owner_component 값을 수정하세요.",
            ))
    return violations


# ── V-002: 컴포넌트 의존성 방향 순환 검사 ────────────────────

def _v002_circular_dependency(sa_data: dict) -> list[ViolationItem]:
    violations: list[ViolationItem] = []
    graph: dict[str, set[str]] = {}
    for comp in sa_data.get("components", []):
        name = _cname(comp)
        deps = comp.get("dependencies", [])
        if isinstance(deps, list):
            graph[name] = set(deps)
        else:
            graph[name] = set()

    visited: set[str] = set()
    path: set[str] = set()

    def dfs(node: str) -> bool:
        if node in path:
            return True
        if node in visited:
            return False
        visited.add(node)
        path.add(node)
        for neighbor in graph.get(node, set()):
            if dfs(neighbor):
                return True
        path.discard(node)
        return False

    for node in list(graph.keys()):
        if node not in visited:
            if dfs(node):
                violations.append(ViolationItem(
                    rule_id="V-002",
                    rule_name="컴포넌트 순환 의존성",
                    severity=Severity.critical,
                    description=f"컴포넌트 '{node}' 에서 순환 의존성이 감지되었습니다.",
                    location=f"Component: {node}",
                    suggestion="의존성 방향을 재검토하고 순환을 끊으세요 (중간 인터페이스/이벤트 도입 고려).",
                ))
                break

    return violations


# ── V-003: DB 테이블 필드 누락 검사 ──────────────────────────

def _v003_table_fields(sa_data: dict) -> list[ViolationItem]:
    violations: list[ViolationItem] = []
    required = {"id", "created_at"}
    for table in sa_data.get("tables", []):
        name = _tname(table)
        cols = _tcols(table)
        fields = {_colname(c).lower() for c in cols}
        missing = required - fields
        if missing:
            violations.append(ViolationItem(
                rule_id="V-003",
                rule_name="DB 테이블 필수 필드",
                severity=Severity.minor,
                description=f"테이블 '{name}' 에 필수 필드 {missing} 가 없습니다.",
                location=f"Table: {name}",
                suggestion="id (PK), created_at (타임스탬프) 필드를 추가하세요.",
            ))
    return violations


# ── V-004: 보안 레이어 검사 ──────────────────────────────────

def _v004_security_layer(sa_data: dict) -> list[ViolationItem]:
    violations: list[ViolationItem] = []
    security_keywords = {"auth", "security", "jwt", "token", "oauth", "guard", "middleware"}
    has_security = any(
        any(kw in _cname(comp).lower() or kw in comp.get("type", "").lower() for kw in security_keywords)
        for comp in sa_data.get("components", [])
    )
    has_user_api = any(
        any(kw in api.get("endpoint", api.get("path", "")).lower() for kw in ("user", "account", "profile", "login", "register"))
        for api in sa_data.get("apis", [])
    )
    if has_user_api and not has_security:
        violations.append(ViolationItem(
            rule_id="V-004",
            rule_name="보안 레이어 누락",
            severity=Severity.major,
            description="사용자 관련 API가 있지만 인증/보안 컴포넌트가 정의되지 않았습니다.",
            location="Components",
            suggestion="AuthService, SecurityMiddleware 등 인증 레이어 컴포넌트를 추가하세요.",
        ))
    return violations


# ── V-005: 외부 서비스 인터페이스 검사 ───────────────────────

def _v005_external_interface(sa_data: dict) -> list[ViolationItem]:
    violations: list[ViolationItem] = []
    external_keywords = {"gateway", "external", "thirdparty", "third_party", "integration"}
    external_comps = [
        c for c in sa_data.get("components", [])
        if any(kw in c.get("type", "").lower() or kw in _cname(c).lower() for kw in external_keywords)
    ]
    for comp in external_comps:
        has_interface = bool(comp.get("interface") or comp.get("protocol") or comp.get("api_spec"))
        if not has_interface:
            violations.append(ViolationItem(
                rule_id="V-005",
                rule_name="외부 서비스 인터페이스 명세 누락",
                severity=Severity.minor,
                description=f"외부 서비스 컴포넌트 '{_cname(comp)}' 에 인터페이스 명세가 없습니다.",
                location=f"Component: {_cname(comp)}",
                suggestion="외부 서비스와의 통신 프로토콜, API spec, 또는 interface 필드를 명세하세요.",
            ))
    return violations


# ── LLM 보조 검증 (V-006: 의미론적 일관성) ──────────────────

def _v006_semantic_coherence_llm(sa_data: dict, api_key: str, model: str) -> list[ViolationItem]:
    """LLM을 사용한 의미론적 일관성 검증. 실패 시 빈 리스트 반환."""
    try:
        llm = _get_llm(api_key, model)
        summary = json.dumps({
            "component_names": [c.get("name") for c in sa_data.get("components", [])[:10]],
            "api_endpoints": [a.get("endpoint", a.get("path")) for a in sa_data.get("apis", [])[:10]],
            "table_names": [_tname(t) for t in sa_data.get("tables", [])[:10]],
        }, ensure_ascii=False)

        prompt = f"""다음 SA(시스템 아키텍처) 요약을 분석하여 의미론적 불일치가 있는지 확인하세요.
컴포넌트 이름, API 경로, 테이블명 사이에 명백한 불일치나 누락이 있으면 JSON 배열로 반환하세요.
문제가 없으면 빈 배열 []을 반환하세요.

형식: [{{"issue": "설명", "location": "위치", "suggestion": "제안"}}]

SA 요약:
{summary}

JSON만 반환:"""

        response = llm.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return []
        items = json.loads(match.group())
        violations = []
        for item in items[:5]:
            if isinstance(item, dict) and "issue" in item:
                violations.append(ViolationItem(
                    rule_id="V-006",
                    rule_name="의미론적 일관성",
                    severity=Severity.minor,
                    description=item.get("issue", ""),
                    location=item.get("location", ""),
                    suggestion=item.get("suggestion", ""),
                ))
        return violations
    except Exception:
        return []


# ── V-007: API 명명 일관성 (LLM) ─────────────────────────────

def _v007_api_naming_consistency_llm(sa_data: dict, api_key: str, model: str) -> list[ViolationItem]:
    """REST 컨벤션 및 명명 일관성 검증."""
    try:
        apis = sa_data.get("apis", [])
        if len(apis) < 2:
            return []
        endpoints = [a.get("endpoint", a.get("path", "")) for a in apis[:20]]
        llm = _get_llm(api_key, model)
        prompt = f"""다음 REST API 엔드포인트 목록에서 명명 일관성 문제를 찾아주세요.
검토 항목: 동사/명사 혼용, 복수/단수 혼용, 케이스 혼용 (camelCase vs snake_case), 계층 구조 불일치.

엔드포인트: {json.dumps(endpoints, ensure_ascii=False)}

문제가 있는 경우만 JSON 배열로 반환하세요. 없으면 [] 반환.
형식: [{{"issue": "설명", "location": "문제 엔드포인트", "suggestion": "수정 제안"}}]
JSON만 반환:"""
        response = llm.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return []
        items = json.loads(match.group())
        return [
            ViolationItem(
                rule_id="V-007",
                rule_name="API 명명 일관성",
                severity=Severity.minor,
                description=item.get("issue", ""),
                location=item.get("location", ""),
                suggestion=item.get("suggestion", ""),
            )
            for item in items[:3]
            if isinstance(item, dict) and "issue" in item
        ]
    except Exception:
        return []


# ── V-008: 컴포넌트 단일 책임 원칙 (LLM) ─────────────────────

def _v008_srp_check_llm(sa_data: dict, api_key: str, model: str) -> list[ViolationItem]:
    """SRP(단일 책임 원칙) 위반 감지."""
    try:
        components = sa_data.get("components", [])
        if not components:
            return []
        comp_summary = [
            {"name": _cname(c), "responsibilities": c.get("responsibilities", c.get("description", ""))}
            for c in components[:15]
        ]
        llm = _get_llm(api_key, model)
        prompt = f"""다음 소프트웨어 컴포넌트 목록에서 단일 책임 원칙(SRP) 위반 가능성을 찾아주세요.
책임이 너무 광범위하거나, 여러 도메인을 처리하거나, 분리되어야 할 기능이 하나에 포함된 경우를 찾으세요.

컴포넌트: {json.dumps(comp_summary, ensure_ascii=False)}

SRP 위반이 의심되는 경우만 반환하세요. 없으면 [].
형식: [{{"issue": "설명", "location": "컴포넌트명", "suggestion": "분리 제안"}}]
JSON만 반환:"""
        response = llm.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return []
        items = json.loads(match.group())
        return [
            ViolationItem(
                rule_id="V-008",
                rule_name="단일 책임 원칙(SRP)",
                severity=Severity.minor,
                description=item.get("issue", ""),
                location=item.get("location", ""),
                suggestion=item.get("suggestion", ""),
            )
            for item in items[:3]
            if isinstance(item, dict) and "issue" in item
        ]
    except Exception:
        return []


# ── V-009: 보안 설계 심층 검토 (LLM) ────────────────────────

def _v009_security_depth_llm(sa_data: dict, api_key: str, model: str) -> list[ViolationItem]:
    """인증 플로우 및 보안 설계의 논리적 완결성 검토."""
    try:
        llm = _get_llm(api_key, model)
        security_comps = [
            c for c in sa_data.get("components", [])
            if any(kw in _cname(c).lower() or kw in c.get("type", "").lower()
                   for kw in ("auth", "security", "jwt", "token", "oauth", "guard", "session"))
        ]
        auth_apis = [
            a for a in sa_data.get("apis", [])
            if any(kw in a.get("endpoint", a.get("path", "")).lower()
                   for kw in ("login", "logout", "token", "auth", "refresh", "register"))
        ]
        if not security_comps and not auth_apis:
            return []
        context = {
            "security_components": [c.get("name") for c in security_comps],
            "auth_apis": [a.get("endpoint", a.get("path")) for a in auth_apis],
        }
        prompt = f"""다음 보안/인증 관련 설계를 검토하여 논리적 완결성 문제를 찾아주세요.
검토 항목: 토큰 갱신 플로우 누락, 로그아웃/세션 만료 처리 누락, 권한 검증 레이어 누락, HTTPS/암호화 명세 부재.

보안 설계: {json.dumps(context, ensure_ascii=False)}

심각한 보안 설계 누락만 반환하세요. 없으면 [].
형식: [{{"issue": "설명", "location": "위치", "suggestion": "개선 방법"}}]
JSON만 반환:"""
        response = llm.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return []
        items = json.loads(match.group())
        return [
            ViolationItem(
                rule_id="V-009",
                rule_name="보안 설계 완결성",
                severity=Severity.major,
                description=item.get("issue", ""),
                location=item.get("location", ""),
                suggestion=item.get("suggestion", ""),
            )
            for item in items[:3]
            if isinstance(item, dict) and "issue" in item
        ]
    except Exception:
        return []


# ── 진입점 ───────────────────────────────────────────────────

def run_verifier(
    sa_data: dict,
    api_key: str = "",
    model: str = "gemini-1.5-flash",
    use_llm: bool = True,
    use_deep_llm: bool = False,
) -> VerifierResult:
    """SA 데이터 검증. sa_data는 components/apis/tables 키를 포함한 dict.

    use_llm: V-006 의미론적 일관성 (기본 LLM)
    use_deep_llm: V-007~V-009 추가 LLM 검증 (더 깊은 분석)
    """
    effective_key = api_key or os.environ.get("GEMINI_API_KEY", "")

    violations: list[ViolationItem] = []
    violations += _v001_api_component_ref(sa_data)
    violations += _v002_circular_dependency(sa_data)
    violations += _v003_table_fields(sa_data)
    violations += _v004_security_layer(sa_data)
    violations += _v005_external_interface(sa_data)
    if use_llm and effective_key:
        violations += _v006_semantic_coherence_llm(sa_data, effective_key, model)
    if use_deep_llm and effective_key:
        violations += _v007_api_naming_consistency_llm(sa_data, effective_key, model)
        violations += _v008_srp_check_llm(sa_data, effective_key, model)
        violations += _v009_security_depth_llm(sa_data, effective_key, model)

    if use_deep_llm and effective_key:
        total_rules = 9
    elif use_llm and api_key:
        total_rules = 6
    else:
        total_rules = 5
    rule_ids_violated = {v.rule_id for v in violations}
    passed_count = total_rules - len(rule_ids_violated)
    score = round(passed_count / total_rules, 3)
    passed = score >= 0.7

    critical_count = sum(1 for v in violations if v.severity == Severity.critical)
    major_count = sum(1 for v in violations if v.severity == Severity.major)

    summary = (
        f"총 {len(violations)}개 위반 감지 (치명적: {critical_count}, 주요: {major_count}). "
        f"일관성 점수: {score:.1%} [{total_rules}개 규칙 적용]"
        if violations
        else f"모든 규칙 통과. 일관성 점수: {score:.1%} [{total_rules}개 규칙 적용]"
    )

    return VerifierResult(
        coherence_score=score,
        passed=passed,
        violations=violations,
        summary=summary,
    )
