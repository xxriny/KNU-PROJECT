"""
PM Artifact Embedding Node
PM 산출물(PMBundle)을 임베딩하고 RAG(pm_db)에 저장합니다.
"""

from typing import Dict, Any
from pipeline.core.state import PipelineState, make_sget
from pipeline.core.models.pm_embedding_model import get_pm_embeddings, MODEL_NAME
from pipeline.domain.pm.nodes.pm_db import upsert_pm_artifact
from observability.logger import get_logger

logger = get_logger()

def pm_embedding_node(state: PipelineState) -> Dict[str, Any]:
    sget = make_sget(state)
    logger.info("Starting pm_embedding_node")
    
    pm_bundle = sget("pm_bundle")
    run_id = sget("run_id", "unknown")
    
    if not pm_bundle:
        logger.warning("No PM bundle found to embed.")
        return {}

    try:
        # 1. 시각적 일관성을 위해 노드 레벨에서 임베딩 수행
        # (pm_db 내부에서도 자동 수행되지만, 명시적 노드에서 미리 수행하여 넘겨줌)
        artifact_type = pm_bundle.get("metadata", {}).get("artifact_type", "RTM_STACK_BUNDLE")
        text_to_embed = f"{artifact_type}: {str(pm_bundle)[:2000]}"
        
        logger.info(f"Embedding PM artifact using {MODEL_NAME}...")
        vector = get_pm_embeddings(text_to_embed)
        
        # 2. RAG 저장소(pm_db)에 업서트
        upsert_pm_artifact(
            session_id=run_id,
            artifact_data=pm_bundle,
            artifact_type=artifact_type,
            version=pm_bundle.get("metadata", {}).get("version", "v1.0"),
            vector=vector
        )
        
        thinking_msg = f"PM 산출물({artifact_type}) 임베딩 및 RAG 저장 완료."
        
        return {
            "thinking_log": (sget("thinking_log", []) or []) + [{"node": "pm_embedding", "thinking": thinking_msg}]
        }
        
    except Exception as e:
        logger.exception(f"pm_embedding_node critical failure: {e}")
        return {}
