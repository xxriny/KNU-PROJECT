import unittest
import os
import sys
from unittest.mock import patch, MagicMock

# Path setup for direct execution
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_root = os.path.abspath(os.path.join(current_dir, "..", "..", "..", ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from pipeline.domain.rag.nodes.project_db import (
    upsert_code_chunk, 
    upsert_code_chunks_batch,
    query_project_code,
    delete_project_knowledge,
    count_session_chunks
)
from pipeline.domain.rag.schemas import CodeChunk

class TestProjectDB(unittest.TestCase):
    def setUp(self):
        self.session_id = f"test_session_{os.urandom(4).hex()}"
        self.test_chunks = [
            CodeChunk(
                chunk_id=f"chunk_{i}",
                session_id=self.session_id,
                file_path="test.py",
                content_text=f"def test_func_{i}(): pass",
                lang="python",
                func_name=f"test_func_{i}"
            ) for i in range(5)
        ]

    def tearDown(self):
        delete_project_knowledge(self.session_id)

    @patch("pipeline.domain.rag.nodes.project_db.get_google_embeddings")
    def test_upsert_and_count(self, mock_embed):
        """데이터 업서트 및 개수 확인 테스트 (MOCK 임베딩)"""
        mock_embed.return_value = [0.1] * 3072
        
        upsert_code_chunk(self.session_id, self.test_chunks[0], api_key="mock_key")
        self.assertEqual(count_session_chunks(self.session_id), 1)

    @patch("pipeline.domain.rag.nodes.project_db.get_google_embeddings")
    def test_batch_upsert_and_query(self, mock_embed):
        """배치 업서트 및 검색 테스트 (MOCK 임베딩)"""
        mock_embed.return_value = [0.1] * 3072
        
        vectors = [[0.1 * i] * 3072 for i in range(len(self.test_chunks))]
        upsert_code_chunks_batch(self.session_id, self.test_chunks, vectors)
        
        self.assertEqual(count_session_chunks(self.session_id), 5)
        
        results = query_project_code("test", session_id=self.session_id, n_results=3, api_key="mock_key")
        self.assertLessEqual(len(results), 3)

if __name__ == "__main__":
    unittest.main()
