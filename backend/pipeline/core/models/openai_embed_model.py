import os
import time
import random
from typing import List, Optional
from openai import OpenAI
from observability.logger import get_logger

logger = get_logger()

def get_openai_client(api_key: str = ""):
    """OpenAI 클라이언트 생성 (환경변수 혹은 인자값 사용)"""
    key = api_key or os.environ.get("OPENAI_API_KEY", "")
    if not key:
        return None
    return OpenAI(api_key=key)

def get_openai_embeddings(text: str, model: str = "text-embedding-3-large", api_key: str = "") -> List[float]:
    """OpenAI 임베딩 생성 (단일 호출)"""
    client = get_openai_client(api_key)
    if not client:
        raise ValueError("OpenAI API Key가 설정되지 않았습니다.")
        
    # text-embedding-3-large의 경우 dimensions 파라미터로 3072 고정 가능
    dimensions = 3072 if "3-large" in model else 1536
    
    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = client.embeddings.create(
                model=model,
                input=text,
                dimensions=dimensions if "ada" not in model else None
            )
            return response.data[0].embedding
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                wait_time = 5 + random.uniform(2, 5)
                logger.warning(f"[OpenAIEmbed] Rate limit, retry in {wait_time:.2f}s...")
                time.sleep(wait_time)
                continue
            raise e

def get_openai_embeddings_batch(texts: List[str], model: str = "text-embedding-3-large", api_key: str = "") -> List[List[float]]:
    """OpenAI 임베딩 생성 (배치 호출)"""
    client = get_openai_client(api_key)
    if not client:
        raise ValueError("OpenAI API Key가 설정되지 않았습니다.")
        
    dimensions = 3072 if "3-large" in model else 1536
    MAX_BATCH_SIZE = 100
    all_embeddings = []
    
    for i in range(0, len(texts), MAX_BATCH_SIZE):
        batch = texts[i : i + MAX_BATCH_SIZE]
        
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = client.embeddings.create(
                    model=model,
                    input=batch,
                    dimensions=dimensions if "ada" not in model else None
                )
                all_embeddings.extend([item.embedding for item in response.data])
                break
            except Exception as e:
                if "429" in str(e) and attempt < max_retries - 1:
                    wait_time = 10 + random.uniform(5, 10)
                    logger.warning(f"[OpenAIEmbed] Batch rate limit, retry in {wait_time:.2f}s...")
                    time.sleep(wait_time)
                    continue
                raise e
                
    return all_embeddings
