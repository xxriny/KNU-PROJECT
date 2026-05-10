import unittest
import os
import sys
from collections import Counter

# Path setup
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_root = os.path.abspath(os.path.join(current_dir, "..", "..", "..", ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from pipeline.domain.rag.nodes.code_chunker import code_chunker_node
from pipeline.core.state import PipelineState

class TestDuplicates(unittest.TestCase):
    def test_find_duplicates_in_project(self):
        """실제 프로젝트 폴더를 스캔하여 중복된 chunk_id가 발생하는지 확인합니다."""
        project_root = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "..", ".."))
        
        state = {
            "source_dir": project_root,
            "run_id": "test_run",
            "action_type": "UPDATE"
        }
        
        result = code_chunker_node(state)
        chunks = result.get("rag_chunks", [])
        
        ids = [c["chunk_id"] for c in chunks]
        counts = Counter(ids)
        duplicates = [item for item, count in counts.items() if count > 1]
        
        if duplicates:
            print(f"\n[ERROR] Found {len(duplicates)} duplicate chunk_ids:")
            for d in duplicates[:10]:
                duplicate_chunks = [c for c in chunks if c["chunk_id"] == d]
                print(f"  ID: {d}")
                for c in duplicate_chunks:
                    print(f"    File: {c['file_path']}, Func: {c['func_name']}")
            
            self.fail(f"중복된 chunk_id가 {len(duplicates)}개 발견되었습니다.")
        else:
            print(f"\n[OK] No duplicate chunk_ids found in {len(chunks)} chunks.")

if __name__ == "__main__":
    unittest.main()
