import os
import sys
import json
from dotenv import load_dotenv

# 프로젝트 루트(backend)를 검색 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from pipeline.domain.pm.nodes.stack_planner import stack_planner_node

load_dotenv()

def debug_stack_planner():
    api_key = os.getenv("GEMINI_API_KEY")
    
    # [1] 가상의 분석 결과 (Features)
    mock_features = [
        {
            "id": "FEAT_001",
            "description": "사용자 회원가입 및 로그인 대시보드",
            "priority": "Must-Have",
            "test_criteria": "로그인 후 메인 화면 진입 여부"
        },
        {
            "id": "FEAT_002",
            "description": "실시간 데이터 시각화 차트",
            "priority": "Should-Have",
            "test_criteria": "데이터 업데이트 시 차트 렌더링 확인"
        },
        {
            "id": "FEAT_003",
            "description": "초고속 이미지 압축 서빙 로직",
            "priority": "Could-Have",
            "test_criteria": "이미지 사이즈 50% 이상 감소 확인"
        }
    ]

    # [2] 가상의 RAG 컨텍스트 (승인된 스택 목록)
    # FEAT_003(이미지 압축)에 대한 적절한 스택이 없는 상황을 가정함
    mock_rag_context = """
    - Frontend: React 18, Zustand (State Management), Tailwind CSS
    - Backend: FastAPI (Python), PostgreSQL, SQLAlchemy
    - Infrastructure: Docker, AWS EC2
    """

    state = {
        "api_key": api_key,
        "requirement_analyzer_output": {
            "features": mock_features
        },
        "stack_rag_context": mock_rag_context,
        "thinking_log": []
    }

    print("\n🚀 [1] Stack Planner 분석 및 매핑 시작...")
    
    # 노드 직접 실행
    result = stack_planner_node(state)
    output = result.get("stack_planner_output", {})

    # [3] 결과 출력
    print("\n🧠 [2] 에이전트 설계 사고 과정 (Thinking):")
    print(output.get("thinking", "No thinking found."))

    print("\n📦 [3] 최종 기술 스택 매핑 결과:")
    mapping = output.get("stack_mapping", [])
    for m in mapping:
        status_icon = "✅" if m["status"] == "APPROVED" else "🔍"
        print(f" {status_icon} [{m['feature_id']}] {m['domain']} : {m['package']}")
        print(f"    - 상태: {m['status']}")
        print(f"    - 근거: {m['reason']}")
    
    # 전체 JSON 확인
    # print(json.dumps(output, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    debug_stack_planner()
