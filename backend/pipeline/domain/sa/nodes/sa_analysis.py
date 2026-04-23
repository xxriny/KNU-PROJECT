from __future__ import annotations
from pipeline.core.state import PipelineState, make_sget
from pipeline.core.node_base import pipeline_node, NodeContext
from pipeline.core.utils import call_structured
from pipeline.domain.sa.schemas import SAAnalysisOutput

SYSTEM_PROMPT = """
당신은 SA 파이프라인의 최종 품질을 책임지는 '수석 아키텍처 검증관(Chief SA QA)'입니다.
설계 결함 발견 시, 수정 방향을 명확히 제시하기 위해 **Key-Value 형식의 핀포인트 피드백**을 제공하십시오.

최종 합격 기준 (5/5 보장):
1. **명칭 일치성 (Zero-Tolerance)**: 
   - 프론트엔드 컴포넌트, API 스키마, DB 테이블 간의 필드명이 1자라도 다르면 무조건 **FAIL**입니다.
   - **표준 명칭**: PK는 `id`, FK는 `user_id` 형식을 엄격히 준수했는지 확인합니다.
2. **타입 정합성**: 식별자는 UUID, 토큰은 String, 날짜는 ISO8601인지 확인합니다.
3. **무결성 게이트**: API 응답 필드가 DB에 없거나, 존재하지 않는 테이블을 참조하는 FK 등을 전수 조사합니다.
4. **엄격한 완전성 검증**: 제공된 요구사항(RTM)에 대응하는 컴포넌트, API, 테이블이 하나라도 누락되었다면 절대 PASS를 주지 마십시오. 특히 모든 산출물 배열이 비어있다면 이는 파이프라인의 치명적 결함이므로 반드시 `FAIL`로 판정하고 `gaps`에 해당 사실을 기록하십시오.
5. **언어 규칙**: 모든 사고 과정(thinking)과 피드백은 반드시 한국어로 작성하십시오.
6. **핀포인트 피드백 (Gaps 작성법)**:
   - 반려 시 "정합성 오류"와 같은 모호한 표현 금지.
   - 형식: `{"Target": "필드명/테이블명", "Reason": "구체적인 오류 사유", "Action": "수정 가이드"}`

출력 데이터 규격 (JSON):
{
  "thinking": "필드 레벨의 기술적 타당성 및 API-DB 정합성 전수 조사 과정",
  "phase": "SA",
  "status": "PASS | FAIL | WARNING",
  "gaps": [
    "{\"Target\": \"user_id\", \"Reason\": \"users 테이블 참조 오류\", \"Action\": \"users 테이블 PK와 타입 일치 및 명칭 확인\"}",
    "{\"Target\": \"GET /api/v1/profile\", \"Reason\": \"응답 스키마에 email 누락\", \"Action\": \"DB users 테이블의 email 필드 추가\"}"
  ],
  "data": { "components": [...], "apis": [...], "tables": [...] }
}
"""

def _to_compact_text(items: list[dict]) -> str:
    """토큰 최적화를 위한 YAML 유사 간결 텍스트 변환기"""
    if not items: return "없음"
    return "\n".join("- " + ", ".join(f"{k}: {v}" for k, v in item.items() if v) for item in items)

def _build_user_message(rtm: list, components: list, apis: list, tables: list) -> str:
    """LLM 메시지 최적화 (토큰 절감 및 검증 집중)"""
    pruned_rtm = _to_compact_text([{"id": r.get("id"), "desc": r.get("desc")} for r in rtm])
    pruned_components = _to_compact_text([{"name": c.get("component_name"), "role": c.get("role")} for c in components])
    pruned_apis = _to_compact_text([{"ep": a.get("endpoint"), "req": str(a.get("request_schema")), "res": str(a.get("response_schema"))} for a in apis])
    pruned_tables = _to_compact_text([{"name": t.get("table_name"), "cols": ", ".join(c.get("name", "") for c in t.get("columns", []))} for t in tables])
    
    return f"\n[RTM]\n{pruned_rtm}\n\n[Components]\n{pruned_components}\n\n[APIs]\n{pruned_apis}\n\n[Tables]\n{pruned_tables}\n"

def _run_python_precheck(apis: list, tables: list) -> list:
    """LLM 호출 전 Python에서 물리적 결함을 먼저 체크 (Logic Offloading)"""
    gaps = []
    # 1. API 스키마 Null 체크 (아까 IT-02 시나리오 실패 대응)
    for api in apis:
        if not api.get("request_schema") and "GET" not in api.get("endpoint", ""):
            gaps.append(f"API 결함: {api.get('endpoint')} 의 request_schema가 비어있습니다.")
        if not api.get("response_schema"):
            gaps.append(f"API 결함: {api.get('endpoint')} 의 response_schema가 비어있습니다.")
            
    # 2. Table 컬럼 Null 체크
    for table in tables:
        if not table.get("columns"):
            gaps.append(f"DB 결함: {table.get('table_name')} 테이블에 정의된 컬럼이 없습니다.")
            
    return gaps

from observability.logger import get_logger

logger = get_logger()

@pipeline_node("sa_analysis")
def sa_analysis_node(ctx: NodeContext) -> dict:
    sget = ctx.sget
    logger.info("=== [Node Entry] sa_analysis_node ===")
    
    # RTM 데이터 소스 다변화 (Robustness)
    merged_proj = sget("merged_project", {})
    rtm = (merged_proj.get("plan", {}).get("requirements_rtm", []) or 
           sget("pm_bundle", {}).get("data", {}).get("rtm", []) or 
           sget("features", []))
    
    components = sget("component_scheduler_output", {}).get("components", [])
    apis = sget("api_modeler_output", {}).get("apis", [])
    tables = sget("db_schema_architect_output", {}).get("tables", [])
    run_id = sget("run_id", "unknown_session")
    
    # 1. Python Pre-check (물리적 결함 선행 검출)
    precheck_gaps = _run_python_precheck(apis, tables)
    
    # 2. Prepare optimized user prompt
    user_content = _build_user_message(rtm, components, apis, tables)
    logger.info(f"Calling SA Analysis LLM (RTM:{len(rtm)}, Comp:{len(components)}, API:{len(apis)}, Table:{len(tables)})")
    
    # 3. Call LLM (최종 검증은 모든 스키마를 상세히 봐야 하므로 압축 제외)
    res = call_structured(
        api_key=ctx.api_key,
        model=ctx.model,
        schema=SAAnalysisOutput,
        system_prompt=SYSTEM_PROMPT.replace("session_id", run_id),
        user_msg=user_content,
        compress_prompt=False
    )
    
    output = res.parsed
    if not output:
        logger.error("SA Analysis LLM returned empty parsed result.")
        return {"error": "SA Analysis LLM 결과 파싱 실패"}

    # Python에서 찾은 gap과 LLM이 찾은 gap 합치기
    final_gaps = list(set(precheck_gaps + (output.gaps or [])))
    final_status = "FAIL" if precheck_gaps else (output.status or "WARNING")
    
    logger.info(f"SA Analysis Result: {final_status} | Gaps: {len(final_gaps)}")
    
    output.gaps = final_gaps
    output.status = final_status
    
    final_sa_output = output.model_dump()
    thinking_msg = output.thinking or "SA 아키텍처 최종 검증 완료"
    
    # [Knowledge Persistence] Phase 3: 분석 결과를 RAG에 영구 저장 (플래그 확인)
    skip_persistence = sget("skip_rag_persistence", False)
    if not skip_persistence:
        from pipeline.domain.sa.nodes.sa_db import upsert_sa_artifact
        try:
            upsert_sa_artifact(
                session_id=run_id,
                artifact_data=final_sa_output,
                artifact_type="SA_ARCH_BUNDLE"
            )
            logger.info(f"SA Analysis Result persisted to RAG for session: {run_id}")
        except Exception as e:
            logger.error(f"Failed to persist SA result to RAG: {e}")
    
    return {
        "sa_analysis_output": final_sa_output,
        "sa_output": final_sa_output,
        "sa_arch_bundle": final_sa_output,
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_analysis", "thinking": thinking_msg}],
        "current_step": "sa_analysis_done"
    }
