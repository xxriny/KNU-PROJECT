"""
PM Agent Pipeline — 아이디어 채팅 노드 v8.1
사용자와 대화하며 아이디어를 발전시키는 LangGraph 노드.
사용자가 "추가/메모/노트로 남겨줘" 등을 명시적으로 요청하면 notes_to_add에 항목을 채워
프론트가 메모(노트)에 자동 저장하도록 한다.

v8.1 변경:
- llm.with_structured_output(IdeaChatOutput)로 구조화 출력 강제. 자유 형식 JSON 파싱 실패로
  notes_to_add가 조용히 누락되던 회귀를 차단.
- 시스템 프롬프트에 reply ↔ notes_to_add 일관성 절대 규칙 추가.
- notes_to_add 길이/샘플을 INFO 로그로 남겨 회귀 진단 가능.
"""

import json
from typing import List

from pydantic import BaseModel, Field

from pipeline.core.state import PipelineState, make_sget
from pipeline.core.utils import get_llm, parse_json_safe
from observability.logger import get_logger
from version import DEFAULT_MODEL

# RAG Manager (Phase 2)
from pipeline.core.rag_manager import rag_manager


# ── 구조화 출력 스키마 ────────────────────────────────────

class NoteToAddItem(BaseModel):
    text: str = Field(
        description="메모 제목/요약 — 한 줄, 50자 이내, 카드 기본 노출용"
    )
    section: str = Field(default="Idea Chat", description="메모 섹션 라벨")
    detail: str = Field(
        default="",
        description=(
            "상세 수정 사항 — 어떤 부분을 어떻게 바꿔야 하는지 구체적·자유 형식으로 작성. "
            "여러 문장 가능, UPDATE 분석 시 LLM이 이 내용을 직접 참고. "
            "사용자 발화가 짧은 한 줄이면 비워둘 수 있음."
        ),
    )


class IdeaChatOutput(BaseModel):
    reply: str = Field(description="사용자에게 보낼 한국어 응답 (마크다운 가능)")
    idea_ready: bool = Field(default=False, description="분석 시작 가능 여부")
    idea_summary: str = Field(default="", description="idea_ready=true일 때 분석에 전달할 아이디어 요약")
    suggested_mode: str = Field(default="create", description="create | update | reverse")
    notes_to_add: List[NoteToAddItem] = Field(
        default_factory=list,
        description="사용자가 명시적으로 메모/노트/기능 추가를 요청했을 때만 채울 메모 목록"
    )


def _extract_text(response) -> str:
    """LangChain AIMessage.content를 문자열로 정규화.
    신모델(gemini-3.1+)은 content를 [{"type":"text","text":"..."}, ...] 리스트로 반환할 수 있음."""
    content = response.content if hasattr(response, "content") else response
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict):
                text = p.get("text") or p.get("content") or ""
                if isinstance(text, str) and text:
                    parts.append(text)
        return "".join(parts)
    return str(content)


SYSTEM_PROMPT = """당신은 PM(프로젝트 매니저) AI 어시스턴트입니다.
사용자가 아이디어를 구체화하거나, 이미 만들어진 분석 결과를 이해하고 다음 액션을 결정하도록 도와주세요.

## 역할
1. 사용자의 막연한 아이디어를 구체적인 프로젝트 기획으로 발전시키세요.
2. 사용자가 프로젝트의 맥락, 기술 스택, 혹은 지적사항(메모)에 대해 물으면 RAG 검색 결과를 바탕으로 정확하게 답변하세요.
3. 적절한 질문을 통해 요구사항을 명확히 하세요.
4. 기술 스택, 대상 사용자, 핵심 기능 등을 파악하세요.
5. 아이디어가 충분히 구체화되면 분석을 시작할 수 있다고 안내하세요.
6. 이전 분석 결과가 주어지면, 그 결과를 설명하거나 개선 방향을 제안하세요. (더 이상 직접적인 '적용' 모드는 없으므로, 대화를 통해 설계를 다듬는 데 집중하세요.)

## 응답 필드 (구조화 출력)
다음 필드를 가진 JSON 객체로 응답합니다 (스키마는 시스템에서 강제됩니다).
- reply: 사용자에게 보낼 응답 (한국어, 마크다운 가능)
- idea_ready: 아이디어가 충분히 구체화되어 분석을 시작할 수 있으면 true
- idea_summary: idea_ready=true일 때 분석에 전달할 구체적 요약, 그 외엔 빈 문자열
- suggested_mode: "create" (신규) | "update" (기능확장) | "reverse" (역공학)
- notes_to_add: 메모(노트)로 저장할 항목 배열 (아래 규칙 참조)

진행 신호:
- 사용자가 "분석 시작", "개발 시작", "이걸로 해줘" 등을 말하면 idea_ready=true.
- 이전 분석 결과가 있는 상태라면 idea_ready는 기본 false. 설명/비교/추천 중심으로 응답.

## notes_to_add — 메모(노트) 자동 작성 규칙 (★중요)

### 채울 조건 (트리거)
사용자의 직전 발화에 다음 같은 **명시적 추가/기록 요청**이 있을 때만 항목을 만듭니다:
- "이 기능 추가해줘", "X 기능을 메모해줘", "노트에 적어줘", "기록해둬", "남겨둬", "기억해둬"
- "메모로 정리해줘", "메모에 요약해서 저장해줘", "이거 메모/노트에 정리"
- "최종적으로 ~를 적용/추가하자", "이 항목 추가", "결정사항으로 남겨"
- 사용자가 분명히 결정·확정·요청·기록 의도를 표현한 모든 변형

### 비울 조건
다음 경우에는 반드시 빈 배열(notes_to_add: [])로 두세요:
- 단순 질문, 탐색, 의견 교환, 일반 대화
- AI(당신)가 단순히 제안·아이디어를 던지는 경우
- 사용자가 "어떻게 생각해?", "괜찮을까?" 등 의견을 물어볼 때

사용자가 명시적으로 추가/메모/노트를 요청하지 않았는데 임의로 채우지 마세요.

### 일관성 절대 규칙 (★깨지면 안 됨)
**reply 본문에서 "메모로 추가했어요", "노트에 적었어요", "메모해뒀어요" 등 추가 사실을 사용자에게 알렸다면, 같은 응답의 notes_to_add 배열에 반드시 해당 항목을 1개 이상 포함해야 합니다.**

반대로 notes_to_add가 빈 배열이면 reply에서도 메모를 추가했다고 말하지 마세요. 두 필드의 약속이 어긋나면 사용자에게 거짓 응답을 하는 것이며, 이는 시스템 신뢰를 깨뜨립니다.

### 항목 형식 (★title-detail 분리)
- **text**: 메모의 **제목/요약**. 카드 한 줄에 노출되므로 **짧고 명확한 한 문장(50자 이내 권장)**. 예: "결제 모듈에 PG사 연동 추가", "회원가입에 이메일 인증 단계 추가".
- **section**: 기본값 "Idea Chat". 명백히 다른 영역이면 "RTM" / "기술 스택" / "API 설계" / "DB 설계" / "보안" 중에서.
- **detail**: **상세 수정 사항**. 사용자 발화에서 *어떤 부분을 어떻게* 바꿔야 하는지 구체적으로 풀어 쓴 본문. 여러 문장 가능. 예시:
  ```
  결제 모듈에 PG사(예: 토스페이먼츠) 연동을 추가한다.
  - 신용카드/계좌이체/간편결제 3종 채널 지원
  - 결제 완료 시점에 주문 상태를 'PAID'로 갱신하고 영수증 메일 발송
  - 결제 실패 시 사용자에게 사유 노출 + 자동 재시도 1회
  ```
  사용자가 짧게 "결제 추가해줘"라고만 말했으면 detail은 빈 문자열로 두고, 사용자가 상세히 설명했으면 그 내용을 정리해 detail에 담는다. **text와 detail에 같은 문장을 중복 작성하지 말 것** — text는 표제, detail은 본문.

### 다중 항목
사용자가 한 번에 여러 기능/항목을 요청하면 항목별로 분리해 배열에 담으세요.

## 코드 참조 규칙 (★사용자 프로젝트 파일에 대한 질문)
- 시스템 메시지 RAG 섹션에 **"### 관련 코드 청크 (사용자 프로젝트)"** 가 포함되어 있다면,
  사용자가 등록한 프로젝트의 실제 코드 파일/함수가 제공된 것입니다. 이 내용을 그대로 인용하거나
  요약해 정확한 답변을 작성하세요. 임의로 추측한 코드를 답변에 포함하지 마세요.
- 위 섹션이 **없는데** 사용자가 "이 파일이 뭐야", "X 함수가 어디 있어", "코드 구조 설명해줘" 같이
  코드 자체를 묻는 경우, 다음과 같이 안내하세요:
  > "프로젝트 코드를 보려면 폴더를 선택한 뒤 분석(CREATE/UPDATE/REVERSE)을 한 번 실행해 주세요.
  > 분석 라운드가 코드 청크를 RAG에 인덱싱하면 그 다음 채팅부터 파일별 정확한 설명이 가능합니다."
  - 이 경우 `notes_to_add`는 비워두세요 (사용자가 명시적으로 메모해달라 한 게 아니므로).

## 대화 스타일
- 친근하지만 전문적인 톤
- 핵심 질문 1-2개씩 던지기 (한 번에 너무 많이 묻지 않기)
- 사용자 아이디어의 장점을 인정하고 발전시키기
"""


def idea_chat_node(state: PipelineState) -> dict:
    """아이디어 채팅 노드 — 사용자와 대화하며 아이디어 구체화 + 메모 자동 추가."""
    logger = get_logger()
    try:
        sget = make_sget(state)
        api_key = sget("api_key", "")
        model = sget("model", DEFAULT_MODEL)
        user_request = sget("user_request", "")
        history = sget("chat_history", [])
        previous_result = sget("previous_result", {})

        if not user_request:
            return {"error": "메시지가 비어있습니다.", "current_step": "idea_chat"}

        # ── RAG Manager 통합 검색 (Phase 2) ──
        rag_context = []
        try:
            pm_sa_results = rag_manager.adaptive_search(user_request, context_type="pm", n_results=3)
            if pm_sa_results:
                rag_context.append("### 관련 산출물 지식 (RTM/Components/API/DB)")
                for res in pm_sa_results:
                    rag_context.append(f"- {res['content'][:1000]}")

            stack_results = rag_manager.adaptive_search(user_request, context_type="stack", n_results=2)
            if stack_results:
                rag_context.append("### 관련 기술 스택 정보")
                for s in stack_results:
                    rag_context.append(f"- {s['package_name']} ({s['version_req']}): {s['content'][:500]}")

            memo_results = rag_manager.adaptive_search(user_request, context_type="memo", n_results=3)
            if memo_results:
                rag_context.append("### 사용자 지적사항 및 메모")
                for res in memo_results:
                    rag_context.append(f"- {res['content']}")
        except Exception as rag_err:
            logger.warning(f"RAG search via RAGManager failed: {rag_err}")

        # ── 사용자 프로젝트 코드 청크 RAG (분석 1회 이후만 동작) ──
        # previous_result.rag_index_status.session_id는 직전 분석 라운드에서 사용된
        # source_dir 해시 기반 영속 ID. 코드 청크는 project_code_knowledge 컬렉션에 들어있음.
        # 분석을 한 번도 안 돌렸으면 session_id가 비어 있어 자연히 검색 스킵.
        code_session_id = ""
        has_code_index = False
        try:
            rag_status = (previous_result or {}).get("rag_index_status") or {}
            code_session_id = rag_status.get("session_id") or ""
            has_code_index = bool(rag_status.get("has_index"))
        except Exception:
            pass

        if code_session_id and has_code_index:
            try:
                from pipeline.domain.rag.nodes.project_db import query_project_code
                code_results = query_project_code(
                    user_request, session_id=code_session_id, n_results=5
                )
                if code_results:
                    rag_context.append("### 관련 코드 청크 (사용자 프로젝트)")
                    for r in code_results[:5]:
                        fp = r.get("file_path", "")
                        fn = r.get("func_name", "")
                        sim = r.get("similarity", 0) or 0
                        snippet = (r.get("content_text") or "")[:500]
                        rag_context.append(
                            f"- {fp}::{fn} (유사도 {sim:.2f})\n  {snippet}"
                        )
            except Exception as code_err:
                logger.warning(f"[idea_chat] 코드 RAG 검색 실패: {code_err}")

        rag_text = "\n".join(rag_context)

        # 메시지 구성
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

        messages = [SystemMessage(content=SYSTEM_PROMPT)]

        if rag_text:
            messages.append(SystemMessage(content=f"## 관련 지식 베이스 (RAG)\n{rag_text}"))

        if previous_result:
            result_context = {
                "metadata": previous_result.get("metadata", {}),
                "requirements_rtm": previous_result.get("requirements_rtm", []),
                "context_spec": previous_result.get("context_spec", {}),
            }
            messages.append(HumanMessage(content=(
                "## 기존 분석 결과 컨텍스트\n"
                f"{json.dumps(result_context, ensure_ascii=False, indent=2)}\n\n"
                "위 결과는 참고용입니다. 사용자가 명시적으로 적용을 요청하기 전까지는 결과를 직접 수정하지 말고, 설명과 제안 중심으로 응답하세요."
            )))

        # 대화 히스토리 추가
        for msg in history:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

        messages.append(HumanMessage(content=user_request))

        # ── 1차: 구조화 출력 강제 (Pydantic 스키마) ──
        llm = get_llm(api_key=api_key, model=model)
        reply = ""
        idea_ready = False
        idea_summary = ""
        suggested_mode = "create"
        notes_to_add: list = []

        try:
            structured_llm = llm.with_structured_output(IdeaChatOutput)
            out = structured_llm.invoke(messages)

            # langchain-google-genai는 보통 IdeaChatOutput 인스턴스를 돌려주지만,
            # 모델/버전에 따라 dict로 반환되는 경우도 있어 둘 다 처리.
            if isinstance(out, dict):
                out = IdeaChatOutput.model_validate(out)

            reply = (out.reply or "").strip()
            idea_ready = bool(out.idea_ready)
            idea_summary = (out.idea_summary or "").strip()
            suggested_mode = (out.suggested_mode or "create").strip()
            notes_to_add = _normalize_notes_to_add(
                [n.model_dump() for n in (out.notes_to_add or [])]
            )

        except Exception as struct_err:
            # 구조화 출력 실패 시 자유 형식 폴백
            logger.warning(f"[idea_chat] structured output failed, falling back to free-form: {struct_err}")
            response = llm.invoke(messages)
            raw = _extract_text(response)
            result = parse_json_safe(raw)

            if not result:
                reply = raw.strip()
                idea_ready = False
                idea_summary = ""
                suggested_mode = "create"
                notes_to_add = []
            else:
                reply = (result.get("reply") or raw.strip()).strip()
                idea_ready = bool(result.get("idea_ready", False))
                idea_summary = (result.get("idea_summary") or "").strip()
                suggested_mode = (result.get("suggested_mode") or "create").strip()
                notes_to_add = _normalize_notes_to_add(result.get("notes_to_add", []))

        # ── 진단 로그: notes_to_add 누수/누락을 즉시 감지하기 위함 ──
        sample = notes_to_add[0]["text"][:60] if notes_to_add else ""
        logger.info(
            f"[idea_chat] notes_to_add={len(notes_to_add)}건"
            f"{' / 첫 항목: ' + sample if sample else ''}"
        )

        # reply가 메모 추가를 시사하는데 notes_to_add가 비어있으면 경고.
        # LLM이 일관성 규칙을 어긴 상태이며, 사용자에게는 "추가했다"고 답하지만
        # 실제로 메모는 들어가지 않는 회귀의 원인이 된다.
        if not notes_to_add and reply:
            reply_lower = reply.replace(" ", "")
            memo_signals = ("메모로추가", "메모에추가", "메모해뒀", "메모해두었",
                            "노트로추가", "노트에추가", "노트에적", "메모에남기",
                            "메모로저장", "메모에저장")
            if any(sig in reply_lower for sig in memo_signals):
                logger.warning(
                    "[idea_chat] reply는 메모 추가를 언급했지만 notes_to_add가 비어있음 "
                    "— LLM이 일관성 규칙을 위반. 사용자에게는 메모가 추가되지 않은 것으로 보임."
                )

        # 히스토리 업데이트
        new_history = list(history)
        new_history.append({"role": "user", "content": user_request})
        new_history.append({"role": "assistant", "content": reply})

        # 채팅 응답은 PROGRESS의 thinking_log에 노출하지 않는다 (대화 채널 분리).
        return {
            "agent_reply": reply,
            "chat_history": new_history,
            "idea_ready": idea_ready,
            "idea_summary": idea_summary,
            "suggested_mode": suggested_mode,
            "notes_to_add": notes_to_add,
            "thinking_log": [],
            "current_step": "idea_chat",
        }

    except Exception as e:
        get_logger().exception("idea_chat_node failed")
        return {
            "error": str(e),
            "thinking_log": [],
            "current_step": "idea_chat",
        }


def _normalize_notes_to_add(raw_notes) -> list:
    """LLM이 반환한 notes_to_add를 안전한 형식으로 정규화한다.

    - 리스트가 아니면 빈 리스트로
    - 각 항목은 dict 또는 str 허용. 최소 'text'가 비어있지 않아야 채택
    - section 기본값 'Idea Chat'
    - text(제목)는 200자, detail(상세)은 4000자로 자름
    """
    if not isinstance(raw_notes, list):
        return []

    normalized = []
    for item in raw_notes:
        if isinstance(item, str):
            text = item.strip()
            section = "Idea Chat"
            detail = ""
        elif isinstance(item, dict):
            text = str(item.get("text") or "").strip()
            section = str(item.get("section") or "Idea Chat").strip() or "Idea Chat"
            detail = str(item.get("detail") or "").strip()
        else:
            continue

        if not text:
            continue
        normalized.append({
            "text": text[:200],
            "section": section[:60],
            "detail": detail[:4000],
        })

    return normalized
