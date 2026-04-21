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

def _build_user_message(rtm: list, components: list, apis: list, tables: list) -> str:
    """LLM 메시지 최적화 (토큰 절감 및 검증 집중)"""
    pruned_rtm = [{"id": r.get("id"), "desc": r.get("desc")} for r in rtm]
    pruned_components = [{"name": c.get("component_name"), "role": c.get("role")} for c in components]
    pruned_apis = [{"ep": a.get("endpoint"), "req": a.get("request_schema"), "res": a.get("response_schema")} for a in apis]
    pruned_tables = [{"name": t.get("table_name"), "cols": [c.get("name") for c in t.get("columns", [])]} for t in tables]
    
    return f"\n    [RTM] {pruned_rtm}\n    [Components] {pruned_components}\n    [APIs] {pruned_apis}\n    [Tables] {pruned_tables}\n    "

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

@pipeline_node("sa_analysis")
def sa_analysis_node(ctx: NodeContext) -> dict:
    sget = ctx.sget
    rtm = sget("merged_project", {}).get("plan", {}).get("requirements_rtm", [])
    components = sget("component_scheduler_output", {}).get("components", [])
    apis = sget("api_data_modeler_output", {}).get("apis", [])
    tables = sget("api_data_modeler_output", {}).get("tables", [])
    run_id = sget("run_id", "unknown_session")
    
    # 1. Python Pre-check (물리적 결함 선행 검출)
    precheck_gaps = _run_python_precheck(apis, tables)
    
    # 2. Prepare optimized user prompt
    user_content = _build_user_message(rtm, components, apis, tables)
    
    # 3. Call LLM
    res = call_structured(
        api_key=ctx.api_key,
        model=ctx.model,
        schema=SAAnalysisOutput,
        system_prompt=SYSTEM_PROMPT.replace("session_id", run_id),
        user_msg=user_content
    )
    
    output = res.parsed
    
    # Python에서 찾은 gap과 LLM이 찾은 gap 합치기
    final_gaps = list(set(precheck_gaps + output.gaps))
    final_status = "FAIL" if precheck_gaps else output.status
    
    output.gaps = final_gaps
    output.status = final_status
    
    final_sa_output = output.model_dump()
    
    return {
        "sa_analysis_output": final_sa_output,
        "sa_output": final_sa_output,
        "sa_arch_bundle": final_sa_output,
        "current_step": "sa_analysis_done"
    }
