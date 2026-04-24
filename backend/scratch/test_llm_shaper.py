import os
import json
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.append(str(Path(__file__).parent.parent))

from result_shaping.result_shaper import shape_result
from dotenv import load_dotenv

load_dotenv()

def test_shaper():
    print("🚀 LLM Result Shaper 테스트 시작...")

    # 1. 시뮬레이션된 Raw 데이터 (약어 및 불완전한 구조)
    raw_data = {
        "api_key": os.environ.get("GEMINI_API_KEY", ""),
        "run_id": "20260424_123456",
        "action_type": "UPDATE",
        "metadata": {
            "project_name": "스마트 팜 모니터링 시스템",
            "status": "In_Progress"
        },
        "pm_bundle": {
            "data": {
                "rtm": [
                    {"id": "REQ-001", "desc": "실시간 온습도 조회", "priority": "Must-have"},
                    {"id": "REQ-002", "desc": "관수 펌프 제어", "priority": "Should-have"}
                ],
                "stacks": [
                    {"n": "FastAPI", "v": "0.100.0", "st": "A"},
                    {"n": "PostgreSQL", "v": "15", "st": "PENDING"}
                ]
            }
        },
        "sa_output": {
            "data": {
                "apis": [
                    {"ep": "GET /sensors", "rq": {}, "rs": {"temp": "float", "humi": "float"}},
                    {"ep": "POST /actuators/pump", "rq": {"state": "bool"}, "rs": {"status": "ok"}}
                ],
                "tables": [
                    {"nm": "sensor_logs", "cl": "id:uuid,val:float,ts:timestamp"}
                ]
            },
            "recommendations": [
                {"priority": "High", "target": "Database", "action": "센서 데이터 파티셔닝 고려"}
            ]
        }
    }

    # 2. Shaper 호출
    try:
        shaped = shape_result(raw_data)
        
        print("\n✅ Shaping 완료!")
        print("-" * 50)
        print(f"프로젝트명: {shaped.get('project_name')}")
        print(f"요약: {shaped.get('summary')}")
        print(f"RTM 개수: {len(shaped.get('requirements_rtm', []))}")
        print(f"기술 스택: {json.dumps(shaped.get('tech_stacks', []), ensure_ascii=False, indent=2)}")
        print(f"API 목록 (변환 확인): {json.dumps(shaped.get('apis', []), ensure_ascii=False, indent=2)}")
        print(f"테이블 목록 (변환 확인): {json.dumps(shaped.get('tables', []), ensure_ascii=False, indent=2)}")
        print(f"권장사항: {json.dumps(shaped.get('recommendations', []), ensure_ascii=False, indent=2)}")
        print("-" * 50)
        
        # 핵심 필드 검증
        assert "endpoint" in shaped.get("apis", [{}])[0], "API 필드 'endpoint' 변환 실패"
        assert "table_name" in shaped.get("tables", [{}])[0], "Table 필드 'table_name' 변환 실패"
        print("🎉 모든 핵심 필드가 표준 스키마로 정상 변환되었습니다.")

    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_shaper()
