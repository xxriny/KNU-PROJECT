import os
import sys
import json
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔 코드페이지(cp949)에서 이모지/한글 출력 시 크래시 방지

# 프로젝트 루트(backend)를 검색 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../.."))

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
            "test_criteria": "로그인 후 메인 화면 진입 확인"
        },
        {
            "id": "FEAT_002",
            "description": "실시간 데이터 시각화 차트",
            "priority": "Should-Have",
            "test_criteria": "데이터 업데이트 후 차트 렌더링 확인"
        },
        {
            "id": "FEAT_003",
            "description": "초고화질 이미지 압축 캐싱 로직",
            "priority": "Could-Have",
            "test_criteria": "이미지 용량 50% 이상 감소 확인"
        }
    ]

    # state["features"]는 stack_planner_node가 직접 읽는 최상위 키다
    # (예전엔 requirement_analyzer_output.features를 감쌌지만 현재 노드 시그니처와는 다름).
    state = {
        "api_key": api_key,
        "features": mock_features,
        "action_type": "CREATE",
        "loop_count": 0,
        "thinking_log": []
    }

    print("\n🔧 [1] Stack Planner 분석 및 매핑 시작...")

    # 노드 직접 실행
    result = stack_planner_node(state)
    output = result.get("stack_planner_output", {})

    # [2] 결과 출력 — StackPlannerOutput 스키마: th(thinking) / m(stack_mapping) / gs(global_stacks)
    print("\n💭 [2] 에이전트 설계 사고 과정 (Thinking):")
    print(output.get("th", "No thinking found."))

    print("\n📋 [3] 최종 기술 스택 매핑 결과:")
    mapping = output.get("m", [])
    for item in mapping:
        status_icon = "✅" if item["status"] == "APPROVED" else "⏳"
        print(f" {status_icon} [{item['f_id']}] {item['dom']} : {item['pkg']}")
        print(f"    - 상태: {item['status']}")
        print(f"    - 근거: {item['reason']}")

    print("\n🌐 [4] 전역 기술 스택 목록 (Global Stacks):")
    for gs_item in output.get("gs", []):
        print(f"  - {gs_item['name']} {gs_item.get('version', '')} ({gs_item.get('domain', '')})")

    # 전체 JSON 확인
    # print(json.dumps(output, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    debug_stack_planner()
