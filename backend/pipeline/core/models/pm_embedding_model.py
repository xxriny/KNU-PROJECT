"""
PM Embedding Model Manager — BGE-M3 for PM/SA Artifacts
기획 산출물 및 설계서의 의미론적 검색을 위한 임베딩을 담당합니다.
"""

import threading
from typing import List, Optional
from sentence_transformers import SentenceTransformer
from observability.logger import get_logger

logger = get_logger()

# ── 모델 설정 ──────────────────────────────────
MODEL_NAME = "BAAI/bge-m3"
_pm_model_instance: Optional[SentenceTransformer] = None
_pm_model_lock = threading.Lock()

def get_pm_embedding_model() -> SentenceTransformer:
    """PM/SA 전용 임베딩 모델 인스턴스 반환 (싱글톤)"""
    global _pm_model_instance
    if _pm_model_instance is None:
        with _pm_model_lock:
            if _pm_model_instance is None:
                # RTX 50-series(sm_120) 커널 비호환 방지를 위해 CPU로 강제 로딩
                _pm_model_instance = SentenceTransformer(MODEL_NAME, device="cpu")
    return _pm_model_instance

def get_pm_embeddings(text: str) -> List[float]:
    """텍스트를 벡터로 변환 (1024차원)"""
    model = get_pm_embedding_model()
    # numpy array를 list로 변환하여 반환
    return model.encode(text).tolist()
