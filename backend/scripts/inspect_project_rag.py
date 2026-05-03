"""
[EXPERIMENT-RAG-VIS] project_code_knowledge ChromaDB 인스펙터 (실험용 — 추후 제거 예정)

원복 방법:
  - 이 파일 통째로 삭제
  - `grep -rn "EXPERIMENT-RAG-VIS" backend/` 로 함께 박아둔 thinking_log 강화
    블록 두 곳(code_chunker.py, code_embedding.py)도 같이 원복

사용법 (backend 디렉터리에서):
  python scripts/inspect_project_rag.py                          # 전체 통계 + 샘플 5개
  python scripts/inspect_project_rag.py --limit 20               # 샘플 N개
  python scripts/inspect_project_rag.py --session 20260503_123456
  python scripts/inspect_project_rag.py --lang python
  python scripts/inspect_project_rag.py --query "user login"     # 유사도 검색 (모델 로드)
  python scripts/inspect_project_rag.py --query "auth" --session <id> --query-results 8
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

# nomic-embed/sentence-transformers 가 동일 OpenMP 런타임을 두 번 적재하는 문제 회피
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# Windows cp949 콘솔에서도 한글/유니코드가 깨지지 않도록 stdout/stderr를 UTF-8로 재설정
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# scripts/ → backend/
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from pipeline.domain.rag.nodes.project_db import (  # noqa: E402
    _get_collection,
    DB_PATH,
    query_project_code,
)


def _print_header(title: str) -> None:
    print("\n" + f" {title} ".center(60, "="))


def _truncate(text: str, n: int = 200) -> str:
    text = text or ""
    flat = text.replace("\n", " ⏎ ")
    return flat[:n] + ("..." if len(text) > n else "")


def _print_stats(coll) -> int:
    total = coll.count()
    _print_header("project_code_knowledge")
    print(f"  Path  : {DB_PATH}")
    print(f"  Total : {total}개 청크")

    if total == 0:
        print("  (비어 있음 — 분석을 한 번도 돌리지 않았거나 RAG 인제스트가 스킵되었습니다)")
        return total

    # 메타데이터만 가져오기 (벡터/문서 본문 제외 — 가벼움)
    sample = coll.get(include=["metadatas"])
    metas = sample.get("metadatas", []) or []

    by_lang = Counter(m.get("lang", "?") for m in metas)
    by_session = Counter(m.get("session_id", "?") for m in metas)
    files = sorted({m.get("file_path", "") for m in metas if m.get("file_path")})

    print(f"  Lang  : {dict(by_lang)}")
    print(f"  Files : {len(files)}개")
    print("  Sessions:")
    for sid, cnt in by_session.most_common():
        print(f"    - {sid}: {cnt}개 청크")
    return total


def _print_samples(coll, limit: int, where: dict | None) -> None:
    kwargs: dict = {"include": ["documents", "metadatas"], "limit": limit}
    if where:
        kwargs["where"] = where
    res = coll.get(**kwargs)
    ids = res.get("ids", []) or []
    docs = res.get("documents", []) or []
    metas = res.get("metadatas", []) or []

    _print_header(f"Samples ({len(ids)}개" + (f", filter={where}" if where else "") + ")")
    if not ids:
        print("  (조건에 맞는 청크 없음)")
        return

    for i, cid in enumerate(ids):
        meta = metas[i] if i < len(metas) else {}
        doc = docs[i] if i < len(docs) else ""
        print(f"\n  - id        : {cid}")
        print(f"    file_path : {meta.get('file_path')}")
        print(f"    func_name : {meta.get('func_name')}")
        print(f"    lang      : {meta.get('lang')}")
        print(f"    session   : {meta.get('session_id')}")
        print(f"    preview   : {_truncate(doc)}")


def _print_query(query: str, session_id: str | None, n_results: int) -> None:
    _print_header(f"Similarity Query (n={n_results})")
    print(f"  query   : {query}")
    if session_id:
        print(f"  session : {session_id}")
    try:
        results = query_project_code(query_text=query, session_id=session_id, n_results=n_results)
    except Exception as e:
        print(f"  Query 실패: {e}")
        return

    if not results:
        print("  (결과 없음)")
        return

    for r in results:
        print(f"\n  - sim       : {r['similarity']}")
        print(f"    id        : {r['chunk_id']}")
        print(f"    file_path : {r['file_path']}")
        print(f"    func_name : {r['func_name']}")
        print(f"    preview   : {_truncate(r['content_text'])}")


def _build_where(session: str | None, lang: str | None) -> dict | None:
    filters = []
    if session:
        filters.append({"session_id": session})
    if lang:
        filters.append({"lang": lang})
    if not filters:
        return None
    if len(filters) == 1:
        return filters[0]
    return {"$and": filters}


def main() -> None:
    parser = argparse.ArgumentParser(description="project_code_knowledge 인스펙터 (EXPERIMENT-RAG-VIS)")
    parser.add_argument("--limit", type=int, default=5, help="샘플 청크 수 (default: 5)")
    parser.add_argument("--session", type=str, default=None, help="session_id 필터")
    parser.add_argument("--lang", type=str, default=None, help="lang 필터 (python | javascript | unknown ...)")
    parser.add_argument("--query", type=str, default=None, help="유사도 검색 쿼리 (지정 시 샘플 출력 대신 검색 실행)")
    parser.add_argument("--query-results", type=int, default=5, help="유사도 검색 결과 수 (default: 5)")
    args = parser.parse_args()

    coll = _get_collection()
    total = _print_stats(coll)

    if total == 0:
        return

    if args.query:
        _print_query(args.query, args.session, args.query_results)
    else:
        _print_samples(coll, args.limit, _build_where(args.session, args.lang))

    print()


if __name__ == "__main__":
    main()
