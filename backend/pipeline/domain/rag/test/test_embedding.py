import unittest
import os
from pipeline.core.models.google_embed_model import get_google_embeddings, get_google_embeddings_batch

class TestGoogleEmbedding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 환경변수에서 API 키 로드
        cls.api_key = os.environ.get("GEMINI_API_KEY", "")
        if not cls.api_key:
            print("\n[SKIP] GEMINI_API_KEY가 설정되지 않아 임베딩 테스트를 건너뜁니다.")

    def test_single_embedding(self):
        """단일 텍스트 임베딩 생성 테스트 (동적 API 호출)"""
        if not self.api_key:
            self.skipTest("No API Key")
            
        text = "테스트 임베딩 문장입니다."
        vector = get_google_embeddings(text, api_key=self.api_key)
        
        self.assertIsInstance(vector, list)
        self.assertEqual(len(vector), 3072) # gemini-embedding-2 default dim
        self.assertIsInstance(vector[0], float)

    def test_batch_embedding(self):
        """배치 텍스트 임베딩 생성 테스트 (동적 API 호출 및 배치 분할 로직 검증)"""
        if not self.api_key:
            self.skipTest("No API Key")
            
        # 105개 문장으로 배치 분할 로직(MAX_BATCH_SIZE=100) 테스트
        texts = [f"문장 {i}" for i in range(105)]
        vectors = get_google_embeddings_batch(texts, api_key=self.api_key)
        
        self.assertEqual(len(vectors), 105)
        self.assertEqual(len(vectors[0]), 3072)

if __name__ == "__main__":
    unittest.main()
