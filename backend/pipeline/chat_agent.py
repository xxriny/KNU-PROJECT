"""
PM Agent Pipeline — 채팅 에이전트 v2.0

두 가지 모드:
  1. REVISE 모드: 기존 RTM을 자연어 지시로 수정 (지속 대화 히스토리 유지)
  2. IDEA 모드: 아이디어가 없는 사용자와 자유 대화 → 아이디어 발전 → 분석 준비

REVISE 모드는 대화 히스토리를 누적하여 "A 수정 → B도 수정 → C 추가" 같은
연속 수정이 자연스럽게 이어진다.
"""

import json
from typing import List, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────
# 공통 직렬화 헬퍼
# ─────────────────────────────────────────────────────────────

def _ser(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if isinstance(obj, dict):
        return obj
    return str(obj)


# ─────────────────────────────────────────────────────────────
# REVISE 모드 스키마
# ─────────────────────────────────────────────────────────────

class RTMRevision(BaseModel):
    REQ_ID: str = Field(description="고유 ID (예: REQ-001)")
    category: str = Field(description="카테고리 (Backend/Frontend/Database 등)")
    description: str = Field(description="기능 설명 (한국어)")
    priority: str = Field(description="Must-have | Should-have | Could-have")
    rationale: str = Field(default="", description="우선순위 근거")
    depends_on: List[str] = Field(default_factory=list, description="선행 REQ_ID 목록")
    test_criteria: str = Field(default="미정", description="테스트 수락 기준")


class ChatRevisionOutput(BaseModel):
    thinking: str = Field(default="", description="수정 추론 과정 (2줄 이내)")
    reply: str = Field(default="", description="사용자에게 보여줄 수정 완료 메시지 (1-2문장, 한국어)")
    summary: str = Field(default="", description="수정된 프로젝트 요약 (한국어, 2-3문장)")
    key_decisions: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
    tech_stack_suggestions: List[str] = Field(default_factory=list)
    risk_factors: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    requirements: List[RTMRevision] = Field(description="수정된 전체 RTM 요구사항 목록")


REVISE_SYSTEM_PROMPT = """당신은 PM 에이전트의 RTM 수정 전문가입니다.
사용자의 자연어 지시를 이해하여 기존 RTM(요구사항 추적 매트릭스)을 정밀하게 수정합니다.

## 핵심 원칙
- 사용자가 "~를 추가해줘", "~를 삭제해줘", "~의 우선순위를 바꿔줘", "~를 수정해줘" 등 어떤 형태로 요청해도 의도를 파악하여 처리하세요.
- 수정이 필요한 항목만 변경하고, 나머지는 그대로 유지하세요.
- 새 요구사항 추가 시 기존 REQ_ID 번호 체계를 이어서 부여하세요.
- 삭제 시 해당 항목을 참조하는 depends_on도 정리하세요.
- context_spec(summary, key_decisions 등)도 변경 내용에 맞게 업데이트하세요.
- 반드시 전체 RTM 목록을 반환하세요 (수정되지 않은 항목도 포함).
- reply 필드에 "REQ-005를 Must-have로 변경하고 결제 모듈 요구사항 2개를 추가했습니다." 같이 간결하게 무엇을 했는지 알려주세요.
- 모든 설명은 한국어로 작성하세요.
"""


# ─────────────────────────────────────────────────────────────
# IDEA 모드 스키마
# ─────────────────────────────────────────────────────────────

class IdeaChatOutput(BaseModel):
    thinking: str = Field(default="", description="내부 추론 (표시 안 함)")
    reply: str = Field(description="사용자에게 보여줄 응답 (한국어, 친근하고 구체적으로)")
    is_ready: bool = Field(default=False, description="아이디어가 충분히 구체화되어 분석을 시작할 수 있으면 True")
    idea_summary: str = Field(default="", description="is_ready=True일 때 분석에 넘길 아이디어 요약 (한국어, 3-5문장)")
    suggested_mode: str = Field(default="create", description="추천 모드: create | update | reverse")


IDEA_SYSTEM_PROMPT = """당신은 PM 에이전트의 아이디어 발굴 도우미입니다.
사용자가 막연한 아이디어를 가지고 있거나, 아직 아이디어가 없는 상태입니다.
친근하고 전문적인 PM의 시각으로 대화하며 아이디어를 구체화해 주세요.

## 역할
- 사용자의 아이디어를 경청하고 핵심 가치, 타겟 사용자, 주요 기능을 파악하세요.
- 질문을 통해 아이디어를 구체화하되, 한 번에 1-2개 질문만 하세요.
- 아이디어가 충분히 구체화되면 (타겟 + 핵심기능 + 목적이 명확) is_ready=True로 설정하고, idea_summary에 분석용 요약을 작성하세요.
- 기존 프로젝트 기능 확장이면 suggested_mode="update", 역공학이면 "reverse", 신규면 "create"로 설정하세요.

## 대화 스타일
- 짧고 명확하게 답변하세요 (3-4문장 이내).
- 사용자가 "분석 시작해줘", "이걸로 해줘" 같은 말을 하면 즉시 is_ready=True로 설정하세요.
- 한국어로만 대화하세요.
"""


# ─────────────────────────────────────────────────────────────
# 대화 히스토리 관리
# ─────────────────────────────────────────────────────────────

class ChatHistory:
    """대화 히스토리 — 앱 레벨에서 인스턴스를 유지"""

    def __init__(self):
        self._messages: List[dict] = []  # [{"role": "user"|"assistant", "content": str}]

    def add_user(self, content: str):
        self._messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str):
        self._messages.append({"role": "assistant", "content": content})

    def get_recent(self, max_turns: int = 6) -> List[dict]:
        """최근 N턴만 반환 (토큰 절약)"""
        return self._messages[-(max_turns * 2):]

    def clear(self):
        self._messages.clear()

    def __len__(self):
        return len(self._messages)


# ─────────────────────────────────────────────────────────────
# REVISE 모드 실행
# ─────────────────────────────────────────────────────────────

def run_chat_revision(
    api_key: str,
    model: str,
    user_request: str,
    previous_result: dict,
    history: Optional[ChatHistory] = None,
    on_status=None,
) -> dict:
    """
    REVISE 모드: 기존 RTM을 자연어 지시로 수정.
    history가 주어지면 대화 히스토리를 누적하여 연속 수정 지원.

    Returns:
        수정된 result dict + "agent_reply" 키 (사용자에게 보여줄 메시지)
    """
    from pipeline.utils import call_structured

    if on_status:
        on_status("chat_agent", "running")

    rtm_list = previous_result.get("requirements_rtm", [])
    ctx_spec = previous_result.get("context_spec", {})
    sg = previous_result.get("semantic_graph", {})

    rtm_serialized = [_ser(r) for r in rtm_list]
    ctx_serialized = _ser(ctx_spec) if ctx_spec else {}

    # 대화 히스토리 컨텍스트 구성
    history_ctx = ""
    if history and len(history) > 0:
        recent = history.get_recent(max_turns=4)
        turns = []
        for msg in recent:
            role = "사용자" if msg["role"] == "user" else "에이전트"
            turns.append(f"[{role}] {msg['content'][:200]}")
        history_ctx = "\n=== 이전 대화 ===\n" + "\n".join(turns) + "\n"

    user_msg = (
        f"=== 현재 RTM ({len(rtm_serialized)}개 요구사항) ===\n"
        f"{json.dumps(rtm_serialized, ensure_ascii=False, indent=1)[:6000]}\n\n"
        f"=== 현재 Context Spec ===\n"
        f"{json.dumps(ctx_serialized, ensure_ascii=False, indent=1)[:2000]}\n"
        f"{history_ctx}\n"
        f"=== 수정 요청 ===\n"
        f"{user_request}\n\n"
        f"위 RTM을 수정 요청에 맞게 업데이트하세요. 수정되지 않은 항목도 모두 포함하여 전체 목록을 반환하세요."
    )

    try:
        result = call_structured(
            api_key=api_key,
            model=model,
            schema=ChatRevisionOutput,
            system_prompt=REVISE_SYSTEM_PROMPT,
            user_msg=user_msg,
            max_retries=3,
            temperature=0.3,
        )

        if on_status:
            on_status("chat_agent", "done")

        # 히스토리 업데이트
        if history is not None:
            history.add_user(user_request)
            history.add_assistant(result.reply or "수정 완료했습니다.")

        # RTM 재구성
        revised_rtm = [
            {
                "REQ_ID": req.REQ_ID,
                "category": req.category,
                "description": req.description,
                "priority": req.priority,
                "rationale": req.rationale,
                "depends_on": req.depends_on,
                "test_criteria": req.test_criteria,
            }
            for req in result.requirements
        ]

        # 시맨틱 그래프 재구성
        existing_node_ids = {n.get("id") for n in sg.get("nodes", [])}
        new_nodes = list(sg.get("nodes", []))
        for req in revised_rtm:
            if req["REQ_ID"] not in existing_node_ids:
                new_nodes.append({
                    "id": req["REQ_ID"],
                    "label": req["description"][:50],
                    "category": req["category"],
                    "tags": [],
                })

        revised_ids = {r["REQ_ID"] for r in revised_rtm}
        new_nodes = [n for n in new_nodes if n.get("id") in revised_ids]

        new_edges = [
            {"source": dep, "target": req["REQ_ID"], "relation": "depends_on"}
            for req in revised_rtm
            for dep in req.get("depends_on", [])
            if dep in revised_ids
        ]

        revised_sg = {"nodes": new_nodes, "edges": new_edges}

        revised_ctx = {
            "summary": result.summary or ctx_serialized.get("summary", ""),
            "key_decisions": result.key_decisions or ctx_serialized.get("key_decisions", []),
            "open_questions": result.open_questions or ctx_serialized.get("open_questions", []),
            "tech_stack_suggestions": result.tech_stack_suggestions or ctx_serialized.get("tech_stack_suggestions", []),
            "risk_factors": result.risk_factors or ctx_serialized.get("risk_factors", []),
            "next_steps": result.next_steps or ctx_serialized.get("next_steps", []),
        }

        new_result = dict(previous_result)
        new_result["requirements_rtm"] = revised_rtm
        new_result["rtm_matrix"] = revised_rtm
        new_result["semantic_graph"] = revised_sg
        new_result["context_spec"] = revised_ctx
        new_result["thinking_log"] = previous_result.get("thinking_log", []) + [
            {"node": "chat_agent", "thinking": result.thinking}
        ]
        new_result["agent_reply"] = result.reply or "수정이 완료되었습니다."

        return new_result

    except Exception as e:
        if on_status:
            on_status("chat_agent", "error")
        raise RuntimeError(f"채팅 에이전트 수정 실패: {e}")


# ─────────────────────────────────────────────────────────────
# IDEA 모드 실행
# ─────────────────────────────────────────────────────────────

def run_idea_chat(
    api_key: str,
    model: str,
    user_message: str,
    history: ChatHistory,
    on_status=None,
) -> dict:
    """
    IDEA 모드: 아이디어 발굴 대화.

    Returns:
        {
            "reply": str,          # 사용자에게 보여줄 응답
            "is_ready": bool,      # 분석 시작 가능 여부
            "idea_summary": str,   # 분석용 아이디어 요약
            "suggested_mode": str, # create | update | reverse
        }
    """
    from pipeline.utils import call_structured

    if on_status:
        on_status("idea_chat", "running")

    # 대화 히스토리 컨텍스트
    history_ctx = ""
    if len(history) > 0:
        recent = history.get_recent(max_turns=5)
        turns = []
        for msg in recent:
            role = "사용자" if msg["role"] == "user" else "에이전트"
            turns.append(f"[{role}] {msg['content']}")
        history_ctx = "=== 이전 대화 ===\n" + "\n".join(turns) + "\n\n"

    user_msg = (
        f"{history_ctx}"
        f"=== 사용자 메시지 ===\n{user_message}\n\n"
        f"위 대화를 바탕으로 아이디어를 발전시켜 주세요."
    )

    try:
        result = call_structured(
            api_key=api_key,
            model=model,
            schema=IdeaChatOutput,
            system_prompt=IDEA_SYSTEM_PROMPT,
            user_msg=user_msg,
            max_retries=2,
            temperature=0.7,
        )

        if on_status:
            on_status("idea_chat", "done")

        # 히스토리 업데이트
        history.add_user(user_message)
        history.add_assistant(result.reply)

        return {
            "reply": result.reply,
            "is_ready": result.is_ready,
            "idea_summary": result.idea_summary,
            "suggested_mode": result.suggested_mode or "create",
        }

    except Exception as e:
        if on_status:
            on_status("idea_chat", "error")
        # 에러 시 기본 응답
        history.add_user(user_message)
        history.add_assistant("죄송합니다, 잠시 오류가 발생했습니다. 다시 말씀해 주세요.")
        return {
            "reply": "죄송합니다, 잠시 오류가 발생했습니다. 다시 말씀해 주세요.",
            "is_ready": False,
            "idea_summary": "",
            "suggested_mode": "create",
        }
