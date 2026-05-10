import unittest
import sys
import os

# 프로젝트 루트 및 backend 폴더를 path에 추가하여 import 가능하게 함
current_dir = os.path.dirname(os.path.abspath(__file__))
# backend 폴더 위치: .../NAVIGATOR/backend (test -> rag -> domain -> pipeline -> backend)
backend_root = os.path.abspath(os.path.join(current_dir, "..", "..", "..", ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

def run_all_tests():
    print("=== NAVIGATOR RAG Subsystem Testing ===")
    loader = unittest.TestLoader()
    suite = loader.discover(current_dir, pattern="test_*.py")
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if not result.wasSuccessful():
        sys.exit(1)

if __name__ == "__main__":
    run_all_tests()
