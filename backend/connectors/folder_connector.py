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


def scan_folder(root_path: str) -> dict:
    """
    폴더를 재귀 탐색하여 파일 트리를 반환.

    Args:
        root_path: 탐색 시작 절대 경로

    Returns:
        {
          "root": "/path/to/folder",
          "name": "folder",
          "tree": [ {"name", "type": "file"|"folder", "path"|"children"}, ... ]
        }
    """
    if not os.path.isdir(root_path):
        raise ValueError(f"유효하지 않은 경로: {root_path}")

    def walk(path: str) -> list:
        entries = []
        try:
            items = sorted(os.listdir(path), key=lambda x: (not os.path.isdir(os.path.join(path, x)), x.lower()))
        except PermissionError:
            return entries

        for name in items:
            if name in IGNORE or name.startswith("."):
                continue
            full = os.path.join(path, name)
            if os.path.isdir(full):
                children = walk(full)
                entries.append({
                    "name": name,
                    "type": "folder",
                    "path": full,
                    "children": children,
                })
            elif os.path.isfile(full):
                entries.append({
                    "name": name,
                    "type": "file",
                    "path": full,
                })
        return entries

    return {
        "root": root_path,
        "name": os.path.basename(root_path),
        "tree": walk(root_path),
    }
