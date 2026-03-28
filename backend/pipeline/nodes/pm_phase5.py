from observability.logger import get_logger
"""
노드 5 — 롤링 컨텍스트 상태 명세서 (Context Spec)

Pydantic 구조화 출력 강제. 전체 파이프라인 결과를 종합하여
SA 에이전트에게 전달할 명세서 생성.
파이프라인 완료 시 PROJECT_STATE.md를 backend/Data/ 폴더에 저장한다.
"""

import json
import os
from datetime import datetime
from connectors.result_logger import LOG_DIR, _safe_filename
from pipeline.state import PipelineState, sget as state_sget
from pipeline.schemas import ContextSpecOutput
from pipeline.utils import call_structured_with_thinking

SYSTEM_PROMPT = """\
당신은 롤링 컨텍스트 명세서 작성 전문가입니다.
파이프라인의 모든 산출물을 종합하여 SA 에이전트에게 전달할 명세서를 생성하세요.

[규칙]
1. summary: 프로젝트 개요 (한국어 2-3문장)
2. key_decisions: 내린 아키텍처/비즈니스 결정 사항들
3. open_questions: 검증이 필요한 미해결 항목들
4. tech_stack_suggestions: 추론된 기술스택 추천사항
   (manifest에서 발견된 프레임워크를 우선하고, 누락된 부분은 요구사항 기반으로 확장하세요)
    가능하면 각 기술 스택 제안은 manifest 근거 여부를 일관되게 반영하세요.
5. risk_factors: 식별된 위험요소들
6. next_steps: SA 에이전트를 위한 추천 다음 단계
7. thinking은 3줄 이내로 작성하세요."""

_LOG_DIR = LOG_DIR


def _build_tech_stack_details(plain_suggestions: list[str], sa_phase1: dict) -> tuple[list[dict], list[str], float]:
    framework_evidence = sa_phase1.get("framework_evidence", []) or []
    manifest_map: dict[str, dict] = {}
    for item in framework_evidence:
        name = (item.get("framework") or "").strip()
        if not name:
            continue
        key = name.lower()
        manifest_map.setdefault(key, {"name": name, "evidence": []})
        ref = f"{item.get('file', '')}: {item.get('reason', '')}".strip(": ")
        if ref and ref not in manifest_map[key]["evidence"]:
            manifest_map[key]["evidence"].append(ref)

    detailed = []
    seen = set()

    for key, item in manifest_map.items():
        seen.add(key)
        detailed.append({
            "name": item["name"],
            "source": "manifest",
            "confidence": min(1.0, 0.75 + len(item["evidence"]) * 0.08),
            "evidence": item["evidence"][:3],
        })

    for suggestion in plain_suggestions or []:
        name = (suggestion or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        detailed.append({
            "name": name,
            "source": "inferred",
            "confidence": 0.55,
            "evidence": ["requirements/context 기반 추론"],
        })

    plain = [item["name"] for item in detailed]
    if not detailed:
        return [], plain_suggestions or [], 0.0

    score = round(sum(item["confidence"] for item in detailed) / len(detailed), 2)
    return detailed, plain, score


def _save_project_state_md(spec: dict, project_name: str, run_id: str = "") -> str:
    """
    PROJECT_STATE.md를 backend/Data/ 폴더에 저장.
    타임스탬프를 포함하므로 같은 프로젝트 여러 실행 기록이 보존된다.
    저장 실패 시 예외를 던지지 않고 빈 문자열 반환.
    """
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        ts = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = _safe_filename(project_name)
        filename = f"{ts}_{safe_name}_PROJECT_STATE.md"
        filepath = os.path.join(_LOG_DIR, filename)

        def _list_items(items: list) -> str:
            return "\n".join(f"- {item}" for item in items) if items else "- (없음)"

        lines = [
            f"# PROJECT_STATE — {project_name}",
            f"> 생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            spec.get("summary", "(요약 없음)"),
            "",
            "## Key Decisions",
            _list_items(spec.get("key_decisions", [])),
            "",
            "## Open Questions",
            _list_items(spec.get("open_questions", [])),
            "",
            "## Tech Stack Suggestions",
            _list_items(spec.get("tech_stack_suggestions", [])),
            "",
            "## Risk Factors",
            _list_items(spec.get("risk_factors", [])),
            "",
            "## Next Steps",
            _list_items(spec.get("next_steps", [])),
        ]

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        get_logger(sget("run_id", "")).info(f"[ContextSpec] PROJECT_STATE.md saved → {filepath}")
        return filepath

    except Exception as e:
        get_logger(sget("run_id", "")).warning(f"[ContextSpec] Warning: PROJECT_STATE.md 저장 실패: {e}")
        return ""


def context_spec_node(state: PipelineState) -> dict:
    def sget(key, default=None):
        return state_sget(state, key, default)

    rtm = sget("rtm_matrix", [])
    sg = sget("semantic_graph", {})
    meta = sget("metadata", {})
    sa_phase1 = sget("sa_phase1", {}) or {}
    
    # 원본 아이디어와 문맥을 가져옵니다. (컨텍스트 기아 해결)
    project_context = sget("project_context", "")
    input_idea = sget("input_idea", "")

    context_input = {
        "project_name": meta.get("project_name", ""),
        "action_type": sget("action_type", ""),
        "original_context": project_context,  # 추가된 핵심 컨텍스트
        "original_idea": input_idea,          # 추가된 핵심 컨텍스트
        "total_requirements": len(rtm),
        "must_count": sum(1 for r in rtm if r.get("priority") == "Must-have"),
        "should_count": sum(1 for r in rtm if r.get("priority") == "Should-have"),
        "could_count": sum(1 for r in rtm if r.get("priority") == "Could-have"),
        "categories": list(set(r.get("category", "") for r in rtm)),
        "semantic_nodes": len(sg.get("nodes", [])),
        "semantic_edges": len(sg.get("edges", [])),
        "manifest_detected_frameworks": sa_phase1.get("detected_frameworks", []),
        "manifest_evidence_count": len(sa_phase1.get("framework_evidence", []) or []),
        "manifest_languages": len(sa_phase1.get("languages", {}) or {}),
        # 5개만 넘기는 대신, 비용 절감을 위해 ID와 카테고리 등 핵심 뼈대만 요약해서 전체를 넘김
        "requirements_summary": [{"ID": r.get("REQ_ID"), "cat": r.get("category"), "desc": r.get("description")} for r in rtm]
    }

    user_msg = f"다음 파이프라인 결과를 종합하여 Context 명세서를 작성하세요:\n```json\n{json.dumps(context_input, ensure_ascii=False)}\n```"

    try:
        result, thinking = call_structured_with_thinking(
            api_key=sget("api_key", ""),
            model=sget("model", "gemini-2.5-flash"),
            schema=ContextSpecOutput,
            system_prompt=SYSTEM_PROMPT,
            user_msg=user_msg,
            max_retries=3,
        )

        spec = result.model_dump()
        spec.pop("thinking", None)
        detailed, plain, score = _build_tech_stack_details(spec.get("tech_stack_suggestions", []), sa_phase1)
        spec["tech_stack_suggestions_detailed"] = detailed
        spec["tech_stack_suggestions"] = plain
        spec["stack_confidence_score"] = score

        project_name = meta.get("project_name", "unnamed")
        state_path = _save_project_state_md(spec, project_name, sget("run_id", ""))

        return {
            "context_spec": spec,
            # "requirements_rtm": final_rtm, <-- 삭제!!! (데이터 무한 증식 버그의 원인)
            "metadata": {**meta, "status": "Completed"},
            "project_state_path": state_path,
            "thinking_log": sget("thinking_log", []) + [{"node": "context_spec", "thinking": thinking}],
            "current_step": "context_spec_done",
        }

    except Exception as e:
        return {
            "context_spec": {"summary": f"Error: {e}", "key_decisions": [], "open_questions": [],
                             "tech_stack_suggestions": [], "tech_stack_suggestions_detailed": [], "stack_confidence_score": 0.0,
                             "risk_factors": [], "next_steps": []},
            # "requirements_rtm": sget("rtm_matrix", []), <-- 삭제!!!
            "metadata": {**meta, "status": "Completed_with_errors"},
            "project_state_path": "",
            "thinking_log": sget("thinking_log", []) + [{"node": "context_spec", "thinking": f"Error: {e}"}],
            "current_step": "context_spec_done",
        }


