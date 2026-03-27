"""
PM Agent Pipeline — 유틸리티 v6.3 (FastAPI 구조 적용)

변경 사항:
- api_key 빈 문자열 시 환경변수 GEMINI_API_KEY 자동 폴백
- 모델 기본값 gemini-2.5-flash 통일
- _get_effective_key() 헬퍼 추가
"""

import json, re, os, threading
from collections import OrderedDict
from typing import Any, Type, TypeVar
from pydantic import BaseModel, ValidationError
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

T = TypeVar("T", bound=BaseModel)
_CACHE_LIMIT = 32


def _make_llm_cache_key(api_key: str, model: str, temperature: float) -> str:
    return f"{api_key}:{model}:{temperature}"


def _remember_cache_entry(cache: OrderedDict[str, Any], key: str, value: Any):
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > _CACHE_LIMIT:
        cache.popitem(last=False)

# ── API 키 해석 ────────────────────────────────
def _get_effective_key(api_key: str) -> str:
    """
    전달받은 api_key가 비어있거나 프론트엔드 플레이스홀더(\'[.env]\') 일 경우
    환경변수 GEMINI_API_KEY를 사용.
    """
    key = (api_key or "").strip()
    # 프론트엔드가 \'[.env]\' 플레이스홀더를 보낸 경우 환경변수로 폴백
    if key in ("", "[.env]", "[env]"):
        key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise ValueError(
            "Gemini API Key가 설정되지 않았습니다. "
            "백엔드 .env 파일에 GEMINI_API_KEY=<키> 를 추가하거나 "
            "프론트엔드 설정에서 API 키를 입력해 주세요."
        )
    # 비ASCII 문자 포함 여부 검증 (httpx 헤더 인코딩 오류 방지)
    if not key.isascii():
        raise ValueError(
            "API 키에 한글 등 비ASCII 문자가 포함되어 있습니다. "
            "Gemini API 키는 영문자/숫자/하이픈만 포함해야 합니다. "
            "Google AI Studio에서 정확한 키를 복사해 주세요."
        )
    return key


# ── LangChain LLM 싱글턴 캐싱 ─────────────────
_llm_cache: OrderedDict[str, ChatGoogleGenerativeAI] = OrderedDict()
_raw_cache: OrderedDict[str, Any] = OrderedDict()
_llm_cache_lock = threading.Lock()
_raw_cache_lock = threading.Lock()


def get_llm(api_key: str, model: str = "gemini-2.5-flash", temperature: float = 0.3) -> ChatGoogleGenerativeAI:
    """ChatGoogleGenerativeAI 싱글턴 (api_key + model 조합으로 캐싱)"""
    try:
        effective_key = _get_effective_key(api_key)
        cache_key = _make_llm_cache_key(effective_key, model, temperature)

        with _llm_cache_lock:
            cached_llm = _llm_cache.get(cache_key)
            if cached_llm is not None:
                _llm_cache.move_to_end(cache_key)
                return cached_llm

        llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=effective_key,
            temperature=temperature,
        )

        with _llm_cache_lock:
            cached_llm = _llm_cache.get(cache_key)
            if cached_llm is not None:
                _llm_cache.move_to_end(cache_key)
                return cached_llm
            _remember_cache_entry(_llm_cache, cache_key, llm)
        return llm
    except ValueError as ve:
        raise ve
    except Exception as e:
        raise RuntimeError(f"LLM 초기화 오류: {str(e)}")


def call_structured(
    api_key: str,
    model: str,
    schema: Type[T],
    system_prompt: str,
    user_msg: str,
    max_retries: int = 3,
    temperature: float = 0.3,
) -> T:
    """
    Pydantic 스키마 강제 구조화 출력 + Self-Correction 재시도 루프.

    1차: with_structured_output(schema)로 LLM API에 JSON 스키마 주입
    실패 시: 에러 메시지를 LLM에게 피드백하여 자가 수정 (최대 max_retries회)

    Returns: Pydantic 모델 인스턴스 (파싱 보장)
    """
    llm = get_llm(api_key, model, temperature)
    structured_llm = llm.with_structured_output(schema)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_msg),
    ]

    last_error = None

    for attempt in range(max_retries):
        result = None
        try:
            result = structured_llm.invoke(messages)
            return result

        except (ValidationError, Exception) as e:
            last_error = e
            error_msg = str(e)

            bad_output = str(result) if result is not None else "Unknown output format or invocation error"
            messages.append(AIMessage(content=bad_output))

            correction_msg = (
                f"Your previous response caused a validation error:\n"
                f"```\n{error_msg}\n```\n\n"
                f"Please fix the output to strictly match the required JSON schema. "
                f"All required fields must be present and no extra fields are allowed.\n\n"
                f"Retry attempt {attempt + 2}/{max_retries}. "
                f"Return ONLY the corrected JSON output."
            )
            messages.append(HumanMessage(content=correction_msg))

    raise RuntimeError(
        f"Structured output failed after {max_retries} attempts. "
        f"Last error: {last_error}"
    )


def call_structured_with_usage(
    api_key: str,
    model: str,
    schema: Type[T],
    system_prompt: str,
    user_msg: str,
    max_retries: int = 3,
    temperature: float = 0.3,
) -> tuple[T, dict]:
    """
    구조화 출력 + usage 메타데이터 추출.

    Returns:
        (parsed_model, usage)
        usage 예시: {"input_tokens": 123, "output_tokens": 45, "total_tokens": 168}
    """
    llm = get_llm(api_key, model, temperature)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_msg),
    ]

    last_error = None

    # include_raw가 지원되면 usage_metadata를 추출하고,
    # 지원되지 않는 환경에서는 call_structured로 안전 폴백한다.
    try:
        structured_llm = llm.with_structured_output(schema, include_raw=True)
    except TypeError:
        parsed = call_structured(
            api_key=api_key,
            model=model,
            schema=schema,
            system_prompt=system_prompt,
            user_msg=user_msg,
            max_retries=max_retries,
            temperature=temperature,
        )
        return parsed, {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    for attempt in range(max_retries):
        result = None
        try:
            result = structured_llm.invoke(messages)

            if isinstance(result, dict):
                parsed = result.get("parsed")
                raw = result.get("raw")
                parsing_error = result.get("parsing_error")
                if parsing_error:
                    raise RuntimeError(f"Structured parsing error: {parsing_error}")
            else:
                # 일부 구현은 parsed 객체만 반환할 수 있다.
                parsed = result
                raw = None

            if parsed is None:
                raise RuntimeError("Structured output parsed result is None")

            usage_meta = getattr(raw, "usage_metadata", None) or {}
            usage = {
                "input_tokens": usage_meta.get("input_tokens", usage_meta.get("prompt_token_count", 0)) or 0,
                "output_tokens": usage_meta.get("output_tokens", usage_meta.get("candidates_token_count", 0)) or 0,
                "total_tokens": usage_meta.get("total_tokens", usage_meta.get("total_token_count", 0)) or 0,
            }
            return parsed, usage

        except (ValidationError, Exception) as e:
            last_error = e
            error_msg = str(e)

            bad_output = str(result) if result is not None else "Unknown output format or invocation error"
            messages.append(AIMessage(content=bad_output))

            correction_msg = (
                f"Your previous response caused a validation error:\n"
                f"```\n{error_msg}\n```\n\n"
                f"Please fix the output to strictly match the required JSON schema. "
                f"All required fields must be present and no extra fields are allowed.\n\n"
                f"Retry attempt {attempt + 2}/{max_retries}. Return ONLY the corrected JSON output."
            )
            messages.append(HumanMessage(content=correction_msg))

    raise RuntimeError(
        f"Structured output with usage failed after {max_retries} attempts. "
        f"Last error: {last_error}"
    )


def call_structured_with_thinking(
    api_key: str,
    model: str,
    schema: Type[T],
    system_prompt: str,
    user_msg: str,
    max_retries: int = 3,
    temperature: float = 0.3,
) -> tuple[T, str]:
    """구조화 출력 + thinking 필드 추출."""
    result = call_structured(
        api_key=api_key,
        model=model,
        schema=schema,
        system_prompt=system_prompt,
        user_msg=user_msg,
        max_retries=max_retries,
        temperature=temperature,
    )
    thinking = getattr(result, "thinking", "")
    return result, thinking


# ── 하위 호환: 기존 call_gemini (비구조화 호출) ────────
from google import genai
from google.genai import types

def _get_raw_client(api_key: str):
    try:
        effective_key = _get_effective_key(api_key)
        with _raw_cache_lock:
            cached_client = _raw_cache.get(effective_key)
            if cached_client is not None:
                _raw_cache.move_to_end(effective_key)
                return cached_client

        client = genai.Client(api_key=effective_key)

        with _raw_cache_lock:
            cached_client = _raw_cache.get(effective_key)
            if cached_client is not None:
                _raw_cache.move_to_end(effective_key)
                return cached_client
            _remember_cache_entry(_raw_cache, effective_key, client)
        return client
    except Exception as e:
        raise RuntimeError(f"Gemini 클라이언트 초기화 오류: {str(e)}")


def call_gemini(api_key: str, model: str = "gemini-2.5-flash", system: str = "",
                user_msg: str = "", temperature: float = 0.3, max_tokens: int = 8192) -> str:
    """비구조화 Gemini 호출"""
    try:
        client = _get_raw_client(api_key)
        resp = client.models.generate_content(
            model=model,
            contents=user_msg,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
        return resp.text or ""
    except Exception as e:
        # API 키 유효성 오류(400 INVALID_ARGUMENT) 등 구체적 에러 메시지 추출
        err_msg = str(e)
        if "API_KEY_INVALID" in err_msg or "400" in err_msg:
            raise RuntimeError(f"Gemini API 키가 유효하지 않습니다. (400 INVALID_ARGUMENT) 올바른 키를 입력해 주세요.")
        raise RuntimeError(f"Gemini 호출 중 오류 발생: {err_msg}")


# ── JSON 유틸 ────────────────────────────────────

def extract_json_block(text: str) -> str:
    m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        return m.group(1)
    b = re.search(r"(\{.*)", text, re.DOTALL)
    return b.group(1) if b else ""


def parse_json_safe(text: str):
    js = extract_json_block(text)
    if not js:
        return None
    try:
        return json.loads(js)
    except Exception:
        return None


def extract_thinking(text: str) -> str:
    m = re.search(r"<thinking>(.*?)</thinking>", text, re.DOTALL)
    return m.group(1).strip() if m else ""
