"""
Code Embedding Node
code_chunker_node가 생성한 코드 청크를 nomic-embed-text로 벡터화하고
project_code_knowledge 컬렉션에 저장합니다.
"""

from typing import Any, Dict

from pipeline.core.state import PipelineState, make_sget
from pipeline.core.models.nomic_embed_model import get_nomic_embeddings, MODEL_NAME
from pipeline.domain.rag.schemas import CodeChunk, RAGIngestOutput
from pipeline.domain.rag.nodes.project_db import upsert_code_chunk
from observability.logger import get_logger

logger = get_logger()


def code_embedding_node(state: PipelineState) -> Dict[str, Any]:
    sget = make_sget(state)
    action_type = (sget("action_type", "") or "").strip().upper()
    run_id = sget("run_id", "unknown")
    raw_chunks = sget("rag_chunks", []) or []

    if action_type == "CREATE":
        output = RAGIngestOutput(session_id=run_id, chunks_ingested=0, status="skipped")
        return {"rag_ingest_output": output.model_dump()}

    logger.info(f"[code_embedding] {len(raw_chunks)}개 청크 임베딩 시작 (model={MODEL_NAME})")

    if not raw_chunks:
        output = RAGIngestOutput(session_id=run_id, chunks_ingested=0, status="empty")
        return {
            "rag_ingest_output": output.model_dump(),
            "thinking_log": (sget("thinking_log", []) or []) + [
                {"node": "code_embedding", "thinking": "임베딩할 청크가 없습니다."}
            ],
        }

    ingested = 0
    for raw in raw_chunks:
        try:
            chunk = CodeChunk(**raw)
            vector = get_nomic_embeddings(chunk.content_text)
            upsert_code_chunk(run_id, chunk, vector)
            ingested += 1
        except Exception as e:
            logger.warning(f"[code_embedding] 청크 임베딩 실패 ({raw.get('chunk_id', '?')}): {e}")

    status = "success" if ingested == len(raw_chunks) else ("partial" if ingested > 0 else "empty")
    output = RAGIngestOutput(session_id=run_id, chunks_ingested=ingested, status=status)

    # >>> [EXPERIMENT-RAG-VIS] BEGIN — 추후 원복 시 이 블록을 다음 한 줄로 교체:
    #     thinking = f"{ingested}/{len(raw_chunks)}개 청크 임베딩 및 저장 완료 (status={status})"
    from pipeline.domain.rag.nodes.project_db import DB_PATH as _PROJECT_DB_PATH  # [EXPERIMENT-RAG-VIS]
    _failed = len(raw_chunks) - ingested
    _avg_chars = int(sum(len(r.get("content_text", "")) for r in raw_chunks) / max(len(raw_chunks), 1))
    thinking = (
        f"임베딩 {ingested}/{len(raw_chunks)}개 (status={status}) — 평균 {_avg_chars}자 / 실패 {_failed}건\n"
        f"  저장소: {_PROJECT_DB_PATH}"
    )
    # <<< [EXPERIMENT-RAG-VIS] END
    logger.info(f"[code_embedding] {thinking}")

    return {
        "rag_ingest_output": output.model_dump(),
        "thinking_log": (sget("thinking_log", []) or []) + [
            {"node": "code_embedding", "thinking": thinking}
        ],
    }
