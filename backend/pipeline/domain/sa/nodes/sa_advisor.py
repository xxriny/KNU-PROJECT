"""
SA Advisor Node — 통합 QA 검증 + 수정 조언 생성
sa_analysis를 대체하며 다음 역할을 수행합니다:
1. 약어→풀네임 Translation Layer (프론트엔드용)
2. Python Pre-check (물리적 결함 선행 검출)
3. LLM QA 검증 + 수정 조언 생성 (RAG 토큰 최적화)
4. sa_arch_bundle 최종 조립
"""
from __future__ import annotations
import json
from pipeline.core.node_base import pipeline_node, NodeContext
from pipeline.core.utils import call_structured, safe_get
from pipeline.domain.sa.schemas import SAAdvisorOutput
from observability.logger import get_logger

logger = get_logger()

# SYSTEM_PROMPT: PM 요구사항과 SA 설계 결과물을 대조하여 검증하고 조언을 생성하는 프롬프트
SYSTEM_PROMPT = """# Role: Lead System Design QA & Architecture Advisor

## Overview
Finalize the validation of design integrity and consistency by comparing PM requirements (RTM) with SA design outputs (API, DB schemas). 
Beyond just error detection, provide professional technical advice considering system stability and scalability.

## Validation & Advisory Guidelines

### 1. Design Consistency
- **Zero-Tolerance Naming**: Conduct a full audit to ensure field/column names are 100% consistent across Components, APIs, and DBs. Report any mismatch as 'Critical'.
- **Referential Integrity**: Ensure all Foreign Keys (FKs) point to existing tables and that their data types match perfectly.

### 2. Requirement Coverage (RTM Compliance)
- **Full Audit**: Verify that all features defined in the RTM are implementable via the designed API or DB structures.
- **Identify Omissions**: Categorize any requirement that cannot be resolved by the current API/DB as a 'Critical' issue.

### 3. Technical Excellence
- **RESTful Standards**: Review URI designs for compliance and ensure HTTP methods match their intended use.
- **Data Type Optimization**: Advise on optimal data types and constraints based on the nature of the stored data.
- **Performance & Scalability**: Identify potential bottlenecks in large-scale data processing or concurrency and suggest solutions like index designs.

### 4. Physical Defect Pre-detection
- Report any missing mandatory fields (req, res) or absent table columns immediately based on the provided <Python Pre-check> results.

## Output Format (JSON)
- **thinking (th)**: Detailed analysis of discovered issues, potential risks, and technical rationale for advice (In Korean).
- **summary (sm)**: A clear 1-2 sentence summary of the overall design health.
- **recommendations (rc)**:
  - **priority**: Critical (Immediate fix required), Warning (Recommended improvement), Info (Best Practice).
  - **target**: Specific file name, table name, or API endpoint where the issue was found.
  - **action**: Concrete and technical guidance to solve the problem (e.g., "Change field name to...", "Add index to...").
"""


# ── 헬퍼 함수 ────────────────────────────────────────────

# _safe_get removed, now using safe_get from core.utils


def _run_python_precheck(apis: list, tables: list) -> list:
    """LLM 호출 전 Python으로 물리적 결함을 선행 검출"""
    gaps = []
    for api in apis:
        ep = safe_get(api, ["ep"]).upper()
        if not safe_get(api, ["req", "rq"]) and not any(m in ep for m in ["GET", "DELETE"]):
            gaps.append(f"API: {safe_get(api, ['ep'])} 의 req가 비어있음")
        if not safe_get(api, ["res", "rs"]):
            gaps.append(f"API: {safe_get(api, ['ep'])} 의 res가 비어있음")
    for table in tables:
        if not safe_get(table, ["cols", "cl"]):
            gaps.append(f"DB: {safe_get(table, ['name', 'nm'])} 테이블에 컬럼 없음")
    return gaps


def _expand_for_frontend(components: list, apis: list, tables: list) -> dict:
    """약어 필드 → 프론트엔드 풀네임 변환 (Translation Layer)"""
    # Components
    expanded_comps = []
    for c in components:
        expanded_comps.append({
            "component_name": safe_get(c, ["name", "nm"]),
            "role": safe_get(c, ["role", "rl"]),
            "domain": {"F": "Frontend", "B": "Backend"}.get(
                safe_get(c, ["domain", "dm"]), safe_get(c, ["domain", "dm"])
            ),
            "dependencies": [d.strip() for d in (safe_get(c, ["deps", "dp"]) or "").split(",") if d.strip()],
            "rtms": safe_get(c, ["rtms", "rt"]),
        })

    # APIs
    expanded_apis = []
    for a in apis:
        ep = safe_get(a, ["ep"])
        rq = safe_get(a, ["req", "rq"])
        rs = safe_get(a, ["res", "rs"])

        def _try_parse(val):
            if isinstance(val, dict): return val
            if isinstance(val, str):
                try: return json.loads(val.replace("'", '"'))
                except: return {"raw": val}
            return {}

        expanded_apis.append({
            "endpoint": ep, "description": ep,
            "request_schema": _try_parse(rq), "response_schema": _try_parse(rs),
        })

    # Tables
    expanded_tables = []
    for t in tables:
        nm = safe_get(t, ["name", "nm"])
        cl_raw = safe_get(t, ["cols", "cl"])
        columns = []
        if isinstance(cl_raw, str):
            for col_str in cl_raw.split(","):
                parts = col_str.strip().split(":")
                p0 = parts[0].strip() if len(parts) > 0 else ""
                p1 = parts[1].strip() if len(parts) > 1 else "string"
                p2 = parts[2].strip() if len(parts) > 2 else ""

                # 특수 케이스: "fk:table.col" 형태로 들어온 경우 처리
                if p0.lower() == "fk" and p1:
                    constr = f"FK({p1})"
                    if columns:
                        # 이전 컬럼에 제약 조건 병합
                        existing = columns[-1].get("constraints", "")
                        columns[-1]["constraints"] = f"{existing} {constr}".strip()
                        continue

                columns.append({
                    "name": p0,
                    "type": p1,
                    "constraints": p2,
                })
        elif isinstance(cl_raw, list):
            columns = cl_raw
        expanded_tables.append({
            "table_name": nm, "columns": columns,
        })

    return {"components": expanded_comps, "apis": expanded_apis, "tables": expanded_tables}


def _build_user_message(rtm: list, components: list, apis: list, tables: list, precheck_gaps: list) -> str:
    p_rtm = "\n".join(f"{safe_get(r, ['id', 'feature_id'])}:{safe_get(r, ['desc', 'description'])}" for r in rtm)
    p_comp = "\n".join(f"{safe_get(c, ['name', 'nm'])}:{safe_get(c, ['role', 'rl'])}" for c in components)
    p_api = "\n".join(f"{safe_get(a, ['ep'])}|{safe_get(a, ['req', 'rq'])}|{safe_get(a, ['res', 'rs'])}" for a in apis)
    p_db = "\n".join(f"{safe_get(t, ['name', 'nm'])}|{safe_get(t, ['cols', 'cl'])}" for t in tables)

    precheck_section = ""
    if precheck_gaps:
        precheck_section = f"\n## Python Pre-check 결함 ({len(precheck_gaps)}건):\n" + "\n".join(f"- {g}" for g in precheck_gaps)

    return (
        f"RTM:\n{p_rtm}\nComp:\n{p_comp}\nAPI:\n{p_api}\nDB:\n{p_db}"
        f"{precheck_section}\n\n"
        f"위 설계를 검증하고, 결함이 있으면 구체적 수정 가이드를 작성하세요."
    )


# ── 메인 노드 ────────────────────────────────────────────

@pipeline_node("sa_advisor")
def sa_advisor_node(ctx: NodeContext) -> dict:
    sget = ctx.sget
    logger.info("=== [Node Entry] sa_advisor_node ===")

    run_id = sget("run_id", "unknown")

    # 1. 데이터 수집
    merged_proj = sget("merged_project", {})
    rtm = (merged_proj.get("plan", {}).get("requirements_rtm", []) or
           sget("pm_bundle", {}).get("data", {}).get("rtm", []) or
           sget("features", []))

    unified_out = sget("sa_unified_modeler_output", {})
    apis = unified_out.get("apis", [])
    tables = unified_out.get("tables", [])
    components = sget("component_scheduler_output", {}).get("components", [])

    logger.info(f"Advisor input: RTM:{len(rtm)}, Comp:{len(components)}, API:{len(apis)}, Table:{len(tables)}")

    # 2. Python Pre-check
    precheck_gaps = _run_python_precheck(apis, tables)

    # 3. Translation Layer (약어 → 풀네임)
    expanded_data = _expand_for_frontend(components, apis, tables)

    # 4. sa_arch_bundle 조립
    sa_arch_bundle = {
        "phase": "SA",
        "metadata": {"version": "v1.0", "session_id": run_id},
        "data": expanded_data,
    }

    # 5. LLM 호출: 통합 QA 검증 + 수정 조언
    user_msg = _build_user_message(rtm, components, apis, tables, precheck_gaps)

    try:
        res = call_structured(
            api_key=ctx.api_key, model=ctx.model,
            schema=SAAdvisorOutput,
            system_prompt=SYSTEM_PROMPT,
            user_msg=user_msg,
            compress_prompt=False, temperature=0.1
        )

        # 7. 추천 사항 병합 및 구조화 (QA vs Architect)
        output = res.parsed
        raw_recs = output.recommendations
        seen_actions = set()
        qa_recs = []
        arch_recs = []

        # LLM 추천 사항 분류 및 중복 제거
        for r in raw_recs:
            act = r.action.strip()
            if act in seen_actions: continue
            seen_actions.add(act)
            
            rec_dict = r.model_dump()
            if r.priority == "Critical":
                qa_recs.append(rec_dict)
            else:
                arch_recs.append(rec_dict)

        # Pre-check gaps 추가 (QA로 분류)
        for gap in precheck_gaps:
            if gap not in seen_actions:
                qa_recs.append({
                    "priority": "Critical",
                    "target": gap.split(":")[0].strip() if ":" in gap else gap,
                    "action": gap,
                })
                seen_actions.add(gap)

        advisor_data = {
            "summary": output.summary,
            "qa_recommendations": qa_recs,
            "arch_recommendations": arch_recs,
            "recommendations": qa_recs + arch_recs, # 하위 호환성
            "status": "FAIL" if qa_recs else ("WARNING" if arch_recs else "PASS"),
            "gaps": [f"{r['target']}|{r['action']}" for r in qa_recs],
        }
        logger.info(f"SA Advisor: status={advisor_data['status']}, {len(advisor_data['recommendations'])} recommendations")

        return {
            "sa_advisor_output": advisor_data,
            "sa_output": {**advisor_data, "data": expanded_data},
            "sa_arch_bundle": sa_arch_bundle,
            "thinking_log": (sget("thinking_log", []) or []) + [
                {"node": "sa_advisor", "thinking": output.thinking or ""}
            ],
            "current_step": "sa_advisor_done",
        }

    except Exception as e:
        logger.exception(f"sa_advisor_node failed: {e}")
        # 폴백: LLM 없이 pre-check 결과만 사용
        fallback_recs = [{"priority": "Critical", "target": g.split(":")[0].strip(), "action": g} for g in precheck_gaps]
        advisor_data = {
            "summary": f"LLM 검증 실패 (폴백 사용): {str(e)[:100]}",
            "recommendations": fallback_recs,
            "status": "FAIL" if precheck_gaps else "WARNING",
            "gaps": precheck_gaps,
        }
        return {
            "sa_advisor_output": advisor_data,
            "sa_output": {**advisor_data, "data": expanded_data},
            "sa_arch_bundle": sa_arch_bundle,
            "thinking_log": (sget("thinking_log", []) or []) + [
                {"node": "sa_advisor", "thinking": f"LLM 실패, 폴백: {e}"}
            ],
        }
