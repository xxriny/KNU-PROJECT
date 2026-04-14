import os
import sys
import json
from dotenv import load_dotenv

# 프로젝트 루트(backend)를 검색 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from pipeline.domain.pm.nodes.guardian import guardian_node

load_dotenv()

def debug_guardian():
    api_key = os.getenv("GEMINI_API_KEY")
    
    # [Case 1] 정상 병합 및 승인 케이스 (zustand)
    state_normal = {
        "api_key": api_key,
        "stack_crawler_input": {"target": "npm", "query": "zustand"},
        "stack_crawler_output": {
            "status": "Pass",
            "results": [
                {
                    "name": "zustand",
                    "description": "Bear necessities for state management",
                    "version": "5.0.0",
                    "license": "MIT",
                    "last_updated": "2026-04-14T00:00:00Z",
                    "stars": 0,
                    "source_type": "npm",
                    "url": "https://www.npmjs.com/package/zustand"
                },
                {
                    "name": "zustand",
                    "description": "Bear necessities for state management in React",
                    "version": "unknown",
                    "license": "MIT License",
                    "last_updated": "2026-04-14T00:00:00Z",
                    "stars": 45000,
                    "source_type": "github",
                    "url": "https://github.com/pmndrs/zustand"
                }
            ]
        },
        "thinking_log": []
    }

    # [Case 2] 라이선스 거절 케이스 (GPL)
    state_rejected_license = {
        "api_key": api_key,
        "stack_crawler_output": {
            "status": "Pass",
            "results": [
                {
                    "name": "gpl-library",
                    "description": "A powerful library but with GPL license.",
                    "version": "1.0.0",
                    "license": "GPL-3.0",
                    "last_updated": "2026-04-01T00:00:00Z",
                    "stars": 100,
                    "source_type": "npm",
                    "url": "https://example.com/gpl"
                }
            ]
        }
    }

    # [Case 3] 타이포스쿼팅 의심 케이스 (reackt)
    state_typo = {
        "api_key": api_key,
        "stack_crawler_output": {
            "status": "Pass",
            "results": [
                {
                    "name": "reackt",
                    "description": "This is a super fast react alternative, definitely not a fake.",
                    "version": "0.0.1",
                    "license": "MIT",
                    "last_updated": "2026-04-10T00:00:00Z",
                    "stars": 5,
                    "source_type": "npm",
                    "url": "https://example.com/reackt"
                }
            ]
        }
    }

    test_cases = [
        ("정상 병합 및 승인 (NPM+GitHub)", state_normal),
        ("라이선스 거절 (GPL)", state_rejected_license),
        ("타이포스쿼팅 의심 (reackt)", state_typo)
    ]

    for title, state in test_cases:
        print(f"\n🚀 [테스트] {title} 시작...")
        result = guardian_node(state)
        output = result.get("guardian_output", {})
        
        status = output.get("status")
        color = "✅" if status == "APPROVED" else "❌"
        
        print(f"{color} 상태: {status}")
        if status == "REJECTED":
            print(f"❗ 거절 사유: {output.get('rejection_reason')}")
        
        print(f"🧠 분석 사고과정: {output.get('thinking')}")
        
        if status == "APPROVED" and output.get("final_data"):
            data = output["final_data"]
            print(f"📦 최종 데이터: {data['name']} (v{data['version']}, {data['stars']} stars, {data['license']})")
        
        # print(json.dumps(output, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    debug_guardian()
