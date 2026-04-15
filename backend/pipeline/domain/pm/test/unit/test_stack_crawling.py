import os
import sys
import json
from dotenv import load_dotenv

# ?„ë¡œ?íŠ¸ ë£¨íŠ¸(backend)ë¥?ê²€??ê²½ë¡œ??ì¶”ê?
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../.."))

from pipeline.domain.pm.nodes.stack_crawling import stack_crawling_node

load_dotenv()

def debug_stack():
    # 1. ?ŒìŠ¤???…ë ¥ (NPM ë°?GitHub ?ˆì‹œ)
    # ?ŒìŠ¤?¸í•˜ê³??¶ì? ì¿¼ë¦¬ë¥?ë³€ê²½í•´ ë³´ì„¸??
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

        print(f"\n {case['query']} ({case['target']}) ?•ë³´ ?˜ì§‘ ?œì‘...")
        
        # 2. ?¸ë“œ ì§ì ‘ ?¤í–‰ (?¤ì œ API ?¸ì¶œ)
        result = stack_crawling_node(state)
        output = result.get("stack_crawler_output", {})

        # 3. ê²°ê³¼ ì¶œë ¥
        if output.get("status") == "Pass":
            print(f" ?˜ì§‘ ?±ê³µ (ê²°ê³¼ {len(output.get('results', []))}ê±?")
            for res in output.get("results", []):
                print(f"  - [{res['name']}] v{res['version']} | {res['license']} | {res['stars']} stars")
                print(f"    * ?¤ëª…: {res['description'][:60]}...")
                print(f"    * URL: {res['url']}")
        else:
            print(f" ?˜ì§‘ ?¤íŒ¨: {output.get('error_message')}")

if __name__ == "__main__":
    debug_stack()
