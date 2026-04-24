"""
Code Embedding Model Manager — nomic-embed-text-v1 for PROJECT_RAG
코드 스니펫의 의미론적 검색을 위한 임베딩을 담당합니다. (768차원)
"""

import threading
from typing import List, Optional
from sentence_transformers import SentenceTransformer
from observability.logger import get_logger

logger = get_logger()

MODEL_NAME = "nomic-ai/nomic-embed-text-v1"
_nomic_model_instance: Optional[SentenceTransformer] = None
_nomic_model_lock = threading.Lock()


def get_nomic_embedding_model() -> SentenceTransformer:
    """코드 전용 임베딩 모델 인스턴스 반환 (싱글톤)"""
    global _nomic_model_instance
    if _nomic_model_instance is None:
        with _nomic_model_lock:
            if _nomic_model_instance is None:
                # RTX 50-series(sm_120) 커널 비호환 방지를 위해 CPU로 강제 로딩
                _nomic_model_instance = SentenceTransformer(
                    MODEL_NAME,
                    trust_remote_code=True,
                    device="cpu",
                )
    return _nomic_model_instance


def get_nomic_embeddings(text: str) -> List[float]:
    """텍스트를 벡터로 변환 (768차원)"""
    model = get_nomic_embedding_model()
    return model.encode(text).tolist()
