"""
RAG Pipeline Graphs
- get_rag_ingest_pipeline(): code_chunker_node → code_embedding_node
- get_rag_query_pipeline(): code_retriever_node (단일 노드, 쿼리 전용)
"""

from langgraph.graph import StateGraph, END

from pipeline.core.state import PipelineState
from pipeline.domain.rag.nodes.code_chunker import code_chunker_node
from pipeline.domain.rag.nodes.code_embedding import code_embedding_node
from pipeline.domain.rag.nodes.code_retriever import code_retriever_node


def get_rag_ingest_pipeline():
    """소스 디렉터리 → 청킹 → 임베딩 → ChromaDB 저장 파이프라인"""
    graph = StateGraph(PipelineState)
    graph.add_node("code_chunker", code_chunker_node)
    graph.add_node("code_embedding", code_embedding_node)
    graph.set_entry_point("code_chunker")
    graph.add_edge("code_chunker", "code_embedding")
    graph.add_edge("code_embedding", END)
    return graph.compile()


def get_rag_query_pipeline():
    """rag_query_input → project_code_knowledge 검색 → rag_query_result 파이프라인"""
    graph = StateGraph(PipelineState)
    graph.add_node("code_retriever", code_retriever_node)
    graph.set_entry_point("code_retriever")
    graph.add_edge("code_retriever", END)
    return graph.compile()
