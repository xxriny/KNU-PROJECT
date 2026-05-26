"""
Pre-flight Idea Extractor
==========================
무거운 PM/SA 파이프라인을 가동하기 직전에, 사용자/AI 사이를 오간 날것의 대화 내역과
미반영 메모를 LLM 한 번에 정제해서 '최종 확정 요구사항' 마크다운 리스트만 추출한다.

목적
- 의사결정 번복(노이즈) 제거: "X 넣어줘 ➔ 아니 빼줘 ➔ Y로 바꿔줘"의 최종 상태만 남김
- 토큰 비용 절감 + 다운스트림 PM/SA가 명확한 신호만 받게 함
- 사용자가 빌드 직전 모달에서 검토/편집할 수 있는 깨끗한 텍스트를 제공
"""

from __future__ import annotations

import json
from typing import List, Optional

from pydantic import BaseModel, Field

from pipeline.core.utils import get_llm, active_jwt_token
from observability.logger import get_logger
from version import DEFAULT_MODEL


# ── 구조화 출력 스키마 ────────────────────────────────────

class FinalIdeaOutput(BaseModel):
    summary_markdown: str = Field(
        description=(
            "최종적으로 개발에 반영해야 할 요구사항만 정리한 마크다운. "
            "글머리 기호(- ) 또는 번호 매기기(1. )로 시작하는 항목들로 구성. "
            "각 항목은 한 줄로 압축하되, 필요하면 들여쓰기 보조 설명 허용. "
            "사용자가 취소/번복한 항목은 절대 포함하지 말 것."
        ),
    )
    dropped_points: List[str] = Field(
        default_factory=list,
        description=(
            "대화 중 한 번 거론됐다가 사용자가 명시적으로 취소·번복한 항목들. "
            "각 항목은 한 줄. UI에서 '제외된 항목' 알림용. 없으면 빈 배열."
        ),
    )


SYSTEM_PROMPT = """당신은 시니어 PM이자 요구사항 큐레이터다.

입력으로 받는 것은 다음 둘이다:
1. **대화 내역**: 사용자(USER)와 AI 어시스턴트(ASSISTANT)가 주고받은 의사결정 과정. 도중에 사용자가
   "역시 빼자", "방금 말한 거 취소", "그건 됐고 대신 …" 같이 **이전 발언을 번복**하는 경우가 흔하다.
2. **미반영 메모**: 사용자가 명시적으로 "기록해둬"라고 요청해 저장한 항목들. 이미 사용자 의지로
   확정된 신호이므로 기본적으로 결과에 포함한다 (단, 대화에서 명시적으로 취소된 경우 제외).

당신의 임무:
- 대화·메모의 **최종 합의 상태**만 남긴 깔끔한 마크다운 요구사항 목록을 생성한다.
- 번복·취소된 항목은 결과에서 완전히 제거하고, `dropped_points`에만 별도로 기록한다.
- 사용자가 던진 질문, AI의 잡담, 일반 대화 톤의 문장은 추출 대상이 아니다. **요구사항(기능/제약/
  목표) 한 줄로 환원 가능한 것만** 남긴다.
- 중복은 합친다. 비슷한 항목이 여러 번 등장하면 가장 마지막 버전의 표현을 채택한다.
- 추측하지 않는다. 대화에 없는 기능을 임의로 추가하지 않는다.

출력 형식:
- `summary_markdown`: `- ` 또는 `1. ` 로 시작하는 글머리 항목 목록. 섹션 헤더(`## …`)는 필요하면
  허용하지만, 항목 자체는 반드시 글머리 기호로 시작한다. 빈 줄로 항목 그룹을 분리해도 좋다.
- `dropped_points`: 사용자가 명시적으로 취소/번복한 항목들의 짧은 한 줄 요약 배열. 없으면 `[]`.

예시:
대화에 "결제는 토스로 하자 → 아니 카카오페이로 바꾸자 → 카카오랑 네이버 둘 다 지원해줘"가 있으면:
- summary_markdown 항목: "- 결제 수단: 카카오페이 + 네이버페이 동시 지원"
- dropped_points: ["토스페이먼츠 단독 연동안"]
"""


def _format_chat(chat_history: list) -> str:
    """role/content 형식의 대화 내역을 LLM이 읽기 쉬운 텍스트로 직렬화."""
    lines: list[str] = []
    for msg in chat_history or []:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            lines.append(f"[USER]\n{content}")
        elif role == "assistant":
            lines.append(f"[ASSISTANT]\n{content}")
        # system_marker 등 그 외 role은 의도적으로 제외 (sync/rollback 마커는 노이즈)
    return "\n\n".join(lines)


def _format_memos(memos: list) -> str:
    """활성 메모 목록을 LLM이 읽기 쉬운 텍스트로 직렬화."""
    if not memos:
        return ""
    lines: list[str] = []
    for i, m in enumerate(memos, 1):
        if not isinstance(m, dict):
            continue
        text = (m.get("text") or "").strip()
        if not text:
            continue
        section = (m.get("section") or "메모").strip()
        detail = (m.get("detail") or "").strip()
        if detail:
            lines.append(f"{i}. [{section}] {text}\n   {detail}")
        else:
            lines.append(f"{i}. [{section}] {text}")
    return "\n".join(lines)


def extract_final_idea(
    chat_history: list,
    memos: Optional[list] = None,
    api_key: str = "",
    model: str = DEFAULT_MODEL,
    auth_token: str = "",
) -> dict:
    """
    대화·메모를 LLM 한 번에 정제해서 최종 확정 요구사항 마크다운을 반환한다.

    Returns:
        {
            "status": "ok" | "error",
            "summary_markdown": str,
            "dropped_points": list[str],
            "error"?: str,
        }
    """
    logger = get_logger()

    # threadpool에서 실행되므로 ContextVar를 직접 세팅
    if auth_token:
        active_jwt_token.set(auth_token)

    logger.info(f"[extract_final_idea] auth_token={'SET' if auth_token else 'EMPTY'} model={model}")

    chat_text = _format_chat(chat_history)
    memo_text = _format_memos(memos or [])

    logger.info(f"[extract_final_idea] chat_len={len(chat_text)} memo_len={len(memo_text)}")

    if not chat_text and not memo_text:
        logger.info("[extract_final_idea] no content → early return")
        return {
            "status": "ok",
            "summary_markdown": "",
            "dropped_points": [],
        }

    user_blocks: list[str] = []
    if chat_text:
        user_blocks.append("## 대화 내역\n" + chat_text)
    if memo_text:
        user_blocks.append("## 미반영 메모\n" + memo_text)
    user_blocks.append(
        "위 입력을 바탕으로 **최종 확정된 요구사항만** `summary_markdown`에 담고, "
        "도중에 취소된 항목은 `dropped_points`에만 짧게 정리하라."
    )
    user_msg = "\n\n".join(user_blocks)

    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        from pipeline.core.utils import get_effective_key

        # 키 fetch 단계 로깅
        try:
            resolved_key = get_effective_key(api_key)
            logger.info(f"[extract_final_idea] key resolved OK (len={len(resolved_key)})")
        except ValueError as ve:
            logger.error(f"[extract_final_idea] key resolve FAILED: {ve}")
            raise

        llm = get_llm(api_key=api_key, model=model)
        logger.info(f"[extract_final_idea] LLM instance acquired, invoking structured output...")
        structured_llm = llm.with_structured_output(FinalIdeaOutput)
        out = structured_llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ])

        if isinstance(out, dict):
            out = FinalIdeaOutput.model_validate(out)

        summary = (out.summary_markdown or "").strip()
        dropped = [s.strip() for s in (out.dropped_points or []) if isinstance(s, str) and s.strip()]

        logger.info(
            f"[extract_final_idea] LLM OK summary_len={len(summary)} dropped={len(dropped)}"
        )

        return {
            "status": "ok",
            "summary_markdown": summary,
            "dropped_points": dropped,
        }

    except Exception as e:
        logger.exception("extract_final_idea failed")
        return {
            "status": "error",
            "summary_markdown": "",
            "dropped_points": [],
            "error": str(e),
        }
