"""
SA Artifact Embedding Node
SA 설계 산출물(SAArchBundle)을 임베딩하고 RAG(sa_db)에 저장합니다.
"""

from typing import Dict, Any
from pipeline.core.state import PipelineState, make_sget
from pipeline.core.models.pm_embedding_model import get_pm_embeddings, MODEL_NAME
from pipeline.domain.sa.nodes.sa_db import upsert_sa_artifact
from observability.logger import get_logger

logger = get_logger()

def sa_embedding_node(state: PipelineState) -> Dict[str, Any]:
    sget = make_sget(state)
    logger.info("=== [Node Entry] sa_embedding_node ===")
    
    sa_bundle = sget("sa_arch_bundle")
    run_id = sget("run_id", "unknown")
    
    if not sa_bundle:
        logger.warning("No SA bundle found to embed.")
        return {
            "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_embedding", "thinking": "저장할 SA 산출물이 없습니다."}]
        }

    data = sa_bundle.get("data", {})
    comp_count = len(data.get("components", []))
    api_count = len(data.get("apis", []))
    table_count = len(data.get("tables", []))
    logger.info(f"Embedding SA bundle [{run_id}]: Comp({comp_count}), API({api_count}), Table({table_count})")

    try:
        # PM과 동일한 라이프사이클로 명시적 임베딩 수행
        artifact_type = "SA_ARCH_BUNDLE"
        text_to_embed = f"{artifact_type}: {str(sa_bundle)[:2000]}"
        
        logger.info(f"Embedding SA artifact using {MODEL_NAME}...")
        vector = get_pm_embeddings(text_to_embed)
        
        # RAG 저장소(sa_db)에 업서트
        upsert_sa_artifact(
            session_id=run_id,
            artifact_data=sa_bundle,
            artifact_type=artifact_type,
            version=sa_bundle.get("metadata", {}).get("version", "v1.0"),
            vector=vector
        )
        
        thinking_msg = f"SA 설계 산출물({artifact_type}) 임베딩 및 RAG 저장 완료."
        
        return {
            "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_embedding", "thinking": thinking_msg}]
        }
        
    except Exception as e:
        logger.exception(f"sa_embedding_node critical failure: {e}")
        return {}
