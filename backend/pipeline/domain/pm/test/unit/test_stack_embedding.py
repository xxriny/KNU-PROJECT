import os
import sys
import json
import numpy as np
from dotenv import load_dotenv

# ?„ë¡œ?íŠ¸ ë£¨íŠ¸(backend)ë¥?ê²€??ê²½ë¡œ??ì¶”ê?
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../.."))

from pipeline.domain.pm.nodes.stack_embedding import stack_embedding_node, get_embedding_model

load_dotenv()

def debug_embedding():
    print("\n?? [1] ëª¨ë¸ ë¡œë”© ?ŒìŠ¤??(ìµœì´ˆ ?¤í–‰ ??ëª¨ë¸ ?¤ìš´ë¡œë“œë¡???ë¶„ì´ ?Œìš”?????ˆìŠµ?ˆë‹¤...)")
    try:
        model = get_embedding_model()
        print(f"??ëª¨ë¸ ë¡œë“œ ?„ë£Œ!")
    except Exception as e:
        print(f"??ëª¨ë¸ ë¡œë“œ ?¤íŒ¨: {e}")
        return

    # [Case 1] ?•ìƒ ?¹ì¸ ?°ì´???„ë² ??    state = {
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

    print("\n?? [2] Stack Embedding ?¸ë“œ ?¤í–‰...")
    result = stack_embedding_node(state)
    output = result.get("stack_embedding_output", {})

    if output.get("vector"):
        vector = output["vector"]
        print(f"???„ë² ???±ê³µ!")
        print(f" - ?€???ìŠ¤?? {output['text_embedded']}")
        print(f" - ë²¡í„° ì°¨ì›: {len(vector)}")
        print(f" - ë²¡í„° ?˜í”Œ (??5ê°?: {vector[:5]}")
    else:
        print(f"???„ë² ???¤íŒ¨: {output.get('thinking')}")

    # [Case 3] ? ì‚¬???ŒìŠ¤??(?¬ìš©?ê? ?œì‹œ???ˆì‹œ ?‘ìš©)
    print("\n?? [3] ? ì‚¬??Similarity) ?ŒìŠ¤??..")
    sentences = [
        "zustand: Bear necessities for state management",
        "redux: A Predictable State Container for JS Apps",
        "fastapi: High performance, easy to learn, fast to code, ready for production",
        "The weather is lovely today."
    ]
    
    embeddings = model.encode(sentences)
    
    # Cosine Similarity ê³„ì‚°
    def cosine_similarity(a, b):
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    print(f" - ê¸°ì?: '{sentences[0]}'")
    for i in range(1, len(sentences)):
        sim = cosine_similarity(embeddings[0], embeddings[i])
        print(f"   vs '{sentences[i]}': {sim:.4f}")

if __name__ == "__main__":
    debug_embedding()
