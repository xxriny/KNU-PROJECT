"""
Stack Embedding Node
Guardian 노드를 통과한 기술 스택 데이터를 고차원 벡터로 변환합니다.
HuggingFace의 'intfloat/multilingual-e5-small' 모델을 사용합니다.
"""

import threading
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer

from pipeline.core.state import PipelineState, make_sget
from pipeline.domain.pm.schemas import StackSourceData, EmbeddingOutput
from observability.logger import get_logger

logger = get_logger()

# ── 모델 싱글톤 로더 ────────────────────────────────
_model_instance: Optional[SentenceTransformer] = None
_model_lock = threading.Lock()
MODEL_NAME = "intfloat/multilingual-e5-small"

def get_embedding_model() -> SentenceTransformer:
    global _model_instance
    if _model_instance is None:
        with _model_lock:
            if _model_instance is None:
                logger.info(f"Loading embedding model: {MODEL_NAME}...")
                # 처음 실행 시 모델 다운로드로 인해 시간이 소요될 수 있음
                _model_instance = SentenceTransformer(MODEL_NAME)
    return _model_instance

def stack_embedding_node(state: PipelineState) -> Dict[str, Any]:
    sget = make_sget(state)
    logger.info("Starting stack_embedding_node")
    
    guardian_output = sget("guardian_output", {})
    if guardian_output.get("status") != "APPROVED":
        logger.warning("Guardian status is not APPROVED. Skipping embedding.")
        return {
            "stack_embedding_output": {
                "vector": [],
                "text_embedded": "",
                "model_name": MODEL_NAME,
                "thinking": "Guardian 노드가 데이터를 승인하지 않아 임베딩을 스킵함."
            }
        }
        
    final_data_raw = guardian_output.get("final_data")
    if not final_data_raw:
        return {"stack_embedding_output": {"vector": [], "text_embedded": "", "model_name": MODEL_NAME, "thinking": "최종 데이터가 없음."}}
        
    final_data = StackSourceData(**final_data_raw)
    
    # 1. 임베딩 대상 텍스트 생성 (Name + Description 조합)
    # E5 모델의 경우 'query: ' 또는 'passage: ' 접두사를 사용하는 것이 권장되기도 하지만, 
    # 일반적인 문장 임베딩에서는 텍스트 결합만으로도 충분함.
    text_to_embed = f"{final_data.name}: {final_data.description}"
    
    try:
        # 2. 모델 로드 및 벡터 추출
        model = get_embedding_model()
        vector = model.encode(text_to_embed).tolist() # JSON 직렬화를 위해 list로 변환
        
        thinking_msg = f"'{final_data.name}' 데이터를 {MODEL_NAME} 모델로 임베딩 완료 (차원: {len(vector)})"
        
        return {
            "stack_embedding_output": {
                "vector": vector,
                "text_embedded": text_to_embed,
                "model_name": MODEL_NAME,
                "thinking": thinking_msg
            },
            "thinking_log": (sget("thinking_log", []) or []) + [{"node": "stack_embedding", "thinking": thinking_msg}]
        }
        
    except Exception as e:
        logger.exception("stack_embedding_node critical failure")
        return {
            "stack_embedding_output": {
                "vector": [],
                "text_embedded": text_to_embed,
                "model_name": MODEL_NAME,
                "thinking": f"임베딩 중 오류 발생: {str(e)}"
            }
        }
