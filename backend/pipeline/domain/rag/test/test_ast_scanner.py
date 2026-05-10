import unittest
import os
import sys
import tempfile

# Path setup
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_root = os.path.abspath(os.path.join(current_dir, "..", "..", "..", ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from pipeline.domain.rag.ast_scanner import extract_functions

class TestASTScanner(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.py_file = os.path.join(self.test_dir.name, "sample.py")
        
        with open(self.py_file, "w", encoding="utf-8") as f:
            f.write("def hello():\n    print('world')\n\nclass MyClass:\n    def method(self):\n        pass")

    def tearDown(self):
        self.test_dir.cleanup()

    def test_extract_python_functions(self):
        """Python 파일에서 함수 및 메서드 추출 테스트 (정적 분석)"""
        results = extract_functions(self.test_dir.name)
        py_funcs = [r for r in results if r['lang'] == 'python']
        
        func_names = {r['func_name'] for r in py_funcs}
        self.assertIn("hello", func_names)
        self.assertIn("method", func_names)
        
    def test_extract_full_project(self):
        """NAVIGATOR 전체 프로젝트 폴더 스캔 테스트 (실제 코드베이스 대상)"""
        # test -> rag -> domain -> pipeline -> backend -> NAVIGATOR (5단계)
        project_root = os.path.abspath(os.path.join(current_dir, "..", "..", "..", "..", ".."))
        
        results = extract_functions(project_root, max_functions=1000)
        
        self.assertGreater(len(results), 0, "프로젝트에서 함수를 하나도 찾지 못했습니다.")
        
        # 특정 핵심 파일들이 포함되었는지 확인
        files = {r['file'].replace("\\", "/") for r in results}
        self.assertTrue(any("backend/main.py" in f for f in files), "backend/main.py가 스캔되지 않았습니다.")
        
        print(f"\n[INFO] Full project scan found {len(results)} functions/methods.")

if __name__ == "__main__":
    unittest.main()
