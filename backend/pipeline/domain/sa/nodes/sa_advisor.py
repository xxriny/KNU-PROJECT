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
from pipeline.core.utils import call_structured
from pipeline.domain.sa.schemas import SAAdvisorOutput
from observability.logger import get_logger

logger = get_logger()

SYSTEM_PROMPT = """# 역할: 시니어 아키텍처 어드바이저 & QA 검증관
## 목표: 설계 데이터의 결함을 검증하고, 개발자에게 구체적이고 실행 가능한 수정 가이드를 제공.

## 검증 규칙:
1. **빈 스키마 예외**: GET/DELETE의 Request Body `{}`는 정상.
2. **명칭 일치성(Zero-Tolerance)**: 컴포넌트-API-DB 간 필드명 불일치 시 Critical.
3. **타입/무결성**: 타입 코드 및 존재하지 않는 FK 참조 전수 조사.
4. **전수 커버리지**: 요구사항(RTM) 중 어떤 API/DB로도 해결되지 않는 항목 식별.

## 조언 규칙:
- **Thinking**: 한국어 핵심 단어 **3개 이내**. 문장 금지.
- **언어**: 모든 내용은 반드시 한국어로 작성.
- **구체성**: "수정하세요" 같은 추상적 조언 금지. 테이블명, 필드명, API 경로를 명시.
- **우선순위**: Critical(즉시 수정) → Warning(권장) → Info(참고) 순.
- **간결성**: 각 조언은 2줄 이내로 작성.
- **summary**: 전체 검증 결과를 1~2문장으로 요약.
"""


# ── 헬퍼 함수 ────────────────────────────────────────────

def _safe_get(obj, keys, default=""):
    for k in keys:
        if hasattr(obj, 'get'):
            v = obj.get(k)
            if v: return v
        v = getattr(obj, k, None)
        if v: return v
    return default


def _run_python_precheck(apis: list, tables: list) -> list:
    """LLM 호출 전 Python으로 물리적 결함을 선행 검출"""
    gaps = []
    for api in apis:
        ep = _safe_get(api, ["ep"]).upper()
        if not _safe_get(api, ["req", "rq"]) and not any(m in ep for m in ["GET", "DELETE"]):
            gaps.append(f"API: {_safe_get(api, ['ep'])} 의 req가 비어있음")
        if not _safe_get(api, ["res", "rs"]):
            gaps.append(f"API: {_safe_get(api, ['ep'])} 의 res가 비어있음")
    for table in tables:
        if not _safe_get(table, ["cols", "cl"]):
            gaps.append(f"DB: {_safe_get(table, ['name', 'nm'])} 테이블에 컬럼 없음")
    return gaps


def _expand_for_frontend(components: list, apis: list, tables: list) -> dict:
    """약어 필드 → 프론트엔드 풀네임 변환 (Translation Layer)"""
    # Components
    expanded_comps = []
    for c in components:
        expanded_comps.append({
            "component_name": _safe_get(c, ["name", "nm"]),
            "role": _safe_get(c, ["role", "rl"]),
            "domain": {"F": "Frontend", "B": "Backend"}.get(
                _safe_get(c, ["domain", "dm"]), _safe_get(c, ["domain", "dm"])
            ),
            "dependencies": [d.strip() for d in (_safe_get(c, ["deps", "dp"]) or "").split(",") if d.strip()],
            "rtms": _safe_get(c, ["rtms", "rt"]),
        })

    # APIs
    expanded_apis = []
    for a in apis:
        ep = _safe_get(a, ["ep"])
        rq = _safe_get(a, ["req", "rq"])
        rs = _safe_get(a, ["res", "rs"])

        def _try_parse(val):
            if isinstance(val, dict): return val
            if isinstance(val, str):
                try: return json.loads(val.replace("'", '"'))
                except: return {"raw": val}
            return {}

        expanded_apis.append({
            "endpoint": ep, "description": ep,
            "request_schema": _try_parse(rq), "response_schema": _try_parse(rs),
            "ep": ep, "rq": rq, "rs": rs,
        })

    # Tables
    expanded_tables = []
    for t in tables:
        nm = _safe_get(t, ["name", "nm"])
        cl_raw = _safe_get(t, ["cols", "cl"])
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
            "nm": nm, "cl": cl_raw,
        })

    return {"components": expanded_comps, "apis": expanded_apis, "tables": expanded_tables}


def _build_rag_context(session_id: str) -> str:
    """RAG에서 해당 세션의 PM/SA 요약 정보를 검색 (토큰 절약)"""
    try:
        from pipeline.domain.pm.nodes.pm_db import _get_collection
        collection = _get_collection()
        results = collection.get(
            where={"session_id": session_id},
            include=["metadatas", "documents"]
        )
        if not results or not results["ids"]:
            return "RAG에 저장된 데이터 없음"
        summaries = []
        for i in range(len(results["ids"])):
            meta = results["metadatas"][i]
            doc = results["documents"][i]
            artifact_type = meta.get("artifact_type", "unknown")
            phase = meta.get("phase", "?")
            summaries.append(f"[{phase}/{artifact_type}] {doc[:500]}")
        return "\n---\n".join(summaries)
    except Exception as e:
        logger.warning(f"RAG context retrieval failed: {e}")
        return "RAG 검색 실패"


def _build_user_message(rtm: list, components: list, apis: list, tables: list, precheck_gaps: list, rag_ctx: str) -> str:
    p_rtm = "\n".join(f"{_safe_get(r, ['id'])}:{_safe_get(r, ['desc'])}" for r in rtm)
    p_comp = "\n".join(f"{_safe_get(c, ['name', 'nm'])}:{_safe_get(c, ['role', 'rl'])}" for c in components)
    p_api = "\n".join(f"{_safe_get(a, ['ep'])}|{_safe_get(a, ['req', 'rq'])}|{_safe_get(a, ['res', 'rs'])}" for a in apis)
    p_db = "\n".join(f"{_safe_get(t, ['name', 'nm'])}|{_safe_get(t, ['cols', 'cl'])}" for t in tables)
    
    precheck_section = ""
    if precheck_gaps:
        precheck_section = f"\n## Python Pre-check 결함 ({len(precheck_gaps)}건):\n" + "\n".join(f"- {g}" for g in precheck_gaps)
    
    return (
        f"RTM:\n{p_rtm}\nComp:\n{p_comp}\nAPI:\n{p_api}\nDB:\n{p_db}"
        f"{precheck_section}"
        f"\n\n## RAG Context (요약)\n{rag_ctx}\n\n"
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

    # 5. RAG 컨텍스트 수집 (토큰 절약형)
    rag_context = _build_rag_context(run_id)

    # 6. LLM 호출: 통합 QA 검증 + 수정 조언
    user_msg = _build_user_message(rtm, components, apis, tables, precheck_gaps, rag_context)

    try:
        res = call_structured(
            api_key=ctx.api_key, model=ctx.model,
            schema=SAAdvisorOutput,
            system_prompt=SYSTEM_PROMPT,
            user_msg=user_msg,
            compress_prompt=True, temperature=0.1
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
