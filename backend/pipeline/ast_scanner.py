"""
pipeline/ast_scanner.py — 소스코드 AST 스캐너

Python 표준 ast 모듈과 정규식으로 소스코드 함수 목록을 추출한다.
외부 의존성 없음. source_dir이 비어 있거나 파싱 실패 시 빈 리스트로 Graceful degrade.
"""

import ast
import os
import re
import pathlib
from typing import Optional

# 스캔 대상 확장자
_PYTHON_EXTS = {".py"}
_JS_EXTS = {".js", ".jsx", ".ts", ".tsx"}

# 단일 파일 최대 크기 (5MB 초과 시 스킵)
_MAX_FILE_BYTES = 5 * 1024 * 1024

# 무시할 디렉터리 패턴
_SKIP_DIRS = {
    "__pycache__", "node_modules", ".git", ".venv", "venv",
    "dist", "build", ".pytest_cache", "coverage",
}


def _should_skip_dir(dirname: str) -> bool:
    return dirname in _SKIP_DIRS or dirname.startswith(".")


# ─────────────────────────────────────────────────────────────
# Python AST 파서
# ─────────────────────────────────────────────────────────────

def _parse_python_file(filepath: pathlib.Path, root: pathlib.Path) -> list[dict]:
    """단일 .py 파일에서 함수/메서드 목록 추출"""
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    rel_path = str(filepath.relative_to(root)).replace("\\", "/")
    results = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            docstring = ast.get_docstring(node) or ""
            decorators = []
            for d in node.decorator_list:
                if isinstance(d, ast.Name):
                    decorators.append(d.id)
                elif isinstance(d, ast.Attribute):
                    decorators.append(d.attr)

            results.append({
                "file": rel_path,
                "func_name": node.name,
                "lineno": node.lineno,
                "docstring": docstring[:200],   # 200자 제한 (토큰 절약)
                "decorators": decorators,
                "lang": "python",
            })

    return results


# ─────────────────────────────────────────────────────────────
# JS/TS 정규식 파서
# ─────────────────────────────────────────────────────────────

# 매칭 패턴:
#   function myFunc(      → 일반 함수 선언
#   async function myFunc(
#   const myFunc = (      → 화살표 함수
#   const myFunc = async (
#   myMethod(             → 클래스 메서드 (들여쓰기 있는 경우)
_JS_FUNC_RE = re.compile(
    r"^[\s]*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)\s*\("
    r"|^[\s]*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(",
    re.MULTILINE,
)


def _parse_js_file(filepath: pathlib.Path, root: pathlib.Path) -> list[dict]:
    """단일 JS/TS/JSX/TSX 파일에서 함수 목록 추출"""
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    rel_path = str(filepath.relative_to(root)).replace("\\", "/")
    results = []

    for lineno, line in enumerate(source.splitlines(), start=1):
        m = _JS_FUNC_RE.match(line)
        if m:
            func_name = m.group(1) or m.group(2)
            if func_name:
                results.append({
                    "file": rel_path,
                    "func_name": func_name,
                    "lineno": lineno,
                    "docstring": "",
                    "decorators": [],
                    "lang": "javascript",
                })

    return results


# ─────────────────────────────────────────────────────────────
# 공개 API
# ─────────────────────────────────────────────────────────────

def extract_functions(source_dir: str, max_functions: int = 300) -> list[dict]:
    """
    source_dir 하위의 모든 Python/JS/TS 파일에서 함수 목록 추출.

    Args:
        source_dir: 스캔할 루트 디렉터리 절대 경로
        max_functions: 반환할 최대 함수 개수 (토큰 폭발 방지)

    Returns:
        [{"file": "...", "func_name": "...", "lineno": int, "docstring": "...", "lang": "..."}]
        source_dir가 비어 있거나 존재하지 않으면 [] 반환.
    """
    if not source_dir:
        return []

    root = pathlib.Path(source_dir)
    if not root.is_dir():
        return []

    results: list[dict] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # 무시할 디렉터리 제거 (os.walk in-place 수정으로 하위 탐색 차단)
        dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]

        for filename in filenames:
            filepath = pathlib.Path(dirpath) / filename
            suffix = filepath.suffix.lower()

            # 파일 크기 체크
            try:
                if filepath.stat().st_size > _MAX_FILE_BYTES:
                    continue
            except OSError:
                continue

            if suffix in _PYTHON_EXTS:
                results.extend(_parse_python_file(filepath, root))
            elif suffix in _JS_EXTS:
                results.extend(_parse_js_file(filepath, root))

            if len(results) >= max_functions:
                return results[:max_functions]

    return results[:max_functions]


def summarize_for_llm(functions: list[dict], max_chars: int = 8000) -> str:
    """
    함수 목록을 LLM 프롬프트용 간결한 문자열로 변환.

    형식: file:func_name:lineno[:docstring 50자]
    """
    lines = []
    for fn in functions:
        doc_snippet = fn.get("docstring", "")[:50].replace("\n", " ")
        entry = f"{fn['file']}:{fn['func_name']}:L{fn['lineno']}"
        if doc_snippet:
            entry += f" — {doc_snippet}"
        lines.append(entry)

    result = "\n".join(lines)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n... (truncated)"
    return result
