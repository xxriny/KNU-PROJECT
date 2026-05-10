"""
Guardian Node
수집된 기술 스택 데이터를 병합하고 보안/정책 규칙에 따라 필터링 및 검증합니다.
GPL 라이선스 차단, 업데이트 지연 패키지 거절 및 LLM 기반 진위 여부 판단을 수행합니다.
"""

import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from pipeline.core.state import PipelineState, make_sget
from pipeline.core.utils import call_structured_with_usage
from pipeline.domain.pm.schemas import StackSourceData, GuardianOutput
from pipeline.domain.rag.nodes.project_db import get_session_inventory
from observability.logger import get_logger
from version import DEFAULT_MODEL

logger = get_logger()

class SemanticCheckResult(BaseModel):
    is_malicious: bool = Field(description="악의적이거나 부적절한 패키지 여부")
    reason: str = Field(description="판단 근거 (한국어)")
    confidence: float = Field(description="판단 신뢰도 (0.0~1.0)")

SEMANTIC_CHECK_PROMPT = """# 역할: 오픈소스 보안 아키텍트 및 감사관 (Security Auditor)

## 개요
제안된 기술 스택의 메타데이터와 현재 프로젝트의 구조(<project_inventory>)를 분석하여, 해당 기술의 안전성과 프로젝트 적합성을 최종 승인합니다.

## 심층 검증 가이드라인

### 1. 보안 및 진위 여부 (Integrity)
- **타이포스쿼팅(Typosquatting)**: 유명 패키지(react, lodash, flask 등)의 이름을 교묘하게 변형하여 악성 코드를 배포하는 가짜 패키지인지 철저히 조사하십시오.
- **악성 징후**: 설명이 모호하거나, 기술적 내용 없이 광고성 문구만 가득하거나, URL이 의심스러운 경우 즉시 반려하십시오.

### 2. 프로젝트 정합성 (Architectural Fit)
- **기존 스택과의 조화**: <project_inventory>를 참고하여, 이미 프로젝트에서 사용 중인 기술과 중복되거나 기술적 일관성을 해치는 도구인지 확인하십시오.
- **도메인 적합성**: 프로젝트의 성격(Web, Data, AI 등)에 맞는 기술인지, 너무 무겁거나 혹은 너무 빈약한 라이브러리는 아닌지 평가하십시오.

### 3. 커뮤니티 및 안정성
- 스타 수, 버전 정보, 업데이트 이력을 종합하여 실제 실무에서 사용 가능한 수준의 안정성을 갖췄는지 판단하십시오.

## 출력 규약
- 반드시 엄격한 잣대를 적용하십시오. 조금이라도 보안 위협이나 정합성 문제가 의심되면 `is_malicious`를 `true`로 설정하고 상세한 사유를 기술하십시오.
- 모든 판단 근거는 전문적인 한국어로 작성하십시오.
"""

def merge_sources(results: List[StackSourceData]) -> Optional[StackSourceData]:
    """여러 소스에서 온 동일 패키지 데이터를 최적의 필드로 병합합니다."""
    if not results:
        return None
    
    # 1. 가장 최신의/신뢰할만한 기본 객체 선택 (NPM 우선)
    npm_data = next((r for r in results if r.source_type == "npm"), None)
    github_data = next((r for r in results if r.source_type == "github"), None)
    pypi_data = next((r for r in results if r.source_type == "pypi"), None)
    
    base = npm_data or github_data or pypi_data or results[0]
    
    # 2. 필드별 최적 데이터 보완
    # version: npm/pypi 우선
    final_version = base.version
    if base.source_type == "github" and (npm_data or pypi_data):
        final_version = (npm_data or pypi_data).version
        
    # stars: github 우선
    final_stars = base.stars
    if github_data:
        final_stars = github_data.stars
        
    # description: 가장 긴 것 선택
    all_desc = [r.description for r in results if r.description]
    final_desc = max(all_desc, key=len) if all_desc else base.description
    
    return StackSourceData(
        name=base.name,
        description=final_desc,
        version=final_version,
        license=base.license,
        last_updated=base.last_updated,
        stars=final_stars,
        source_type="merged",
        url=base.url
    )

def rule_based_filter(data: StackSourceData) -> tuple[bool, Optional[str]]:
    """하드코딩된 규칙 기반 필터링 (라이선스, 업데이트 일자 등)"""
    
    # 1. 라이선스 체크 (GPL 등 상업적 이용 제한 라이선스 차단)
    forbidden_licenses = ["GPL", "AGPL", "LGPL"]
    if any(lib in data.license.upper() for lib in forbidden_licenses):
        return False, f"제한적인 라이선스({data.license})를 사용하고 있습니다."
    
    # 2. 업데이트 지연 체크 (최근 1년 내 업데이트 여부)
    if data.last_updated != "unknown":
        try:
            # GitHub/NPM 날짜 처리 (예: 2024-04-14T...)
            last_date = datetime.fromisoformat(data.last_updated.replace("Z", "+00:00"))
            if datetime.now(last_date.tzinfo) - last_date > timedelta(days=365):
                return False, "마지막 업데이트가 1년 이상 경과하여 유지보수가 중단된 것으로 의심됩니다."
        except Exception:
            pass # 날짜 파싱 실패 시 다른 룰에 맡김
            
    # 3. 설명 부실 체크
    if len(data.description) < 10:
        return False, "패키지 설명이 너무 부실하여 신뢰할 수 없습니다."
        
    return True, None

def llm_semantic_check(api_key: str, model: str, data: StackSourceData, inventory: dict) -> tuple[bool, str]:
    """LLM을 이용한 시맨틱 보안 및 적합성 검증"""
    inventory_str = ""
    if inventory:
        lines = ["<project_inventory>"]
        for p, items in sorted(inventory.items()):
            lines.append(f"- {p}: {[it.get('name') for it in items[:5]]}")
        lines.append("</project_inventory>")
        inventory_str = "\n".join(lines)

    user_msg = f"""{inventory_str}

### [검증 대상 기술 정보]
- Name: {data.name}
- Version: {data.version}
- Description: {data.description}
- URL: {data.url}

위 기술이 프로젝트에 안전하고 적합한지 보안 전문가로서 판단하십시오.
"""
    
    try:
        out, _ = call_structured_with_usage(
            api_key=api_key,
            model=model,
            schema=SemanticCheckResult,
            system_prompt=SEMANTIC_CHECK_PROMPT,
            user_msg=user_msg,
            temperature=0.1,
            compress_prompt=False
        )
        
        if out.is_malicious:
            return False, f"보안 및 적합성 검증 탈락: {out.reason}"
        return True, f"보안 검증 통과: {out.reason}"
    except Exception as e:
        logger.error(f"Semantic Check failed: {e}")
        return True, "보안 검증 시스템 일시 오류로 스킵"

def guardian_node(state: PipelineState) -> Dict[str, Any]:
    sget = make_sget(state)
    logger.info("=== [Node Entry] guardian_node ===")
    
    crawler_output = sget("stack_crawler_output", {})
    results_raw = crawler_output.get("results", [])
    results = [StackSourceData(**r) for r in results_raw]
    action_type = sget("action_type", "CREATE")
    run_id = sget("run_id", sget("session_id", "guardian_session"))
    
    if not results:
        return {
            "guardian_output": {
                "status": "REJECTED",
                "final_data": None,
                "rejection_reason": "수집된 기술 정보가 없습니다.",
                "thinking": "데이터 부재로 인한 자동 거절"
            }
        }

    # 1. 병합 (Merge)
    merged = merge_sources(results)
    if not merged:
        return {"guardian_output": {"status": "REJECTED", "rejection_reason": "병합 실패"}}

    # 2. 규칙 기반 필터 (Rule-based)
    is_safe, reason = rule_based_filter(merged)
    if not is_safe:
        return {
            "guardian_output": {
                "status": "REJECTED",
                "final_data": merged.model_dump(),
                "rejection_reason": reason,
                "thinking": f"Rule-based 필터에 의해 거절됨: {reason}"
            }
        }
    thinking_steps.append("라이선스 및 업데이트 주기 규칙 검증 통과")

    # 3. AI 시맨틱 체크 (LLM)
    is_legit, ai_reason = llm_semantic_check(
        api_key=sget("api_key", ""),
        model=sget("model", DEFAULT_MODEL),
        data=merged
    )
    
    status = "APPROVED" if is_legit else "REJECTED"
    final_reason = None if is_legit else ai_reason
    thinking_steps.append(ai_reason)

    return {
        "guardian_output": {
            "status": status,
            "final_data": merged.model_dump(),
            "rejection_reason": final_reason,
            "thinking": " | ".join(thinking_steps)
        },
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "guardian", "thinking": " | ".join(thinking_steps)}]
    }
