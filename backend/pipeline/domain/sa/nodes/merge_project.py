from __future__ import annotations
from pipeline.core.state import PipelineState, make_sget
from pipeline.core.node_base import pipeline_node, NodeContext
from pipeline.core.utils import call_structured
from pipeline.domain.sa.schemas import MergeProjectOutput

SYSTEM_PROMPT = """
당신은 NAVIGATOR 시스템의 '수석 통합 아키텍트(Senior Integration Architect)'입니다.
전달받은 PM 요구사항 번들과 현재 프로젝트의 기존 코드/설계 상태를 분석하여 최적의 병합 전략을 수립하는 역할을 맡고 있습니다.

핵심 설계 규칙:
1. 모드 파악: 기존 프로젝트 정보(system_scan)가 비어있다면 'CREATE' 모드로 간주하고 PM 분석서를 100% 수용합니다.
2. 충돌 해결 (UPDATE 모드):
   - 기존 구조와 새로운 요구사항 간의 충돌을 식별하고 데이터 무결성을 위해 필요한 제약 조건(예: Composite Unique Key)을 명시합니다.
   - **데이터 구조 최적화**: 소셜 로그인 연동 시 확장성을 위해 `User` 테이블에 직접 필드를 추가하기보다, **1:N 관계인 `OAuthAccount` 테이블로 분리 설계**하여 멀티 프로바이더(Google, Kakao 등) 지원이 가능하도록 합니다.
3. 세부 아키텍처 가이드라인:
   - 보안/인증 관련: OAuth 연동 시 토큰 검증은 필수이며, **기존 이메일 계정 존재 시 계정 탈취(Account Takeover) 방지를 위해 해당 이메일의 소유권 확인(Verified 상태 체크) 및 연동 승인 절차**를 전략에 포함합니다.
   - **에러 핸들링 전략**: 외부 API 호출 실패, 네트워크 타임아웃, 유효하지 않은 토큰 수신 시의 구체적인 에러 처리 및 사용자 응답 로직을 기술합니다.
   - 트랜잭션/안전성: 복합적인 엔티티 생성 시 원자성을 보장하기 위한 전략을 기술합니다.
4. 다운스트림 전달: 수립된 전략은 후속 노드가 구체적인 구현체로 변환할 수 있도록 명확하고 구체적인 문장으로 작성합니다.
5. 언어 규칙: 모든 사고 과정(thinking)과 병합 전략은 반드시 한국어로 상세히 작성하십시오. 영어를 사용하지 마십시오.

출력 데이터 규격 (JSON):
{
  "thinking": "병합 전략 수립 근거 (1:N 테이블 분리 설계 및 보안 취약점 대응 전략 포함)",
  "mode": "CREATE | UPDATE | REVERSE_ENGINEER",
  "base_context": { "설명": "기존 스택 및 주요 데이터 모델 정보" },
  "merge_strategy": "구체적인 충돌 해결책 및 설계 가이드라인 (테이블 구조, 보안 정책, 에러 핸들링 포함)"
}
"""

def _build_user_message(input_idea: str, system_scan: dict, rtm: list) -> str:
    """LLM 메시지 최적화 (토큰 절감)"""
    pruned_rtm = [{"id": r.get("id"), "desc": r.get("desc"), "pri": r.get("pri")} for r in rtm]
    scan_summary = {
        "frameworks": system_scan.get("detected_frameworks", []),
        "entities": system_scan.get("existing_entities", []),
        "api_count": len(system_scan.get("existing_apis", []))
    }
    return f"\n    [Input Idea] {input_idea}\n    [System Scan Summary] {scan_summary}\n    [PM Requirements] {pruned_rtm}\n    "

from observability.logger import get_logger

logger = get_logger()

@pipeline_node("sa_merge_project")
def sa_merge_project_node(ctx: NodeContext) -> dict:
    state = ctx.state
    sget = ctx.sget
    logger.info("=== [Node Entry] sa_merge_project_node ===")
    
    input_idea = sget("input_idea", "")
    system_scan = sget("system_scan", {}) or {}
    
    # PM 번들에서 최종 정제된 RTM 가져오기
    pm_bundle = sget("pm_bundle", {})
    requirements_rtm = pm_bundle.get("data", {}).get("rtm", []) or sget("features", [])
    
    if not requirements_rtm:
        logger.warning("No RTM/Features found in state for SA merge.")
    
    # 1. Prepare optimized user prompt
    user_content = _build_user_message(input_idea, system_scan, requirements_rtm)
    
    # 2. Call LLM for merge strategy
    res = call_structured(
        api_key=ctx.api_key,
        model=ctx.model,
        schema=MergeProjectOutput,
        system_prompt=SYSTEM_PROMPT,
        user_msg=user_content,
        compress_prompt=True # Phase 3 enabled
    )
    
    output = res.parsed
    
    # 3. Build merged_project contract for downstream
    merged_project = {
        "mode": output.mode,
        "base_context": output.base_context,
        "merge_strategy": output.merge_strategy,
        "plan": {
            "requirements_rtm": requirements_rtm,
            "context_spec": sget("context_spec", {})
        }
    }
    
    thinking_msg = output.thinking or "프로젝트 병합 전략 수립 완료"
    
    return {
        "sa_merge_project_output": output.model_dump(),
        "merged_project": merged_project,
        "action_type": output.mode,
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_merge_project", "thinking": thinking_msg}],
        "current_step": "sa_merge_project_done"
    }
