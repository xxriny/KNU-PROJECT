import os
import sys
import json
from dotenv import load_dotenv

# 현재 파일 위치를 기준으로 프로젝트 루트(backend)를 검색 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from pipeline.domain.pm.nodes.requirement_analyzer import requirement_analyzer_node

load_dotenv()

def debug_analyzer():
    # 1. 초기 상태 설정
    state = {
        "api_key": os.getenv("GEMINI_API_KEY"),
        "input_idea": "회원가입 기능이랑 로그인 기능 만들어줘. 소셜 로그인도 포함해서.",
        "action_type": "CREATE",
        "thinking_log": []
    }

    print("\n[1] AI 분석 시작 중...")
    
    # 2. 노드 직접 실행 (실제 LLM 호출)
    result = requirement_analyzer_node(state)

    if "error" in result:
        print(f"❌ 에러 발생: {result['error']}")
        return

    # 3. 결과 출력
    print("\n[2] AI 사고 과정 (Thinking):")
    for log in result.get("thinking_log", []):
        print(f" > {log['thinking']}")

    print("\n[3] 추출된 원자 요구사항 (Features):")
    features = result.get("features", [])
    for f in features:
        print(f" - [{f['id']}] {f['description']} ({f['priority']})")
        print(f"   * 검증 기준: {f['test_criteria']}")

    # 전체 JSON이 보고 싶다면
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    debug_analyzer()
