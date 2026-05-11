"""
Code Embedding Node
code_chunker_node가 생성한 코드 청크를 nomic-embed-text로 벡터화하고
project_code_knowledge 컬렉션에 저장합니다.
"""

from typing import Any, Dict

from pipeline.core.state import PipelineState, make_sget
from pipeline.core.models.google_embed_model import get_google_embeddings_batch, MODEL_NAME
from pipeline.domain.rag.schemas import CodeChunk, RAGIngestOutput
from pipeline.domain.rag.nodes.project_db import upsert_code_chunks_batch
from observability.logger import get_logger

logger = get_logger()


def code_embedding_node(state: PipelineState) -> Dict[str, Any]:
    sget = make_sget(state)
    action_type = (sget("action_type", "") or "").strip().upper()
    api_key = sget("api_key", "")
    # session_id는 source_dir 해시 기반 영속 키. 없으면 run_id로 폴백.
    session_id = sget("session_id", "") or sget("run_id", "unknown")
    raw_chunks = sget("rag_chunks", []) or []

    if action_type == "CREATE":
        output = RAGIngestOutput(session_id=session_id, chunks_ingested=0, status="skipped")
        return {"rag_ingest_output": output.model_dump()}

    logger.info(f"[code_embedding] {len(raw_chunks)}개 청크 임베딩 시작 (model={MODEL_NAME})")

    if not raw_chunks:
        # 이전 노드(code_chunker)에서 이미 인덱싱되어 스킵한 경우, 중복 로그를 피하기 위해 바로 반환
        index_status = sget("rag_index_status") or {}
        if index_status.get("has_index"):
            return {"rag_ingest_output": RAGIngestOutput(session_id=session_id, chunks_ingested=0, status="skipped").model_dump()}

        output = RAGIngestOutput(session_id=session_id, chunks_ingested=0, status="empty")
        return {
            "rag_ingest_output": output.model_dump(),
            "thinking_log": (sget("thinking_log", []) or []) + [
                {"node": "code_embedding", "thinking": "임베딩할 청크가 없습니다."}
            ],
        }

    chunks_list = []
    texts = []

    for raw in raw_chunks:
        try:
            chunk = CodeChunk(**raw)
            chunks_list.append(chunk)
            texts.append(chunk.content_text)
        except Exception as e:
            logger.warning(f"[code_embedding] 청크 초기화 실패 ({raw.get('chunk_id', '?')}): {e}")

    ingested = len(chunks_list)
    if ingested > 0:
        try:
            vectors = get_google_embeddings_batch(texts, api_key=api_key)
            upsert_code_chunks_batch(session_id, chunks_list, vectors)
        except Exception as e:
            logger.warning(f"[code_embedding] 배치 임베딩/저장 실패: {e}")
            ingested = 0

    status = "success" if ingested == len(raw_chunks) else ("partial" if ingested > 0 else "empty")
    output = RAGIngestOutput(session_id=session_id, chunks_ingested=ingested, status=status)

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
