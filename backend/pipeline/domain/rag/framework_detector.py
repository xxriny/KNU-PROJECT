"""
프레임워크 감지(LLM 비의존).

매니페스트(package.json/requirements.txt/pyproject.toml)와 엔트리포인트
파일의 정적 검사로 프레임워크 단서를 수집한다. result_shaping의
container diagram, SA의 merge_project가 직접 호출한다.
"""

from __future__ import annotations

import json
from pathlib import Path


def _safe_read_text(path: Path, limit: int = 200_000) -> str:
    try:
        data = path.read_text(encoding="utf-8", errors="replace")
        return data[:limit]
    except OSError:
        return ""


def detect_framework_evidence(source_dir: str) -> tuple[list[str], list[dict], dict]:
    """매니페스트/엔트리포인트 기반 프레임워크 단서 수집.

    Returns:
        (frameworks, evidence, coverage)
        - frameworks: 정렬된 프레임워크 이름 리스트
        - evidence: [{"framework", "file", "reason"}, ...] (최대 20)
        - coverage: {"path_exists": bool, "manifest_files_found": int, "framework_signals": int}
    """
    frameworks: set[str] = set()
    evidence: list[dict] = []
    coverage = {
        "path_exists": False,
        "manifest_files_found": 0,
        "framework_signals": 0,
    }

    root = Path(source_dir) if source_dir else None
    if not root or not root.is_dir():
        return [], [], coverage

    coverage["path_exists"] = True

    def add_signal(framework: str, rel_file: str, reason: str):
        frameworks.add(framework)
        evidence.append({"framework": framework, "file": rel_file, "reason": reason})

    # package.json 기반 신호
    package_json = root / "package.json"
    if package_json.exists():
        coverage["manifest_files_found"] += 1
        try:
            pkg = json.loads(_safe_read_text(package_json))
            deps = {
                **(pkg.get("dependencies") or {}),
                **(pkg.get("devDependencies") or {}),
            }
            dep_names = set(deps.keys())
            if "react" in dep_names:
                add_signal("React", "package.json", "dependencies.react 발견")
            if "electron" in dep_names:
                add_signal("Electron", "package.json", "dependencies/devDependencies.electron 발견")
            if "vite" in dep_names:
                add_signal("Vite", "package.json", "dependencies/devDependencies.vite 발견")
            if "next" in dep_names:
                add_signal("Next.js", "package.json", "dependencies.next 발견")
        except (json.JSONDecodeError, TypeError):
            pass

    # Python manifest 기반 신호
    requirements = root / "requirements.txt"
    if requirements.exists():
        coverage["manifest_files_found"] += 1
        req_text = _safe_read_text(requirements).lower()
        if "fastapi" in req_text:
            add_signal("FastAPI", "requirements.txt", "fastapi 패키지 발견")
        if "flask" in req_text:
            add_signal("Flask", "requirements.txt", "flask 패키지 발견")
        if "django" in req_text:
            add_signal("Django", "requirements.txt", "django 패키지 발견")
        if "streamlit" in req_text:
            add_signal("Streamlit", "requirements.txt", "streamlit 패키지 발견")
        if "pyqt" in req_text or "pyside" in req_text:
            add_signal("Qt", "requirements.txt", "pyqt/pyside 패키지 발견")

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        coverage["manifest_files_found"] += 1
        pp_text = _safe_read_text(pyproject).lower()
        if "fastapi" in pp_text:
            add_signal("FastAPI", "pyproject.toml", "fastapi 의존성 발견")
        if "flask" in pp_text:
            add_signal("Flask", "pyproject.toml", "flask 의존성 발견")
        if "django" in pp_text:
            add_signal("Django", "pyproject.toml", "django 의존성 발견")

    # 엔트리포인트 파일 기반 신호
    common_entry_files = [
        ("electron/main.js", "Electron", "Electron 메인 프로세스 엔트리 파일"),
        ("src/main.jsx", "React", "React 엔트리 파일"),
        ("src/main.tsx", "React", "React TypeScript 엔트리 파일"),
        ("backend/main.py", "FastAPI", "백엔드 엔트리 파일(main.py)"),
    ]
    for rel, fw, reason in common_entry_files:
        fpath = root / rel
        if fpath.exists():
            coverage["manifest_files_found"] += 1
            add_signal(fw, rel, reason)

    coverage["framework_signals"] = len(evidence)
    dedup_evidence = []
    seen = set()
    for item in evidence:
        key = (item["framework"], item["file"], item["reason"])
        if key not in seen:
            seen.add(key)
            dedup_evidence.append(item)

    return sorted(frameworks), dedup_evidence[:20], coverage
