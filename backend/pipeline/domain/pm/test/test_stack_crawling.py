import os
import sys
import json
from dotenv import load_dotenv

# 프로젝트 루트(backend)를 검색 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from pipeline.domain.pm.nodes.stack_crawling import stack_crawling_node

load_dotenv()

def debug_stack():
    # 1. 테스트 입력 (NPM 및 GitHub 예시)
    # 테스트하고 싶은 쿼리를 변경해 보세요.
    test_cases = [
        {"target": "npm", "query": "zustand"},
        {"target": "github", "query": "pmndrs/zustand"},
        {"target": "pypi", "query": "httpx"}
    ]

    for case in test_cases:
        state = {
            "stack_crawler_input": case,
            "thinking_log": []
        }

        print(f"\n {case['query']} ({case['target']}) 정보 수집 시작...")
        
        # 2. 노드 직접 실행 (실제 API 호출)
        result = stack_crawling_node(state)
        output = result.get("stack_crawler_output", {})

        # 3. 결과 출력
        if output.get("status") == "Pass":
            print(f" 수집 성공 (결과 {len(output.get('results', []))}건)")
            for res in output.get("results", []):
                print(f"  - [{res['name']}] v{res['version']} | {res['license']} | {res['stars']} stars")
                print(f"    * 설명: {res['description'][:60]}...")
                print(f"    * URL: {res['url']}")
        else:
            print(f" 수집 실패: {output.get('error_message')}")

if __name__ == "__main__":
    debug_stack()
