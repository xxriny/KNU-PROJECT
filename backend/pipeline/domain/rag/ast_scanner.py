"""
pipeline/ast_scanner.py — 소스코드 AST 스캐너(수정)

Python 표준 ast 모듈과 정규식으로 소스코드 함수 목록을 추출한다.
외부 의존성 없음. source_dir이 비어 있거나 파싱 실패 시 빈 리스트로 Graceful degrade.
"""

import ast
import os
import re
import pathlib
from collections import defaultdict
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

_JS_IMPORT_RE = re.compile(
    r"(?:import\s+(?:[^\"']+?\s+from\s+)?|require\()\s*[\"']([^\"']+)[\"']"
)


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


def _collect_python_imports(filepath: pathlib.Path) -> list[str]:
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
    except (OSError, SyntaxError):
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name:
                    imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * int(getattr(node, "level", 0) or 0)
            module = node.module or ""
            if module:
                imports.append(f"{prefix}{module}")
            for alias in node.names:
                if alias.name == "*":
                    continue
                if module:
                    imports.append(f"{prefix}{module}.{alias.name}")
                else:
                    imports.append(f"{prefix}{alias.name}")

    return list(dict.fromkeys(imports))


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


def _collect_js_imports(filepath: pathlib.Path) -> list[str]:
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    imports = [match.group(1) for match in _JS_IMPORT_RE.finditer(source) if match.group(1)]
    return list(dict.fromkeys(imports))


def _enumerate_source_files(root: pathlib.Path) -> list[pathlib.Path]:
    files: list[pathlib.Path] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]

        for filename in filenames:
            filepath = pathlib.Path(dirpath) / filename
            suffix = filepath.suffix.lower()
            if suffix not in (_PYTHON_EXTS | _JS_EXTS):
                continue

            try:
                if filepath.stat().st_size > _MAX_FILE_BYTES:
                    continue
            except OSError:
                continue

            files.append(filepath)

    return files


def _language_for_suffix(suffix: str) -> str:
    if suffix.lower() in _PYTHON_EXTS:
        return "python"
    if suffix.lower() in _JS_EXTS:
        return "javascript"
    return "unknown"


def _entrypoint_hint(rel_path: str) -> bool:
    normalized = rel_path.lower()
    return normalized.endswith("/main.py") or normalized.endswith("/main.jsx") or normalized.endswith("/main.tsx") or normalized.endswith("/index.js")


def _candidate_paths_for_python_import(raw_import: str, rel_path: str) -> list[str]:
    normalized = (raw_import or "").strip()
    if not normalized:
        return []

    current = pathlib.PurePosixPath(rel_path)
    current_dir = pathlib.PurePosixPath(*current.parts[:-1])
    current_top = current.parts[0] if len(current.parts) > 1 else ""

    leading = len(normalized) - len(normalized.lstrip("."))
    module = normalized.lstrip(".")
    module_path = module.replace(".", "/") if module else ""
    candidates: list[str] = []

    def add_candidate(base: pathlib.PurePosixPath):
        if str(base) == ".":
            return
        candidates.append(f"{base.as_posix()}.py")
        candidates.append(f"{base.as_posix()}/__init__.py")

    if leading:
        base_parts = list(current_dir.parts)
        up_levels = max(leading - 1, 0)
        if up_levels:
            base_parts = base_parts[:-up_levels] if up_levels <= len(base_parts) else []
        base = pathlib.PurePosixPath(*base_parts) if base_parts else pathlib.PurePosixPath()
        target = base / module_path if module_path else base
        add_candidate(target)
    else:
        target = pathlib.PurePosixPath(module_path)
        add_candidate(target)
        if current_top:
            add_candidate(pathlib.PurePosixPath(current_top) / module_path)

    return list(dict.fromkeys(candidate for candidate in candidates if candidate and candidate != ".py"))


def _candidate_paths_for_js_import(raw_import: str, rel_path: str) -> list[str]:
    normalized = (raw_import or "").strip()
    if not normalized or not normalized.startswith("."):
        return []

    current = pathlib.PurePosixPath(rel_path)
    current_dir = pathlib.PurePosixPath(*current.parts[:-1])
    target = pathlib.PurePosixPath(current_dir, normalized)
    target_str = target.as_posix()

    candidates = []
    for ext in (".js", ".jsx", ".ts", ".tsx"):
        candidates.append(f"{target_str}{ext}")
        candidates.append(f"{target_str}/index{ext}")

    return list(dict.fromkeys(candidates))


def _resolve_internal_imports(rel_path: str, lang: str, raw_imports: list[str], known_paths: set[str]) -> list[str]:
    resolved: list[str] = []

    for raw_import in raw_imports:
        if lang == "python":
            candidates = _candidate_paths_for_python_import(raw_import, rel_path)
        else:
            candidates = _candidate_paths_for_js_import(raw_import, rel_path)

        for candidate in candidates:
            normalized = candidate.replace("\\", "/")
            if normalized in known_paths and normalized not in resolved and normalized != rel_path:
                resolved.append(normalized)
                break

    return resolved


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


def extract_file_inventory(source_dir: str, max_files: int = 600) -> list[dict]:
    """소스 파일 인벤토리와 내부 import 관계를 반환한다."""
    if not source_dir:
        return []

    root = pathlib.Path(source_dir)
    if not root.is_dir():
        return []

    source_files = _enumerate_source_files(root)
    known_paths = {
        str(filepath.relative_to(root)).replace("\\", "/")
        for filepath in source_files
    }

    inventory: list[dict] = []
    for filepath in source_files[:max_files]:
        rel_path = str(filepath.relative_to(root)).replace("\\", "/")
        lang = _language_for_suffix(filepath.suffix)

        if lang == "python":
            functions = _parse_python_file(filepath, root)
            raw_imports = _collect_python_imports(filepath)
        else:
            functions = _parse_js_file(filepath, root)
            raw_imports = _collect_js_imports(filepath)

        inventory.append(
            {
                "file": rel_path,
                "lang": lang,
                "function_count": len(functions),
                "raw_imports": raw_imports,
                "internal_imports": _resolve_internal_imports(rel_path, lang, raw_imports, known_paths),
                "is_entrypoint": _entrypoint_hint(rel_path),
            }
        )

    inventory.sort(key=lambda item: (not item.get("is_entrypoint", False), item.get("file", "")))
    return inventory[:max_files]


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
