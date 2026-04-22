from __future__ import annotations
from pipeline.core.state import PipelineState, make_sget
from pipeline.core.node_base import pipeline_node, NodeContext
from pipeline.core.utils import call_structured
from pipeline.domain.sa.schemas import SAAnalysisOutput

SYSTEM_PROMPT = """
당신은 SA 파이프라인의 최종 품질을 책임지는 '수석 아키텍처 검증관(Chief SA QA)'입니다.

최종 합격 기준 (5/5 보장):
1. **명칭 일치성 (Zero-Tolerance)**: 
   - 프론트엔드 컴포넌트, API 스키마, DB 테이블 간의 필드명이 1자라도 다르면 무조건 **FAIL**입니다.
   - **표준 명칭**: PK는 반드시 `id`여야 하며, FK는 `user_id`, `post_id` 형식을 따라야 합니다.
2. **타입 정합성**: 식별자는 UUID, 토큰은 String, 날짜는 ISO8601인지 확인합니다.
3. **무결성 게이트**: 설계상의 모순(예: FE는 user_id를 보내는데 API는 id로 받음)을 발견하면 구체적인 리포트를 작성합니다.
4. **언어 규칙**: 모든 사고 과정(thinking)과 결함 리포트(gaps)는 반드시 한국어로 작성하십시오. 영어를 사용하지 마십시오.

출력 데이터 규격 (JSON):
{
  "thinking": "필드 레벨의 기술적 타당성 검토 과정 (예: ID=UUID, Token=String 등의 도메인 지식 적용)",
  "phase": "SA",
  "version": "v1.0.0",
  "bundle_id": "session_id_SA_BNDL",
  "status": "PASS | FAIL | WARNING",
  "gaps": ["누락된 기능", "타입 부적합 사례(예: JWT를 UUID로 설계함)", "명명 규칙 위반 등"],
  "data": { "components": [ ... ], "apis": [ ... ], "tables": [ ... ] }
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
    apis = sget("api_data_modeler_output", {}).get("apis", [])
    tables = sget("api_data_modeler_output", {}).get("tables", [])
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
    
    # [Knowledge Persistence] Phase 3: 분석 결과를 RAG에 영구 저장
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
    
    # 루프 횟수 관리
    current_sa_loop = sget("sa_loop_count", 0)
    new_sa_loop = current_sa_loop + 1 if final_status == "FAIL" else current_sa_loop

    return {
        "sa_analysis_output": final_sa_output,
        "sa_output": final_sa_output,
        "sa_arch_bundle": final_sa_output,
        "sa_loop_count": new_sa_loop,
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_analysis", "thinking": thinking_msg}],
        "current_step": "sa_analysis_done"
    }
