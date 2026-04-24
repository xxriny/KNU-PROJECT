import json
import os
import sys
from unittest.mock import MagicMock, patch

# ?꾨줈?앺듃 猷⑦듃 諛?backend 寃쎈줈 ?먮룞 異붽?
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.abspath(os.path.join(current_dir, "../../../../../"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from pipeline.domain.sa.nodes.sa_embedding import sa_embedding_node

def run_experiment():
    # 1. ?쒕굹由ъ삤 ?ㅼ젙
    state = {
        "sa_arch_bundle": {"phase": "SA", "data": {"components": [{"name": "AuthUI"}]}},
        "run_id": "exp_session", "thinking_log": []
    }

    with patch("pipeline.domain.sa.nodes.sa_embedding.get_pm_embeddings", return_value=[0.1, 0.2]), \
         patch("pipeline.domain.sa.nodes.sa_embedding.upsert_sa_artifact"):
        
        # 2. ?몃뱶 ?ㅽ뻾
        result = sa_embedding_node(state)
        
        # 3. 寃곌낵 異쒕젰
        print("\n" + "="*60)
        print(" [SA EXPERIMENT] sa_embedding (RAG Storage)")
        print("="*60)
        print(f"??濡쒓렇: {result['thinking_log'][-1]['thinking']}")
        print("-" * 60)
        print(json.dumps(result["thinking_log"], indent=2, ensure_ascii=False))
        print("="*60 + "\n")

if __name__ == "__main__":
    run_experiment()
