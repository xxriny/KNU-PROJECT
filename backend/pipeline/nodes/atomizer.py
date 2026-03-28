import time
import traceback
from pydantic import BaseModel, Field
from pipeline.state import PipelineState, sget
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

# 1. CREATE 및 UPDATE 모드용 프롬프트 (MECE 기획자 페르소나)
PM_SYSTEM_PROMPT = """당신은 수석 소프트웨어 기획자(PM)입니다.

<goal>
사용자의 비즈니스 아이디어나 기능 추가 요청을 완벽한 원자적 요구사항(RTM)으로 분해하고 기획하세요.
</goal>

<rules>
1) 반드시 단일 JSON 객체만 출력하세요.
2) 단일 책임 원칙: 하나의 요구사항은 하나의 검증 가능한 기능만 포함해야 합니다.
3) [MECE 원칙 적용] 요구사항을 추출할 때 상호 배제 및 전체 포괄(MECE) 원칙을 엄격히 적용하세요. 중복되는 아이디어나 기능은 하나로 깔끔하게 병합하여 최적화된 요구사항 목록을 도출하세요.
4) description에 AND/OR가 들어가면 분리 가능한지 판단하고, 가능하면 요구사항을 나누세요.
5) 입력 내용이 너무 모호하여 기획이 불가능하면 action_type=Needs_Clarification으로 설정하고 clarification_questions를 작성하세요.
6) category는 다음 중 하나로 지정하세요: Frontend, Backend, Architecture, Database, Security, AI/ML, Infrastructure
</rules>
"""

# 2. REVERSE ENGINEER 모드용 프롬프트 (가드레일 리버스 엔지니어 페르소나)
REVERSE_SYSTEM_PROMPT = """당신은 수석 소프트웨어 리버스 엔지니어입니다.

<goal>
입력된 소스 코드 스캔 결과(AST 요약)를 분석하여, '현재 시스템에 실제로 구현되어 있는 기능(As-Is)'만 추출하여 요구사항 명세서(RTM)로 복원하세요.
</goal>

<critical_rules>
1) [절대 준수] 새로운 아이디어나 기능을 절대 상상해서 추가하지 마세요. (No Hallucination)
2) [절대 준수] 오직 제공된 코드의 함수명, 클래스, docstring에 명시적으로 존재하는 기능만 단일 책임 원칙에 따라 분해하세요. 중복되는 기능이 있다면 하나로 깔끔하게 정리하되, 없는 기능을 지어내면 안 됩니다.
3) 반드시 단일 JSON 객체만 출력하세요.
4) category는 다음 중 하나로 지정하세요: Frontend, Backend, Architecture, Database, Security, AI/ML, Infrastructure
</critical_rules>
"""

def atomizer_node(state: PipelineState) -> dict:
    try:
        api_key = sget(state, "api_key", "")
        model = sget(state, "model", "gemini-2.5-flash")
        idea = (sget(state, "input_idea", "") or "").strip()
        requested_action_type = (sget(state, "action_type", "") or "").strip().upper()

        # 3. 모드에 따른 동적 프롬프트 선택 및 컨텍스트 주입 분기
        if requested_action_type == "REVERSE_ENGINEER":
            system_prompt = REVERSE_SYSTEM_PROMPT
            # 역공학 시 sa_phase1에서 스캔한 AST 데이터를 읽어옵니다.
            sa_data = sget(state, "sa_phase1", {})
            scanned_funcs = sa_data.get("sample_functions", [])
            ctx = f"기존 코드 함수 목록: {scanned_funcs}"
        else:
            system_prompt = PM_SYSTEM_PROMPT
            ctx = (sget(state, "project_context", "") or "").strip()

        parts = []
        if requested_action_type in {"CREATE", "UPDATE", "REVERSE_ENGINEER"}:
            parts.append(f"<requested_action_type>\n{requested_action_type}\n</requested_action_type>")
        if ctx:
            parts.append(f"<project_context>\n{ctx}\n</project_context>")
        if idea:
            parts.append(f"<input_idea>\n{idea}\n</input_idea>")
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
            temperature=0.1,  # 일관성 및 환각 억제를 위해 온도 고정
        )

        latency_ms = int((time.perf_counter() - t0) * 1000)

        metadata = (out.metadata.model_dump() if out.metadata else {}) or {"status": "Success"}
        if requested_action_type in {"CREATE", "UPDATE", "REVERSE_ENGINEER"} and metadata.get("action_type") != "Needs_Clarification":
            metadata["action_type"] = requested_action_type
            
        metadata["latency_ms"] = latency_ms
        metadata["input_tokens"] = usage.get("input_tokens", 0)
        metadata["output_tokens"] = usage.get("output_tokens", 0)

        raw_reqs = [r.model_dump() for r in (out.atomic_requirements or [])]
        metadata["total_requirements"] = len(raw_reqs)
        thinking = (out.thinking_process or "").strip() or "원자화 분석 완료"

        return {
            "raw_requirements": raw_reqs,
            "metadata": metadata,
            "clarification_questions": out.clarification_questions or [],
            "action_type": metadata.get("action_type", "CREATE"),
            "thinking_log": (sget(state, "thinking_log", []) or []) + [{"node": "atomizer", "thinking": thinking}],
            "current_step": "atomizer_done",
        }

    except Exception as e:
        traceback.print_exc()
        return {
            "error": f"atomizer 실패: {e}",
            "thinking_log": [{"node": "atomizer", "thinking": f"오류: {e}"}],
            "current_step": "error",
        }