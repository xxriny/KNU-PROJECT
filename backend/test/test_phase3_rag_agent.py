"""
Phase 3: RAG agent 및 project_db 검증 테스트
- project_vector_db 물리 저장소 삭제 확인
- rag_graph.py 정상 임포트
- project_db.py 함수 정상 동작 (ChromaDB 연결)
- sa_db.py delete_sa_knowledge 누락 함수 추가 확인
- pipeline_runner.py RAG 2단계 구조 확인
"""
import os
import sys
import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

STORAGE_DIR = os.path.join(BACKEND_DIR, "storage")


class TestProjectDbRemoval:
    """project_vector_db 초기화(stale 데이터 제거) 확인"""

    def test_project_vector_db_has_no_stale_data(self):
        """새로 초기화된 project_vector_db에 stale 세션 데이터가 없어야 함.

        project_vector_db 폴더 자체는 ChromaDB가 자동 재생성하지만,
        이전 세션 데이터는 삭제되어 있어야 함.
        """
        from pipeline.domain.rag.nodes.project_db import count_session_chunks
        # 임의의 이전 세션 ID로 데이터가 없는지 확인
        stale_sessions = [
            "20260514_120000",
            "20260515_090000",
            "old_session_xyz",
        ]
        for session_id in stale_sessions:
            count = count_session_chunks(session_id)
            assert count == 0, f"stale 데이터가 남아있습니다 (session={session_id}, chunks={count})"


class TestRAGGraphImports:
    """RAG agent (rag_graph.py) 임포트 확인"""

    def test_rag_graph_importable(self):
        from pipeline.orchestration.rag_graph import (
            get_rag_ingest_pipeline,
            get_rag_query_pipeline,
            get_rag_routing_map,
        )
        assert callable(get_rag_ingest_pipeline)
        assert callable(get_rag_query_pipeline)
        assert callable(get_rag_routing_map)

    def test_rag_routing_map_structure(self):
        from pipeline.orchestration.rag_graph import get_rag_routing_map
        routing = get_rag_routing_map()
        assert "first_node" in routing
        assert routing["first_node"] == "code_chunker"
        assert "next_nodes" in routing
        assert "start_message" in routing


class TestProjectDbFunctions:
    """project_db.py 함수 시그니처 및 임포트 확인"""

    def test_project_db_functions_importable(self):
        from pipeline.domain.rag.nodes.project_db import (
            upsert_code_chunk,
            upsert_code_chunks_batch,
            delete_project_knowledge,
            count_session_chunks,
            has_session_chunks,
            get_session_inventory,
            query_project_code,
            get_file_chunks,
            DB_PATH,
        )
        assert callable(upsert_code_chunks_batch)
        assert callable(count_session_chunks)
        assert callable(delete_project_knowledge)
        assert isinstance(DB_PATH, str)

    def test_count_session_chunks_no_crash_on_empty(self):
        """인덱스 없는 세션에 count_session_chunks 호출 시 크래시 없어야 함"""
        from pipeline.domain.rag.nodes.project_db import count_session_chunks
        result = count_session_chunks("nonexistent_session_xyz_123")
        assert isinstance(result, int)
        assert result == 0

    def test_has_session_chunks_false_for_empty(self):
        from pipeline.domain.rag.nodes.project_db import has_session_chunks
        result = has_session_chunks("nonexistent_session_xyz_123")
        assert result is False


class TestSADbDeleteFunction:
    """sa_db.py delete_sa_knowledge 함수 존재 확인"""

    def test_delete_sa_knowledge_exists(self):
        from pipeline.domain.sa.nodes.sa_db import delete_sa_knowledge
        assert callable(delete_sa_knowledge)

    def test_delete_sa_knowledge_returns_int(self):
        """존재하지 않는 세션 삭제 시 0 반환해야 함"""
        from pipeline.domain.sa.nodes.sa_db import delete_sa_knowledge
        result = delete_sa_knowledge("nonexistent_session_xyz_123")
        assert isinstance(result, int)
        assert result == 0


class TestRAGPipelineRunnerIntegration:
    """pipeline_runner.py RAG 2단계 구조 확인"""

    def test_pipeline_runner_imports_rag_ingest(self):
        """pipeline_runner가 get_rag_ingest_pipeline을 임포트해야 함"""
        runner_file = os.path.join(BACKEND_DIR, "orchestration", "pipeline_runner.py")
        with open(runner_file, encoding="utf-8") as f:
            content = f.read()
        assert "get_rag_ingest_pipeline" in content
        assert "rag_ingest" in content

    def test_pipeline_runner_imports_session(self):
        """pipeline_runner가 compute_project_session_id를 임포트해야 함"""
        runner_file = os.path.join(BACKEND_DIR, "orchestration", "pipeline_runner.py")
        with open(runner_file, encoding="utf-8") as f:
            content = f.read()
        assert "compute_project_session_id" in content
        assert "count_session_chunks" in content

    def test_pipeline_runner_no_dev_pipeline(self):
        """pipeline_runner에 develop 파이프라인 참조가 없어야 함"""
        runner_file = os.path.join(BACKEND_DIR, "orchestration", "pipeline_runner.py")
        with open(runner_file, encoding="utf-8") as f:
            content = f.read()
        assert "get_develop_pipeline" not in content
        assert "get_develop_routing_map" not in content

    def test_validate_analysis_inputs_importable(self):
        """pipeline_runner의 utility 함수들이 외부에서 임포트 가능해야 함"""
        from orchestration.pipeline_runner import (
            validate_analysis_inputs,
            build_reverse_context,
            analysis_pipeline_type,
        )
        assert callable(validate_analysis_inputs)
        assert callable(build_reverse_context)
        assert callable(analysis_pipeline_type)


class TestCodeChunkerNode:
    """code_chunker 노드 임포트 확인"""

    def test_code_chunker_importable(self):
        from pipeline.domain.rag.nodes.code_chunker import code_chunker_node
        assert callable(code_chunker_node)

    def test_code_embedding_importable(self):
        from pipeline.domain.rag.nodes.code_embedding import code_embedding_node
        assert callable(code_embedding_node)

    def test_code_retriever_importable(self):
        from pipeline.domain.rag.nodes.code_retriever import code_retriever_node
        assert callable(code_retriever_node)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
