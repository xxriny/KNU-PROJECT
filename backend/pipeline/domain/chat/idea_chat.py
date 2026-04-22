"""
PM Agent Pipeline — 아이디어 채팅 노드 v8.0
사용자와 대화하며 아이디어를 발전시키는 LangGraph 노드.
아이디어가 충분히 구체화되면 분석 파이프라인으로 전달할 요약을 생성한다.
"""

import json
from pipeline.core.state import PipelineState, make_sget
from pipeline.core.utils import get_llm, parse_json_safe
from observability.logger import get_logger
from version import DEFAULT_MODEL

# RAG Manager (Phase 2)
from pipeline.core.rag_manager import rag_manager


SYSTEM_PROMPT = """당신은 PM(프로젝트 매니저) AI 어시스턴트입니다.
사용자가 아이디어를 구체화하거나, 이미 만들어진 분석 결과를 이해하고 다음 액션을 결정하도록 도와주세요.

## 역할
1. 사용자의 막연한 아이디어를 구체적인 프로젝트 기획으로 발전시키세요.
2. 사용자가 프로젝트의 맥락, 기술 스택, 혹은 지적사항(메모)에 대해 물으면 RAG 검색 결과를 바탕으로 정확하게 답변하세요.
3. 적절한 질문을 통해 요구사항을 명확히 하세요.
4. 기술 스택, 대상 사용자, 핵심 기능 등을 파악하세요.
5. 아이디어가 충분히 구체화되면 분석을 시작할 수 있다고 안내하세요.
6. 이전 분석 결과가 주어지면, 그 결과를 설명하거나 개선 방향을 제안하세요. (더 이상 직접적인 '적용' 모드는 없으므로, 대화를 통해 설계를 다듬는 데 집중하세요.)

## 응답 형식
반드시 아래 JSON 형식으로 응답하세요:
```json
{
  "reply": "사용자에게 보낼 응답 (한국어, 마크다운 가능)",
  "idea_ready": false,
  "idea_summary": "",
  "suggested_mode": "create"
}
```

- idea_ready: 아이디어가 충분히 구체화되어 분석을 시작할 수 있으면 true
- idea_summary: idea_ready가 true일 때, 분석에 전달할 구체적인 아이디어 요약
- suggested_mode: "create" (신규), "update" (기능확장), "reverse" (역공학)
- 사용자가 "분석 시작", "개발 시작", "이걸로 해줘" 등을 말하면 idea_ready를 true로 설정
- 이전 결과가 있는 상태라면 idea_ready는 기본적으로 false를 유지하고, 설명/비교/추천 중심으로 응답하세요.

## 대화 스타일
- 친근하지만 전문적인 톤
- 핵심 질문 1-2개씩 던지기 (한 번에 너무 많이 묻지 않기)
- 사용자 아이디어의 장점을 인정하고 발전시키기
"""


def idea_chat_node(state: PipelineState) -> dict:
    """아이디어 채팅 노드 — 사용자와 대화하며 아이디어 구체화"""
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
            # 1. 산출물 지식 검색 (PM/SA)
            pm_sa_results = rag_manager.adaptive_search(user_request, context_type="pm", n_results=3)
            if pm_sa_results:
                rag_context.append("### 관련 산출물 지식 (RTM/Components/API/DB)")
                for res in pm_sa_results:
                    rag_context.append(f"- {res['content'][:1000]}")

            # 2. 기술 스택 지식 검색
            stack_results = rag_manager.adaptive_search(user_request, context_type="stack", n_results=2)
            if stack_results:
                rag_context.append("### 관련 기술 스택 정보")
                for s in stack_results:
                    rag_context.append(f"- {s['package_name']} ({s['version_req']}): {s['content'][:500]}")

            # 3. 사용자 메모/지적사항 검색
            memo_results = rag_manager.adaptive_search(user_request, context_type="memo", n_results=3)
            if memo_results:
                rag_context.append("### 사용자 지적사항 및 메모")
                for res in memo_results:
                    rag_context.append(f"- {res['content']}")
        except Exception as rag_err:
            get_logger().warning(f"RAG search via RAGManager failed: {rag_err}")

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
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))

        messages.append(HumanMessage(content=user_request))

        # LLM 호출
        llm = get_llm(api_key=api_key, model=model)
        response = llm.invoke(messages)
            
        raw = response.content if hasattr(response, "content") else str(response)

        result = parse_json_safe(raw)

        if not result:
            # JSON 파싱 실패 시 텍스트 응답으로 처리
            reply = raw.strip()
            idea_ready = False
            idea_summary = ""
            suggested_mode = "create"
        else:
            reply = result.get("reply", raw.strip())
            idea_ready = result.get("idea_ready", False)
            idea_summary = result.get("idea_summary", "")
            suggested_mode = result.get("suggested_mode", "create")

        # 히스토리 업데이트
        new_history = list(history)
        new_history.append({"role": "user", "content": user_request})
        new_history.append({"role": "assistant", "content": reply})

        return {
            "agent_reply": reply,
            "chat_history": new_history,
            "idea_ready": idea_ready,
            "idea_summary": idea_summary,
            "suggested_mode": suggested_mode,
            "thinking_log": [{"node": "idea_chat", "thinking": reply}],
            "current_step": "idea_chat",
        }

    except Exception as e:
        get_logger().exception("idea_chat_node failed")
        return {
            "error": str(e),
            "thinking_log": [{"node": "idea_chat", "thinking": f"오류: {e}"}],
            "current_step": "idea_chat",
        }
