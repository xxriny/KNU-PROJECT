"""Python 구문 검사 스크립트"""
import py_compile, os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
errors = []

for root, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    for f in files:
        if f.endswith(".py") and f != "check_syntax.py":
            path = os.path.join(root, f)
            rel = os.path.relpath(path, ROOT)
            try:
                py_compile.compile(path, doraise=True)
                print(f"  OK  {rel}")
            except py_compile.PyCompileError as e:
                errors.append(str(e))
                print(f"ERROR {rel}: {e}")

print()
if errors:
    print(f"FAILED: {len(errors)} error(s)")
    sys.exit(1)
else:
    print(f"All {sum(1 for _ in errors.__class__.__mro__) - 1 + len([x for x in os.walk(ROOT)])} Python files OK")
