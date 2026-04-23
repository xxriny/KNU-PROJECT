"""
PM Agent Pipeline — 유틸리티 v6.3 (FastAPI 구조 적용)

변경 사항:
- api_key 빈 문자열 시 환경변수 GEMINI_API_KEY 자동 폴백
- 모델 기본값 gemini-2.5-flash 통일
- _get_effective_key() 헬퍼 추가
"""

import json, re, os, threading
from contextvars import ContextVar
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Generic, Type, TypeVar
from pydantic import BaseModel, ValidationError
from observability.logger import get_logger
from pipeline.core.models.gemini_model import get_gemini_client, get_raw_genai_client
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from pipeline.core.cost_manager import calculate_cost
from pipeline.core.compressor import get_compressor
from version import DEFAULT_MODEL, DEFAULT_TEMPERATURE, MAX_LLM_RETRIES

T = TypeVar("T", bound=BaseModel)
_CACHE_LIMIT = 32
logger = get_logger()

# ── 비용 및 토큰 추적용 전역 컨텍스트 (Phase 0) ──────
# 각 노드 실행 중 발생하는 모든 LLM 호출의 사용량을 임시 저장합니다.
active_usage_log: ContextVar[list] = ContextVar("active_usage_log", default=[])
active_session_id: ContextVar[str] = ContextVar("active_session_id", default="")


@dataclass
class LLMResult(Generic[T]):
    parsed: T
    usage: dict
    cost: float
    thinking: str
    retry_count: int = 0


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


def get_llm(api_key: str, model: str = DEFAULT_MODEL, temperature: float = DEFAULT_TEMPERATURE) -> ChatGoogleGenerativeAI:
    """ChatGoogleGenerativeAI 위임 (core/models/gemini_model 사용)"""
    return get_gemini_client(api_key, model, temperature)


def _retry_loop(structured_llm, messages: list, max_retries: int, label: str):
    """공통 Self-Correction 재시도 루프. 성공 시 raw invoke 결과 반환."""
    messages = list(messages)
    last_error = None
    for attempt in range(max_retries):
        result = None
        try:
            result = structured_llm.invoke(messages)
            return result, attempt # 결과와 시도 횟수(0-based) 반환
        except ValidationError as e:
            last_error = e
            error_msg = str(e)
        except Exception as e:
            last_error = e
            error_msg = str(e)

        bad_output = str(result) if result is not None else "Unknown output format or invocation error"
        messages.append(AIMessage(content=bad_output))
        messages.append(HumanMessage(content=(
            f"Your previous response caused a validation error:\n"
            f"```\n{error_msg}\n```\n\n"
            f"Please fix the output to strictly match the required JSON schema. "
            f"All required fields must be present and no extra fields are allowed.\n\n"
            f"Retry attempt {attempt + 2}/{max_retries}. "
            f"Return ONLY the corrected JSON output."
        )))

    raise RuntimeError(
        f"{label} failed after {max_retries} attempts. Last error: {last_error}"
    )


_ZERO_USAGE: dict = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


def call_structured(
    api_key: str,
    model: str,
    schema: Type[T],
    system_prompt: str,
    user_msg: str,
    max_retries: int = MAX_LLM_RETRIES,
    temperature: float = DEFAULT_TEMPERATURE,
    compress_prompt: bool = False,
    compression_rate: float = 0.5,
) -> LLMResult[T]:
    """Unified structured output: parsed result, usage metadata, and thinking."""
    # Phase 3: Prompt Compression
    if compress_prompt:
        # LLMLingua-2 기반 압축 실행 (가변 압축률 지원)
        user_msg = get_compressor().compress_with_preservation(user_msg, target_token_rate=compression_rate)
        logger.info(f"[PromptCompressor] Compressed with rate {compression_rate}")

    llm = get_llm(api_key, model, temperature)
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_msg)]

    try:
        structured_llm = llm.with_structured_output(schema, include_raw=True)
    except TypeError:
        structured_llm = llm.with_structured_output(schema)
        parsed, retries = _retry_loop(structured_llm, messages, max_retries, "Structured output")
        return LLMResult(
            parsed=parsed,
            usage={**_ZERO_USAGE},
            thinking=getattr(parsed, "thinking", ""),
            retry_count=retries,
        )

    raw_result, retries = _retry_loop(structured_llm, messages, max_retries, "Structured output")

    if isinstance(raw_result, dict):
        parsed = raw_result.get("parsed")
        raw = raw_result.get("raw")
        parsing_error = raw_result.get("parsing_error")
        if parsing_error:
            raise RuntimeError(f"Structured parsing error: {parsing_error}")
    else:
        parsed = raw_result
        raw = None

    if parsed is None:
        raise RuntimeError("Structured output parsed result is None")

    usage_meta = getattr(raw, "usage_metadata", None) or {}
    usage = {
        "input_tokens": usage_meta.get("input_tokens", usage_meta.get("prompt_token_count", 0)) or 0,
        "output_tokens": usage_meta.get("output_tokens", usage_meta.get("candidates_token_count", 0)) or 0,
        "total_tokens": usage_meta.get("total_tokens", usage_meta.get("total_token_count", 0)) or 0,
    }
    
    cost = calculate_cost(model, usage["input_tokens"], usage["output_tokens"])

    # 중앙 집중형 추적을 위해 컨텍스트에 기록 (Phase 0)
    current_log = active_usage_log.get().copy()
    
    # 캐싱 통계 계산 (Phase 1)
    from pipeline.core.cache_manager import cache_manager
    session_id = active_session_id.get()
    cache_stats = {"cache_hit": False, "savings_usd": 0.0}
    
    if session_id:
        # 시스템 프롬프트를 정적 컨텍스트로 간주하여 캐시 (첫 호출 시)
        if session_id not in cache_manager.session_pool:
            cache_manager.cache_static_context(session_id, system_prompt)
        
        cache_stats = cache_manager.get_cache_stats(session_id, model, usage)

    log_entry = {
        "model": model,
        "input": usage["input_tokens"],
        "output": usage["output_tokens"],
        "cost": cost,
        "cache_hit": cache_stats["cache_hit"],
        "savings": cache_stats["savings_usd"]
    }
    current_log.append(log_entry)
    active_usage_log.set(current_log)

    return LLMResult(
        parsed=parsed,
        usage=usage,
        cost=cost,
        thinking=getattr(parsed, "thinking", ""),
        retry_count=retries,
    )


def call_structured_with_usage(
    api_key: str,
    model: str,
    schema: Type[T],
    system_prompt: str,
    user_msg: str,
    max_retries: int = MAX_LLM_RETRIES,
    temperature: float = DEFAULT_TEMPERATURE,
) -> tuple[T, dict]:
    """Backward-compat wrapper: returns (parsed, usage)."""
    result = call_structured(
        api_key=api_key, model=model, schema=schema,
        system_prompt=system_prompt, user_msg=user_msg,
        max_retries=max_retries, temperature=temperature,
    )
    return result.parsed, result.usage


def call_structured_with_thinking(
    api_key: str,
    model: str,
    schema: Type[T],
    system_prompt: str,
    user_msg: str,
    max_retries: int = MAX_LLM_RETRIES,
    temperature: float = DEFAULT_TEMPERATURE,
) -> tuple[T, str]:
    """Backward-compat wrapper: returns (parsed, thinking)."""
    result = call_structured(
        api_key=api_key, model=model, schema=schema,
        system_prompt=system_prompt, user_msg=user_msg,
        max_retries=max_retries, temperature=temperature,
    )
    return result.parsed, result.thinking


# ── 하위 호환: 기존 call_gemini (비구조화 호출) ────────
from google import genai
from google.genai import types

def _get_raw_client(api_key: str):
    """원시 클라이언트 위임 (core/models/gemini_model 사용)"""
    return get_raw_genai_client(api_key)


def call_gemini(api_key: str, model: str = DEFAULT_MODEL, system: str = "",
                user_msg: str = "", temperature: float = DEFAULT_TEMPERATURE, max_tokens: int = 8192) -> str:
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


# ── 직렬화 유틸 ──────────────────────────────────

def to_serializable(obj: Any) -> Any:
    """Pydantic 모델, dict, list를 재귀적으로 JSON 직렬화 가능하게 변환."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_serializable(item) for item in obj]
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    return str(obj)
