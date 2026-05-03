"""
PM Artifact Embedding Node
PM 산출물(PMBundle)을 임베딩하고 RAG(pm_db)에 저장합니다.
pm_analysis가 제거되었으므로, pm_bundle이 없으면 자체 조립합니다.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List
from pipeline.core.state import PipelineState, make_sget
from pipeline.core.models.pm_embedding_model import get_pm_embeddings, MODEL_NAME
from pipeline.domain.pm.nodes.pm_db import upsert_pm_artifact
from observability.logger import get_logger

logger = get_logger()


def _assemble_pm_bundle(features: List[Dict], stack_mapping: List[Dict], run_id: str) -> Dict:
    """features + stack_mapping → pm_bundle 조립 (LLM 불필요, 순수 데이터 병합)"""
    feature_ids = {f.get("id") for f in features}
    approved_ids = {m.get("f_id") for m in stack_mapping if m.get("status") == "APPROVED"}
    coverage = round(len(feature_ids & approved_ids) / max(len(feature_ids), 1), 3)

    return {
        "metadata": {
            "session_id": run_id,
            "bundle_id": f"{run_id}_PM_BNDL",
            "version": "1.0",
            "phase": "PM",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        "data": {
            "rtm": [
                {"feature_id": f.get("id"), "category": f.get("cat", f.get("category", "")),
                 "description": f.get("desc", f.get("description", "")),
                 "priority": f.get("pri", f.get("priority", "")),
                 "dependencies": f.get("deps", f.get("dependencies", [])),
                 "test_criteria": f.get("tc", f.get("test_criteria", ""))}
                for f in features
            ],
            "tech_stacks": [
                {"feature_id": m.get("f_id", m.get("feature_id")),
                 "domain": m.get("dom", m.get("domain", "")),
                 "pkg": m.get("pkg", m.get("package", "")),
                 "status": m.get("status", "APPROVED")}
                for m in stack_mapping
            ],
        },
        "_coverage_rate": coverage,
    }


def pm_embedding_node(state: PipelineState) -> Dict[str, Any]:
    sget = make_sget(state)
    logger.info("Starting pm_embedding_node")
    
    pm_bundle = sget("pm_bundle")
    run_id = sget("run_id", "unknown")
    
    # pm_analysis가 제거되었으므로, pm_bundle이 없으면 자체 조립
    if not pm_bundle:
        features = sget("features", [])
        planner_out = sget("stack_planner_output", {})
        stack_mapping = planner_out.get("m", planner_out.get("stack_mapping", []))
        
        if features:
            pm_bundle = _assemble_pm_bundle(features, stack_mapping, run_id)
            logger.info(f"[PM Embedding] Auto-assembled pm_bundle: {len(features)} RTM, {len(stack_mapping)} stacks")
        else:
            logger.warning("No PM bundle and no features found to embed.")
            return {}

    # 커버리지 추출
    coverage_rate = pm_bundle.pop("_coverage_rate", 0.0) if isinstance(pm_bundle, dict) else 0.0

    try:
        artifact_type = pm_bundle.get("metadata", {}).get("artifact_type", "PM_BUNDLE")
        text_to_embed = f"{artifact_type}: {str(pm_bundle)[:2000]}"
        
        logger.info(f"Embedding PM artifact using {MODEL_NAME}...")
        vector = get_pm_embeddings(text_to_embed)
        
        upsert_pm_artifact(
            session_id=run_id,
            artifact_data=pm_bundle,
            artifact_type=artifact_type,
            version=pm_bundle.get("metadata", {}).get("version", "1.0"),
            vector=vector
        )
        
        thinking_msg = f"PM 산출물({artifact_type}) 임베딩 및 RAG 저장 완료."
        
        return {
            "pm_bundle": pm_bundle,
            "pm_coverage_rate": coverage_rate,
            "thinking_log": (sget("thinking_log", []) or []) + [{"node": "pm_embedding", "thinking": thinking_msg}]
        }
        
    except Exception as e:
        logger.exception(f"pm_embedding_node critical failure: {e}")
        return {"pm_bundle": pm_bundle, "pm_coverage_rate": coverage_rate}
