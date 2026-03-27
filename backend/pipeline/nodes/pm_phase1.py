"""
Agent Pipeline — Atomizer Node 
입력 분석 → 모드 감지(CREATE/UPDATE/REVERSE_ENGINEER) → 원자 요구사항 추출
"""

import time
import traceback
from pydantic import BaseModel, Field
from pipeline.state import PipelineState
from pipeline.utils import call_structured_with_usage


class AtomicRequirement(BaseModel):
    REQ_ID: str = Field(description="고유 ID. 예: REQ-001")
    category: str = Field(description="Frontend|Backend|Architecture|Database|Security|AI/ML|Infrastructure")
    description: str = Field(description="한국어 1문장, 테스트 가능한 단일 책임 기능")


class AtomizerMetadata(BaseModel):
    project_name: str = Field(default="Untitled")
    action_type: str = Field(description="CREATE|UPDATE|REVERSE_ENGINEER|Needs_Clarification")
    status: str = Field(description="Success|Needs_Clarification")
    total_requirements: int = Field(default=0)


class AtomizerOutput(BaseModel):
    thinking_process: str = Field(default="", description="모드 판별 및 분해 근거 요약")
    metadata: AtomizerMetadata
    clarification_questions: list[str] = Field(default_factory=list)
    atomic_requirements: list[AtomicRequirement] = Field(default_factory=list)


SYSTEM_PROMPT = """당신은 요구사항 원자화 전문가입니다.

<goal>
비즈니스 아이디어 또는 기존 시스템 설명을 원자적 요구사항으로 분해하세요.
</goal>

<modes>
입력에 <requested_action_type>이 주어지면 해당 모드를 최우선으로 적용하세요.
주어지지 않았다면 아래 규칙으로 추론하세요:
- input_idea만 존재: CREATE
- project_context + input_idea 존재: UPDATE
- project_context만 존재: REVERSE_ENGINEER
</modes>

<rules>
1) 반드시 단일 JSON 객체만 출력하세요.
2) 마크다운 코드블록, 설명 문장, 부가 텍스트를 절대 출력하지 마세요.
3) 단일 책임 원칙: 하나의 요구사항은 하나의 검증 가능한 기능만 포함.
4) description에 AND/OR, 그리고/또는이 들어가면 분리 가능한지 먼저 판단하고, 분리 가능하면 요구사항을 나눠 작성.
5) 모호하면 action_type=Needs_Clarification, clarification_questions 2~3개, atomic_requirements는 빈 배열.
6) category는 다음 중 하나: Frontend, Backend, Architecture, Database, Security, AI/ML, Infrastructure
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

<few_shot_reverse_engineer>
입력 문맥: "현재 시스템에는 게시글 작성/조회/수정이 존재"
출력 규칙: 기능 단위로 REQ를 분해하여 atomic_requirements 배열에 JSON으로 반환.
</few_shot_reverse_engineer>
"""


def atomizer_node(state: PipelineState) -> dict:
    try:
        # TypedDict / 객체 모두 호환
        def sget(key: str, default=None):
            if hasattr(state, "get"):
                val = state.get(key, default)
            else:
                val = getattr(state, key, default)
            return default if val is None else val

        api_key = sget("api_key", "")
        model = sget("model", "gemini-2.5-flash")
        ctx = (sget("project_context", "") or "").strip()
        idea = (sget("input_idea", "") or "").strip()
        requested_action_type = (sget("action_type", "") or "").strip().upper()
        sa_phase1 = sget("sa_phase1", {}) or {}

        parts = []
        if requested_action_type in {"CREATE", "UPDATE", "REVERSE_ENGINEER"}:
            parts.append(f"<requested_action_type>\n{requested_action_type}\n</requested_action_type>")
        if ctx:
            parts.append(f"<project_context>\n{ctx}\n</project_context>")
        if idea:
            parts.append(f"<input_idea>\n{idea}\n</input_idea>")
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
            system_prompt=SYSTEM_PROMPT,
            user_msg=user_content,
            max_retries=3,    # 내부 재시도
            temperature=0.2,
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
        traceback.print_exc()
        return {
            "error": f"atomizer 실패: {e}",
            "thinking_log": [{"node": "atomizer", "thinking": f"오류: {e}"}],
            "current_step": "error",
        }