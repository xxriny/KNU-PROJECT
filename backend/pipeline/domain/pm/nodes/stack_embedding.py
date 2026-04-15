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
from pipeline.domain.pm.nodes.stack_db import upsert_stack_entry
from pipeline.core.models.stack_embedding_model import get_stack_embeddings, MODEL_NAME
from observability.logger import get_logger

logger = get_logger()

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
        # 2. 모델 로드 및 벡터 추출 (공용 엔진 사용)
        vector = get_stack_embeddings(text_to_embed)
        
        thinking_msg = f"'{final_data.name}' 데이터를 {MODEL_NAME} 모델로 임베딩 완료 (차원: {len(vector)})"

        # 3. [RAG Persistence] 기술 스택 지식 전용 DB에 저장
        try:
            run_id = sget("run_id", "unknown")
            upsert_stack_entry(
                session_id=run_id,
                stack_data={
                    "package_name": final_data.name,
                    "domain": sget("current_domain", "unknown"),
                    "version_req": final_data.version,
                    "install_cmd": final_data.install_cmd or "unknown",
                    "content_text": text_to_embed
                },
                vector=vector
            )
        except Exception as db_err:
            logger.warning(f"Failed to persist stack entry to stack_db: {db_err}")

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
