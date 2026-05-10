"""
Google Gemini Embedding Model Manager
로컬 모델 대신 Google API를 사용하여 임베딩을 생성합니다.
"""

from typing import List, Optional
from observability.logger import get_logger
from pipeline.core.models.gemini_model import get_raw_genai_client

logger = get_logger()

# Google API docs: "최신 모델인 gemini-embedding-2는 Gemini API의 첫 번째 멀티모달 임베딩 모델입니다."
MODEL_NAME = "gemini-embedding-2"

def get_google_embeddings(text: str, api_key: str = "") -> List[float]:
    """텍스트를 벡터로 변환 (Gemini gemini-embedding-2, 768차원)"""
    try:
        client = get_raw_genai_client(api_key)
        response = client.models.embed_content(
            model=MODEL_NAME,
            contents=text
        )
        return response.embeddings[0].values
    except Exception as e:
        logger.error(f"[GoogleEmbed] Single embedding failed: {e}")
        raise

def get_google_embeddings_batch(texts: List[str], api_key: str = "") -> List[List[float]]:
    """여러 텍스트를 배치로 변환 (Gemini gemini-embedding-2)"""
    if not texts:
        return []
    
    # API 호출 제한을 피하기 위해 100개씩 나누어 처리
    MAX_BATCH_SIZE = 100
    all_embeddings = []
    
    try:
        client = get_raw_genai_client(api_key)
        
        for i in range(0, len(texts), MAX_BATCH_SIZE):
            batch_texts = texts[i : i + MAX_BATCH_SIZE]
            response = client.models.embed_content(
                model=MODEL_NAME,
                contents=batch_texts
            )
            all_embeddings.extend([e.values for e in response.embeddings])
            
        return all_embeddings
    except Exception as e:
        logger.error(f"[GoogleEmbed] Batch embedding failed: {e}")
        raise
