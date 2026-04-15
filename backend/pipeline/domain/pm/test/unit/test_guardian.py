import os
import sys
import json
from dotenv import load_dotenv

# ?„ë¡œ?íŠ¸ ë£¨íŠ¸(backend)ë¥?ê²€??ê²½ë¡œ??ì¶”ê?
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../.."))

from pipeline.domain.pm.nodes.guardian import guardian_node

load_dotenv()

def debug_guardian():
    api_key = os.getenv("GEMINI_API_KEY")
    
    # [Case 1] ?•ìƒ ë³‘í•© ë°??¹ì¸ ì¼€?´ìŠ¤ (zustand)
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

    # [Case 2] ?¼ì´? ìŠ¤ ê±°ì ˆ ì¼€?´ìŠ¤ (GPL)
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

    # [Case 3] ?€?´í¬?¤ì¿¼???˜ì‹¬ ì¼€?´ìŠ¤ (reackt)
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
        ("?•ìƒ ë³‘í•© ë°??¹ì¸ (NPM+GitHub)", state_normal),
        ("?¼ì´? ìŠ¤ ê±°ì ˆ (GPL)", state_rejected_license),
        ("?€?´í¬?¤ì¿¼???˜ì‹¬ (reackt)", state_typo)
    ]

    for title, state in test_cases:
        print(f"\n?? [?ŒìŠ¤?? {title} ?œì‘...")
        result = guardian_node(state)
        output = result.get("guardian_output", {})
        
        status = output.get("status")
        color = "?? if status == "APPROVED" else "??
        
        print(f"{color} ?íƒœ: {status}")
        if status == "REJECTED":
            print(f"??ê±°ì ˆ ?¬ìœ : {output.get('rejection_reason')}")
        
        print(f"?§  ë¶„ì„ ?¬ê³ ê³¼ì •: {output.get('thinking')}")
        
        if status == "APPROVED" and output.get("final_data"):
            data = output["final_data"]
            print(f"?“¦ ìµœì¢… ?°ì´?? {data['name']} (v{data['version']}, {data['stars']} stars, {data['license']})")
        
        # print(json.dumps(output, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    debug_guardian()
