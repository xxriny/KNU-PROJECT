"""
folder_connector — 로컬 폴더 스캔

Electron dialog.showOpenDialog로 선택된 폴더를
재귀 탐색하여 React 파일 트리 형식으로 반환한다.
"""

import os

IGNORE = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", ".cache", ".idea",
    ".vscode", "*.egg-info",
}


def scan_folder(root_path: str, max_depth: int = 3) -> dict:
    """
    폴더를 재귀 탐색하여 파일 트리를 반환.

    Args:
        root_path: 탐색 시작 절대 경로
        max_depth: 탐색 최대 깊이 (기본 3)

    Returns:
        {
          "root": "/path/to/folder",
          "name": "folder",
          "tree": [ {"name", "type": "file"|"folder", "path"|"children"}, ... ]
        }
    """
    if not os.path.isdir(root_path):
        raise ValueError(f"유효하지 않은 경로: {root_path}")

    def walk(path: str, current_depth: int = 1) -> list:
        entries = []
        if current_depth > max_depth:
            return entries

        try:
            items = sorted(os.listdir(path), key=lambda x: (not os.path.isdir(os.path.join(path, x)), x.lower()))
        except PermissionError:
            return entries

        for name in items:
            if name in IGNORE or name.startswith("."):
                continue
            full = os.path.join(path, name)
            if os.path.isdir(full):
                children = walk(full, current_depth + 1)
                entries.append({
                    "name": name,
                    "kind": "directory", # 일관성을 위해 kind로 통일 (기존 로직 고려)
                    "type": "folder",
                    "path": full,
                    "children": children,
                })
            elif os.path.isfile(full):
                entries.append({
                    "name": name,
                    "kind": "file",
                    "type": "file",
                    "path": full,
                })
        return entries

    return {
        "root": root_path,
        "name": os.path.basename(root_path),
        "tree": walk(root_path),
    }
