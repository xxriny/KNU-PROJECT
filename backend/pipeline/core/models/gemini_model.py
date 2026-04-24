"""
Gemini Model Manager — Google Generative AI & LangChain Integration
`core/utils.py`에서 분리된 Gemini API 관리 도메인입니다.
"""

import os
import threading
from collections import OrderedDict
from typing import Any, List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from google import genai
from version import DEFAULT_MODEL, DEFAULT_TEMPERATURE

# ── 상수 및 캐시 설정 ────────────────────────────────
_CACHE_LIMIT = 32
_llm_cache: OrderedDict[str, ChatGoogleGenerativeAI] = OrderedDict()
_raw_cache: OrderedDict[str, genai.Client] = OrderedDict()
_llm_cache_lock = threading.Lock()
_raw_cache_lock = threading.Lock()





def _remember_cache_entry(cache: OrderedDict, key: str, value: Any):
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > _CACHE_LIMIT:
        cache.popitem(last=False)


def get_gemini_client(api_key: str, model: str = DEFAULT_MODEL, temperature: float = DEFAULT_TEMPERATURE) -> ChatGoogleGenerativeAI:
    """LangChain 기반의 ChatGoogleGenerativeAI 인스턴스 반환 (싱글톤 캐싱)"""
    from pipeline.core.utils import get_effective_key
    effective_key = get_effective_key(api_key)
    cache_key = f"{effective_key}:{model}:{temperature}"

    with _llm_cache_lock:
        if cache_key in _llm_cache:
            _llm_cache.move_to_end(cache_key)
            return _llm_cache[cache_key]

        llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=effective_key,
            temperature=temperature,
        )
        _remember_cache_entry(_llm_cache, cache_key, llm)
    return llm


def get_raw_genai_client(api_key: str) -> genai.Client:
    """Google GenAI SDK 기반의 원시 클라이언트 반환 (싱글톤 캐싱)"""
    from pipeline.core.utils import get_effective_key
    effective_key = get_effective_key(api_key)
    with _raw_cache_lock:
        if effective_key in _raw_cache:
            _raw_cache.move_to_end(effective_key)
            return _raw_cache[effective_key]

        client = genai.Client(api_key=effective_key)
        _remember_cache_entry(_raw_cache, effective_key, client)
    return client
