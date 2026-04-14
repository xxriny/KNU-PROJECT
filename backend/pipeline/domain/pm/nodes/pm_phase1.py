"""
Agent Pipeline — Atomizer Node
입력 분석 → 모드 감지(CREATE/UPDATE/REVERSE_ENGINEER) → 원자 요구사항 추출
"""

import time

from pipeline.core.state import PipelineState, make_sget
from observability.logger import get_logger
from pipeline.core.utils import call_structured_with_usage
from pipeline.domain.pm.nodes.atomizer import AtomizerOutput
from version import DEFAULT_MODEL


# CREATE / UPDATE 모드용 프롬프트 (MECE 기획자 페르소나)
PM_SYSTEM_PROMPT = """당신은 수석 소프트웨어 기획자(PM)입니다.

<goal>
사용자의 비즈니스 아이디어나 기능 추가 요청을 완벽한 원자적 요구사항(RTM)으로 분해하고 기획하세요.
</goal>

<rules>
1) 반드시 단일 JSON 객체만 출력하세요.
2) 마크다운 코드블록, 설명 문장, 부가 텍스트를 절대 출력하지 마세요.
3) 단일 책임 원칙: 하나의 요구사항은 하나의 검증 가능한 기능만 포함.
4) [MECE 원칙] 요구사항 추출 시 상호 배제 및 전체 포괄(MECE) 원칙을 엄격히 적용하세요. 중복 아이디어는 하나로 병합하여 최적화된 목록을 도출하세요.
5) description에 AND/OR, 그리고/또는이 들어가면 분리 가능한지 판단하고, 분리 가능하면 요구사항을 나눠 작성.
6) 모호하면 action_type=Needs_Clarification, clarification_questions 2~3개, atomic_requirements는 빈 배열.
7) category는 다음 중 하나: Frontend, Backend, Architecture, Database, Security, AI/ML, Infrastructure
</rules>

<few_shot_create>
입력: "사용자는 이메일로 가입하고, 가입 후 대시보드에서 내 작업 목록을 본다."
추출될 요구사항 개념(반드시 JSON의 atomic_requirements 배열에 반영):
1) REQ-001: 이메일 가입 기능 (Security)
2) REQ-002: 가입 성공 후 사용자 기본 프로필 생성 (Backend)
3) REQ-003: 대시보드에서 사용자 작업 목록 조회 (Frontend)
</few_shot_create>

<few_shot_update>
입력 문맥: "기존 서비스는 이메일 로그인만 지원"
신규 아이디어: "구글 소셜 로그인을 추가"
출력 규칙: 위 정보를 반영한 단일 JSON 객체로 반환하고, 신규 REQ를 atomic_requirements에 포함.
</few_shot_update>
"""


# REVERSE_ENGINEER 모드용 프롬프트 (환각 방지 가드레일 리버스 엔지니어 페르소나)
REVERSE_SYSTEM_PROMPT = """당신은 수석 소프트웨어 리버스 엔지니어입니다.

<goal>
입력된 소스 코드 스캔 결과(AST 요약 및 함수 목록)를 분석하여,
'현재 시스템에 실제로 구현되어 있는 기능(As-Is)'만 추출하여 요구사항 명세서(RTM)로 복원하세요.
</goal>

<critical_rules>
1) [절대 준수] 새로운 아이디어나 기능을 절대 상상해서 추가하지 마세요. (No Hallucination)
2) [절대 준수] 오직 제공된 코드의 함수명, 클래스, docstring에 명시적으로 존재하는 기능만
   단일 책임 원칙에 따라 분해하세요. 중복 기능은 하나로 정리하되, 없는 기능을 지어내면 안 됩니다.
3) 반드시 단일 JSON 객체만 출력하세요.
4) category는 다음 중 하나: Frontend, Backend, Architecture, Database, Security, AI/ML, Infrastructure
</critical_rules>
"""


def atomizer_node(state: PipelineState) -> dict:
    try:
        sget = make_sget(state)

        api_key = sget("api_key", "")
        model = sget("model", DEFAULT_MODEL)
        ctx = (sget("project_context", "") or "").strip()
        idea = (sget("input_idea", "") or "").strip()
        requested_action_type = (sget("action_type", "") or "").strip().upper()
        sa_phase1 = sget("sa_phase1", {}) or {}

        # 모드에 따른 프롬프트 선택
        system_prompt = REVERSE_SYSTEM_PROMPT if requested_action_type == "REVERSE_ENGINEER" else PM_SYSTEM_PROMPT

        parts = []
        if requested_action_type in {"CREATE", "UPDATE", "REVERSE_ENGINEER"}:
            parts.append(f"<requested_action_type>\n{requested_action_type}\n</requested_action_type>")
        if ctx:
            parts.append(f"<project_context>\n{ctx}\n</project_context>")
        if idea:
            parts.append(f"<input_idea>\n{idea}\n</input_idea>")
        # REVERSE 모드: sa_phase1 스캔 함수 목록을 명시 주입 (환각 방지 가드레일)
        if requested_action_type == "REVERSE_ENGINEER" and sa_phase1:
            scanned_funcs = sa_phase1.get("sample_functions", []) or []
            if scanned_funcs:
                funcs_text = "\n".join(f"- {f}" for f in scanned_funcs)
                parts.append(f"<scanned_functions>\n{funcs_text}\n</scanned_functions>")
        if requested_action_type == "UPDATE" and sa_phase1:
            analysis_lines = []
            if sa_phase1.get("architecture_assessment"):
                analysis_lines.append(f"- architecture_assessment: {sa_phase1['architecture_assessment']}")
            if sa_phase1.get("scanned_files") is not None:
                analysis_lines.append(f"- scanned_files: {sa_phase1.get('scanned_files', 0)}")
            if sa_phase1.get("scanned_functions") is not None:
                analysis_lines.append(f"- scanned_functions: {sa_phase1.get('scanned_functions', 0)}")
            if sa_phase1.get("languages"):
                analysis_lines.append(f"- languages: {sa_phase1['languages']}")
            if sa_phase1.get("key_modules"):
                analysis_lines.append(f"- key_modules: {sa_phase1['key_modules']}")
            if sa_phase1.get("concerns"):
                analysis_lines.append(f"- concerns: {sa_phase1['concerns']}")
            if sa_phase1.get("recommended_focus"):
                analysis_lines.append(f"- recommended_focus: {sa_phase1['recommended_focus']}")
            if analysis_lines:
                parts.append("<existing_code_analysis>\n" + "\n".join(analysis_lines) + "\n</existing_code_analysis>")
        user_content = "\n\n".join(parts)

        if not user_content:
            return {"error": "입력이 비어있습니다.", "current_step": "atomizer"}

        t0 = time.perf_counter()

        out, usage = call_structured_with_usage(
            api_key=api_key,
            model=model,
            schema=AtomizerOutput,
            system_prompt=system_prompt,
            user_msg=user_content,
            max_retries=3,
            temperature=0.1,
        )

        latency_ms = int((time.perf_counter() - t0) * 1000)

        metadata = (out.metadata.model_dump() if out.metadata else {}) or {"status": "Success"}
        if requested_action_type in {"CREATE", "UPDATE", "REVERSE_ENGINEER"} and metadata.get("action_type") != "Needs_Clarification":
            metadata["action_type"] = requested_action_type
        # 토큰/지연시간은 LLM 추론값이 아니라 런타임 측정값을 주입한다.
        metadata["latency_ms"] = latency_ms
        metadata["input_tokens"] = usage.get("input_tokens", 0)
        metadata["output_tokens"] = usage.get("output_tokens", 0)

        raw_reqs = [r.model_dump() for r in (out.atomic_requirements or [])]
        # LLM 환각 방어: 실제 배열 길이로 덮어씀
        metadata["total_requirements"] = len(raw_reqs)
        thinking = (out.thinking_process or "").strip() or "원자화 분석 완료"

        return {
            "raw_requirements": raw_reqs,
            "metadata": metadata,
            "clarification_questions": out.clarification_questions or [],
            "action_type": metadata.get("action_type", "CREATE"),
            "thinking_log": (sget("thinking_log", []) or []) + [{"node": "atomizer", "thinking": thinking}],
            "current_step": "atomizer_done",
        }

    except Exception as e:
        get_logger().exception("atomizer_node failed")
        return {
            "error": f"atomizer 실패: {e}",
            "thinking_log": [{"node": "atomizer", "thinking": f"오류: {e}"}],
            "current_step": "error",
        }

