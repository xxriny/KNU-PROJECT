"""
Stack Embedding Model Manager — BGE-M3 for Tech Stack Knowledge
기술 스택 라이브러리 및 도구의 의미론적 검색을 위한 임베딩을 담당합니다.
"""

import threading
from typing import List, Optional
from sentence_transformers import SentenceTransformer
from observability.logger import get_logger

logger = get_logger()

# ── 모델 설정 ──────────────────────────────────
MODEL_NAME = "BAAI/bge-m3"
_stack_model_instance: Optional[SentenceTransformer] = None
_stack_model_lock = threading.Lock()

def get_stack_embedding_model() -> SentenceTransformer:
    """기술 스택 전용 임베딩 모델 인스턴스 반환 (싱글톤)"""
    global _stack_model_instance
    if _stack_model_instance is None:
        with _stack_model_lock:
            if _stack_model_instance is None:
                # RTX 50-series(sm_120) 커널 비호환 방지를 위해 CPU로 강제 로딩
                _stack_model_instance = SentenceTransformer(MODEL_NAME, device="cpu")
    return _stack_model_instance

def get_stack_embeddings(text: str) -> List[float]:
    """기술 스택 텍스트를 벡터로 변환 (1024차원)"""
    model = get_stack_embedding_model()
    return model.encode(text).tolist()
