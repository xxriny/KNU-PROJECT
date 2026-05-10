import time
import random
import re
import os
from typing import List, Optional, Dict
from observability.logger import get_logger
from pipeline.core.models.gemini_model import get_raw_genai_client
from pipeline.core.models.openai_embed_model import get_openai_embeddings, get_openai_embeddings_batch

logger = get_logger()

# 통합 모델 리스트
ALL_EMBED_MODELS = [
    {"provider": "google", "name": "gemini-embedding-2", "dim": 3072},
    {"provider": "google", "name": "gemini-embedding-001", "dim": 3072},
    {"provider": "openai", "name": "text-embedding-3-large", "dim": 3072},
    {"provider": "openai", "name": "text-embedding-3-small", "dim": 1536},
]

# 모델별 상태 관리 (대기 시간 기록)
# { "model_name": next_available_time }
models_next_available: Dict[str, float] = {m["name"]: 0.0 for m in ALL_EMBED_MODELS}

# 레거시 호환성
MODEL_NAME = ALL_EMBED_MODELS[0]["name"]
EMBED_MODELS = [m["name"] for m in ALL_EMBED_MODELS if m["provider"] == "google"]

MODEL_TOKEN_LIMITS = {
    "gemini-embedding-2": 8000,
    "gemini-embedding-001": 2000,
    "text-embedding-3-large": 8000,
    "text-embedding-3-small": 8000
}

def _pad_vector(vector: List[float], target_dim: int = 3072) -> List[float]:
    current_dim = len(vector)
    if current_dim >= target_dim: return vector[:target_dim]
    return vector + [0.0] * (target_dim - current_dim)

def _get_retry_delay(err_msg: str) -> float:
    """에러 메시지에서 대기 시간 추출"""
    delay_match = re.search(r"retry in (\d+\.?\d*)s", err_msg)
    if delay_match:
        return float(delay_match.group(1)) + 1.0
    return 30.0 + random.uniform(5, 10)

def get_google_embeddings(text: str, api_key: str = "") -> List[float]:
    """텍스트를 벡터로 변환 (병렬/비차단 폴백)"""
    last_error = None
    start_time = time.time()
    # 전체 시도 시간 제한 (예: 5분)
    TIMEOUT = 300 
    
    while time.time() - start_time < TIMEOUT:
        available_model_found = False
        
        for m in ALL_EMBED_MODELS:
            model_name = m["name"]
            provider = m["provider"]
            
            # 현재 모델이 사용 가능한지 체크 (비차단)
            if time.time() < models_next_available.get(model_name, 0):
                continue
            
            available_model_found = True
            try:
                limit = MODEL_TOKEN_LIMITS.get(model_name, 2000)
                safe_text = text[:limit * 4]
                
                if provider == "google":
                    client = get_raw_genai_client(api_key)
                    response = client.models.embed_content(model=model_name, contents=safe_text)
                    return response.embeddings[0].values
                else:
                    if not os.environ.get("OPENAI_API_KEY"): continue
                    vector = get_openai_embeddings(safe_text, model=model_name)
                    return _pad_vector(vector)
            except Exception as e:
                last_error = e
                if "429" in str(e):
                    delay = _get_retry_delay(str(e))
                    models_next_available[model_name] = time.time() + delay
                    logger.warning(f"[UnifiedEmbed] {model_name} rate limited. Waiting {delay:.1f}s. Trying next model immediately...")
                    # 멈추지 않고 다음 모델로 즉시 진행
                    continue
                else:
                    # 429가 아닌 치명적 에러는 해당 모델을 일정 시간 제외
                    models_next_available[model_name] = time.time() + 60
                    continue

        # 만약 모든 모델이 대기 중이라면, 가장 빨리 풀리는 시간만큼만 잠시 휴식
        if not available_model_found:
            min_wait = min(models_next_available.values()) - time.time()
            if min_wait > 0:
                # 너무 오래 기다리지 않도록 최대 5초씩 끊어서 확인
                sleep_time = min(min_wait, 5.0)
                time.sleep(max(sleep_time, 0.1))
                
    raise last_error or Exception("Embedding timeout")

def get_google_embeddings_batch(texts: List[str], api_key: str = "") -> List[List[float]]:
    """여러 텍스트를 배치로 변환 (세션 내 모델 일관성 유지)"""
    if not texts: return []
    
    last_error = None
    MAX_BATCH_SIZE = 100
    all_embeddings = [None] * len(texts)
    pending_indices = list(range(0, len(texts), MAX_BATCH_SIZE))
    
    # [CRITICAL] 한 번 결정된 모델을 이 배치 작업 끝까지 고수 (공간 일관성)
    chosen_model = None
    
    start_time = time.time()
    while pending_indices and (time.time() - start_time < 600):
        # 사용할 모델 후보 결정
        candidate_models = [chosen_model] if chosen_model else ALL_EMBED_MODELS
        
        for m in candidate_models:
            if not m or not pending_indices: break
            
            model_name = m["name"]
            provider = m["provider"]
            
            if time.time() < models_next_available.get(model_name, 0):
                continue
                
            idx_start = pending_indices[0]
            idx_end = min(idx_start + MAX_BATCH_SIZE, len(texts))
            batch = texts[idx_start:idx_end]
            
            try:
                limit = MODEL_TOKEN_LIMITS.get(model_name, 2000)
                safe_batch = [t[:limit * 4] for t in batch]
                
                if provider == "google":
                    client = get_raw_genai_client(api_key)
                    response = client.models.embed_content(model=model_name, contents=safe_batch)
                    batch_results = [e.values for e in response.embeddings]
                else:
                    if not os.environ.get("OPENAI_API_KEY"): 
                        models_next_available[model_name] = time.time() + 3600
                        continue
                    vectors = get_openai_embeddings_batch(safe_batch, model=model_name)
                    batch_results = [_pad_vector(v) for v in vectors]
                
                # 성공 시 모델 고정
                if not chosen_model:
                    chosen_model = m
                    logger.info(f"[UnifiedEmbed] Model locked to {model_name} for this session.")
                
                for i, res in enumerate(batch_results):
                    all_embeddings[idx_start + i] = res
                pending_indices.pop(0)
                logger.info(f"[UnifiedEmbed] Batch {idx_start}-{idx_end} success with {model_name}")
                
            except Exception as e:
                last_error = e
                if "429" in str(e):
                    delay = _get_retry_delay(str(e))
                    models_next_available[model_name] = time.time() + delay
                    logger.warning(f"[UnifiedEmbed] {model_name} limited. Waiting for next candidate...")
                else:
                    models_next_available[model_name] = time.time() + 60
                
                # 모델이 고정되었는데 실패했다면 루프를 돌아 대기
                if chosen_model:
                    time.sleep(2)
                    break
                continue

        if pending_indices and not chosen_model:
            time.sleep(1)
            
    if any(e is None for e in all_embeddings):
        raise last_error or Exception("Batch embedding failed or timed out")
        
    return all_embeddings
