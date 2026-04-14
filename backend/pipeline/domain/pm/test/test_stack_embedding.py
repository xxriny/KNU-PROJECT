import os
import sys
import json
import numpy as np
from dotenv import load_dotenv

# 프로젝트 루트(backend)를 검색 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from pipeline.domain.pm.nodes.stack_embedding import stack_embedding_node, get_embedding_model

load_dotenv()

def debug_embedding():
    print("\n🚀 [1] 모델 로딩 테스트 (최초 실행 시 모델 다운로드로 수 분이 소요될 수 있습니다...)")
    try:
        model = get_embedding_model()
        print(f"✅ 모델 로드 완료!")
    except Exception as e:
        print(f"❌ 모델 로드 실패: {e}")
        return

    # [Case 1] 정상 승인 데이터 임베딩
    state = {
        "guardian_output": {
            "status": "APPROVED",
            "final_data": {
                "name": "zustand",
                "description": "Bear necessities for state management in React",
                "version": "5.0.0",
                "license": "MIT",
                "last_updated": "2026-04-14T00:00:00Z",
                "stars": 45000,
                "source_type": "merged",
                "url": "https://github.com/pmndrs/zustand"
            }
        },
        "thinking_log": []
    }

    print("\n🚀 [2] Stack Embedding 노드 실행...")
    result = stack_embedding_node(state)
    output = result.get("stack_embedding_output", {})

    if output.get("vector"):
        vector = output["vector"]
        print(f"✅ 임베딩 성공!")
        print(f" - 대상 텍스트: {output['text_embedded']}")
        print(f" - 벡터 차원: {len(vector)}")
        print(f" - 벡터 샘플 (앞 5개): {vector[:5]}")
    else:
        print(f"❌ 임베딩 실패: {output.get('thinking')}")

    # [Case 3] 유사성 테스트 (사용자가 제시한 예시 응용)
    print("\n🚀 [3] 유사성(Similarity) 테스트...")
    sentences = [
        "zustand: Bear necessities for state management",
        "redux: A Predictable State Container for JS Apps",
        "fastapi: High performance, easy to learn, fast to code, ready for production",
        "The weather is lovely today."
    ]
    
    embeddings = model.encode(sentences)
    
    # Cosine Similarity 계산
    def cosine_similarity(a, b):
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    print(f" - 기준: '{sentences[0]}'")
    for i in range(1, len(sentences)):
        sim = cosine_similarity(embeddings[0], embeddings[i])
        print(f"   vs '{sentences[i]}': {sim:.4f}")

if __name__ == "__main__":
    debug_embedding()
