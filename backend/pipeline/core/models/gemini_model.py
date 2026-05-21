"""
Gemini Model Manager — Google Generative AI & LangChain Integration
`core/utils.py`에서 분리된 Gemini API 관리 도메인입니다.
"""

import os
import threading
from collections import OrderedDict
from typing import Any, List, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from google import genai
from version import DEFAULT_MODEL, DEFAULT_TEMPERATURE
from observability.logger import get_logger

logger = get_logger()

# ── 상수 및 캐시 설정 ────────────────────────────────
_CACHE_LIMIT = 32
_llm_cache: OrderedDict[str, BaseChatModel] = OrderedDict()
_raw_cache: OrderedDict[str, genai.Client] = OrderedDict()
_llm_cache_lock = threading.Lock()
_raw_cache_lock = threading.Lock()


def _remember_cache_entry(cache: OrderedDict, key: str, value: Any):
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > _CACHE_LIMIT:
        cache.popitem(last=False)


def get_gemini_client(api_key: str, model: str = DEFAULT_MODEL, temperature: float = DEFAULT_TEMPERATURE) -> BaseChatModel:
    """LangChain 기반의 LLM 인스턴스 반환 (Vertex AI 우선 적용 및 실패 시 Fallback 지원)"""
    from pipeline.core.utils import get_effective_key
    effective_key = get_effective_key(api_key)
    cache_key = f"{effective_key}:{model}:{temperature}"

    with _llm_cache_lock:
        if cache_key in _llm_cache:
            _llm_cache.move_to_end(cache_key)
            return _llm_cache[cache_key]

        use_vertex = os.environ.get("USE_VERTEX_AI", "true").lower() == "true"
        llm = None
        
        if use_vertex:
            try:
                from langchain_google_vertexai import ChatVertexAI
                project_id = os.environ.get("GCP_PROJECT_ID")
                location = os.environ.get("GCP_LOCATION", "us-central1")
                
                # Vertex AI 초기화 시도
                llm = ChatVertexAI(
                    model_name=model,
                    temperature=temperature,
                    project=project_id,
                    location=location
                )
                logger.info(f"Vertex AI (ChatVertexAI) 인스턴스가 성공적으로 초기화되었습니다: {model}")
            except Exception as e:
                logger.warning(f"Vertex AI 초기화 실패, 기존 Google API로 폴백합니다. 원인: {e}")
                llm = None
        
        if llm is None:
            # Fallback 또는 USE_VERTEX_AI=false 인 경우
            llm = ChatGoogleGenerativeAI(
                model=model,
                google_api_key=effective_key,
                temperature=temperature,
            )

        _remember_cache_entry(_llm_cache, cache_key, llm)
    return llm


def get_raw_genai_client(api_key: str) -> genai.Client:
    """Google GenAI SDK 기반의 원시 클라이언트 반환 (Vertex AI 우선 및 Fallback)"""
    from pipeline.core.utils import get_effective_key
    effective_key = get_effective_key(api_key)
    with _raw_cache_lock:
        if effective_key in _raw_cache:
            _raw_cache.move_to_end(effective_key)
            return _raw_cache[effective_key]

        use_vertex = os.environ.get("USE_VERTEX_AI", "true").lower() == "true"
        client = None

        if use_vertex:
            try:
                project_id = os.environ.get("GCP_PROJECT_ID")
                location = os.environ.get("GCP_LOCATION", "us-central1")
                client = genai.Client(vertexai=True, project=project_id, location=location)
                logger.info("Vertex AI (genai.Client)가 성공적으로 초기화되었습니다.")
            except Exception as e:
                logger.warning(f"Vertex AI 원시 클라이언트 초기화 실패, 기존 Google API로 폴백합니다. 원인: {e}")
                client = None

        if client is None:
            client = genai.Client(api_key=effective_key)

        _remember_cache_entry(_raw_cache, effective_key, client)
    return client
