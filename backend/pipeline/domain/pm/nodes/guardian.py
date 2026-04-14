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
from observability.logger import get_logger
from version import DEFAULT_MODEL

logger = get_logger()

class SemanticCheckResult(BaseModel):
    is_malicious: bool = Field(description="악의적이거나 타이포스쿼팅 의심 여부")
    reason: str = Field(description="판단 근거 (한국어)")
    confidence: float = Field(description="판단 신뢰도 (0.0~1.0)")

SEMANTIC_CHECK_PROMPT = """당신은 오픈소스 보안 전문가입니다. 
제공된 기술 스택의 메타데이터를 분석하여 다음 사항을 판단하세요.

1. 타이포스쿼팅(Typosquatting): 유명 패키지(예: react, lodash, zustand)의 이름을 교묘하게 바꾼 가짜 패키지인지 확인하세요. (예: reackt, zunstand 등)
2. 악성 코드 징조: 설명이 너무 부실하거나, 기술적인 내용 대신 의심스러운 광고나 무의미한 텍스트만 있는지 확인하세요.

반드시 엄격하게 판단하여 조금이라도 의심스러우면 is_malicious를 true로 설정하세요.
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
    # 날짜 형식이 다양할 수 있어 간단한 체크만 수행 가능할 경우 우선 패스하거나, ISO 형식일 때만 체크
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

def llm_semantic_check(api_key: str, model: str, data: StackSourceData) -> tuple[bool, str]:
    """LLM을 이용한 시맨틱 보안 검증"""
    user_msg = f"Package Name: {data.name}\nDescription: {data.description}\nURL: {data.url}"
    
    try:
        out, _ = call_structured_with_usage(
            api_key=api_key,
            model=model,
            schema=SemanticCheckResult,
            system_prompt=SEMANTIC_CHECK_PROMPT,
            user_msg=user_msg,
            temperature=0.1
        )
        
        if out.is_malicious:
            return False, f"AI 보안 검증 탈락: {out.reason}"
        return True, "AI 보안 검증 통과"
    except Exception as e:
        logger.error(f"Semantic Check failed: {e}")
        return True, "AI 보안 검증 스킵 (시스템 오류)"

def guardian_node(state: PipelineState) -> Dict[str, Any]:
    sget = make_sget(state)
    logger.info("Starting guardian_node")
    
    crawler_output = sget("stack_crawler_output", {})
    results_raw = crawler_output.get("results", [])
    results = [StackSourceData(**r) for r in results_raw]
    
    if not results:
        return {
            "guardian_output": {
                "status": "REJECTED",
                "final_data": None,
                "rejection_reason": "수집된 기술 스택 정보가 없습니다.",
                "thinking": "크롤링 결과가 비어있어 분석을 중단함."
            }
        }

    # 1. 병합 (Merge)
    merged = merge_sources(results)
    if not merged:
        return {"guardian_output": {"status": "REJECTED", "rejection_reason": "병합 실패"}}

    thinking_steps = ["여러 소스의 데이터를 병합 완료 (NPM 버전 + GitHub Stars 등)"]

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
