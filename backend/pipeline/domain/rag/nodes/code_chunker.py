"""
Code Chunker Node
소스 디렉터리를 순회하며 함수/클래스 단위 코드 청크를 추출합니다.
- Python  : ast.get_source_segment() 기반 정확한 본문 추출
- JS/TS   : 함수 시작 라인 감지 후 라인 범위 슬라이싱
- 기타     : 1500자 슬라이딩 윈도우 (코드 파일에 한함)
"""

import ast
import hashlib
import os
import re
from typing import Any, Dict, List

from pipeline.core.state import PipelineState, make_sget
from pipeline.domain.rag.schemas import CodeChunk
from observability.logger import get_logger

logger = get_logger()

# ── 설정 ────────────────────────────────────────────────────
_MAX_CHUNK_CHARS = 6000
_WINDOW_SIZE = 1500
_WINDOW_OVERLAP = 300
_MAX_JS_FUNC_LINES = 100

_IGNORE_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", ".cache",
    ".idea", ".vscode", "storage",
}

_PYTHON_EXTS = {".py"}
_JS_EXTS = {".js", ".jsx", ".ts", ".tsx"}
_OTHER_CODE_EXTS = {".java", ".go", ".rs", ".c", ".cpp", ".rb", ".kt", ".swift"}

# JS/TS 최상위 함수·클래스·화살표 함수 탐지 정규식
_JS_FUNC_RE = re.compile(
    r"^[ \t]*(?:export\s+)?(?:default\s+)?(?:async\s+)?"
    r"(?:function\s+\w+|class\s+\w+|(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?(?:function|\())",
    re.MULTILINE,
)


# ── 헬퍼 ────────────────────────────────────────────────────

def _chunk_id(session_id: str, file_path: str, func_name: str) -> str:
    file_hash = hashlib.md5(file_path.encode()).hexdigest()[:8]
    safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", func_name)[:40]
    return f"{session_id}_{file_hash}_{safe_name}"


def _window_chunks(
    source: str, file_path: str, session_id: str, version: str, lang: str
) -> List[CodeChunk]:
    chunks, i, n = [], 0, 0
    while i < len(source):
        body = source[i : i + _WINDOW_SIZE]
        if not body.strip():
            break
        chunks.append(CodeChunk(
            chunk_id=_chunk_id(session_id, file_path, f"FILE_CHUNK_{n}"),
            session_id=session_id,
            version=version,
            file_path=file_path,
            func_name=f"FILE_CHUNK_{n}",
            content_text=body,
            lang=lang,
        ))
        i += _WINDOW_SIZE - _WINDOW_OVERLAP
        n += 1
    return chunks


def _extract_python(source: str, file_path: str, session_id: str, version: str) -> List[CodeChunk]:
    chunks = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return _window_chunks(source, file_path, session_id, version, "python")

    # ClassDef 내부 FunctionDef는 ClassDef 청크에 포함되므로 최상위만 추출
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = ast.get_source_segment(source, node)
        if not body:
            continue
        chunks.append(CodeChunk(
            chunk_id=_chunk_id(session_id, file_path, node.name),
            session_id=session_id,
            version=version,
            file_path=file_path,
            func_name=node.name,
            content_text=body[:_MAX_CHUNK_CHARS],
            lang="python",
        ))

    return chunks if chunks else _window_chunks(source, file_path, session_id, version, "python")


def _extract_js(source: str, file_path: str, session_id: str, version: str) -> List[CodeChunk]:
    lines = source.splitlines()
    matches = list(_JS_FUNC_RE.finditer(source))

    if not matches:
        return _window_chunks(source, file_path, session_id, version, "javascript")

    # 각 매치의 시작 라인 인덱스 계산 (0-indexed)
    start_lines = [source.count("\n", 0, m.start()) for m in matches]
    start_lines.append(len(lines))  # sentinel

    chunks = []
    for i, m in enumerate(matches):
        sl = start_lines[i]
        el = min(start_lines[i + 1], sl + _MAX_JS_FUNC_LINES)
        body = "\n".join(lines[sl:el])[:_MAX_CHUNK_CHARS]

        # 함수명 추출 (매치 텍스트에서)
        func_name = f"js_func_{i}"
        name_m = re.search(r"(?:function|class)\s+(\w+)|(?:const|let|var)\s+(\w+)", m.group())
        if name_m:
            func_name = name_m.group(1) or name_m.group(2) or func_name

        chunks.append(CodeChunk(
            chunk_id=_chunk_id(session_id, file_path, func_name),
            session_id=session_id,
            version=version,
            file_path=file_path,
            func_name=func_name,
            content_text=body,
            lang="javascript",
        ))

    return chunks


def _should_ignore(name: str) -> bool:
    return name in _IGNORE_DIRS or name.startswith(".")


def _process_file(
    full_path: str,
    rel_path: str,
    session_id: str,
    version: str,
) -> List[CodeChunk]:
    ext = os.path.splitext(full_path)[1].lower()
    lang = (
        "python" if ext in _PYTHON_EXTS
        else "javascript" if ext in _JS_EXTS
        else "unknown"
    )
    if ext not in (_PYTHON_EXTS | _JS_EXTS | _OTHER_CODE_EXTS):
        return []

    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read()
    except OSError:
        return []

    if not source.strip():
        return []

    if ext in _PYTHON_EXTS:
        return _extract_python(source, rel_path, session_id, version)
    if ext in _JS_EXTS:
        return _extract_js(source, rel_path, session_id, version)
    # 기타 코드 파일 — 슬라이딩 윈도우
    return _window_chunks(source, rel_path, session_id, version, lang)


# ── LangGraph 노드 ──────────────────────────────────────────

def code_chunker_node(state: PipelineState) -> Dict[str, Any]:
    sget = make_sget(state)
    source_dir = sget("source_dir", "")
    run_id = sget("run_id", "unknown")
    version = "v1.0"

    logger.info(f"[code_chunker] source_dir={source_dir!r}")

    if not source_dir or not os.path.isdir(source_dir):
        logger.warning("[code_chunker] source_dir이 유효하지 않아 청킹을 건너뜁니다.")
        return {
            "rag_chunks": [],
            "thinking_log": (sget("thinking_log", []) or []) + [
                {"node": "code_chunker", "thinking": "source_dir이 없거나 유효하지 않아 청킹 생략."}
            ],
        }

    all_chunks: List[CodeChunk] = []

    for dirpath, dirnames, filenames in os.walk(source_dir):
        # 무시 디렉터리 가지치기 (in-place 수정으로 os.walk 재귀 방지)
        dirnames[:] = [d for d in dirnames if not _should_ignore(d)]

        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(full_path, source_dir).replace("\\", "/")
            chunks = _process_file(full_path, rel_path, run_id, version)
            all_chunks.extend(chunks)

    thinking = f"총 {len(all_chunks)}개 코드 청크 추출 완료 (source_dir: {source_dir})"
    logger.info(f"[code_chunker] {thinking}")

    return {
        "rag_chunks": [c.model_dump() for c in all_chunks],
        "thinking_log": (sget("thinking_log", []) or []) + [
            {"node": "code_chunker", "thinking": thinking}
        ],
    }
