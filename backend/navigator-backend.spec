# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec — NAVIGATOR backend sidecar (macOS / Linux)

Build (from backend/ directory):
    pip install pyinstaller
    pyinstaller navigator-backend.spec --noconfirm

Output:
    backend/dist/navigator-backend/navigator-backend   (macOS/Linux)

Notes:
  - upx=False: UPX can corrupt macOS native extensions (.dylib)
  - collect_all is used for packages with data files or dynamic plugin loading
  - auth/database.py reads NAVIGATOR_STORAGE_DIR env var set by Electron;
    NAVIGATOR_BACKEND_ROOT env var is also set for .env loading in main.py
"""
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None


def ca(pkg):
    """Collect all data, binaries, and hidden imports for a package."""
    try:
        d, b, h = collect_all(pkg)
        return d, b, h
    except Exception as e:
        print(f"[spec] Warning: collect_all('{pkg}') failed: {e}")
        return [], [], []


# ── 패키지별 수집 (data files + dynamic plugins) ──────────────────────────────
uvicorn_d,     uvicorn_b,     uvicorn_h     = ca('uvicorn')
fastapi_d,     fastapi_b,     fastapi_h     = ca('fastapi')
starlette_d,   starlette_b,   starlette_h   = ca('starlette')
pydantic_d,    pydantic_b,    pydantic_h    = ca('pydantic')
pydantic_s_d,  pydantic_s_b,  pydantic_s_h  = ca('pydantic_settings')
langchain_d,   langchain_b,   langchain_h   = ca('langchain')
lc_core_d,     lc_core_b,     lc_core_h     = ca('langchain_core')
lc_comm_d,     lc_comm_b,     lc_comm_h     = ca('langchain_community')
lc_google_d,   lc_google_b,   lc_google_h   = ca('langchain_google_genai')
langgraph_d,   langgraph_b,   langgraph_h   = ca('langgraph')
lg_ckpt_d,     lg_ckpt_b,     lg_ckpt_h     = ca('langgraph_checkpoint')
structlog_d,   structlog_b,   structlog_h   = ca('structlog')
sqlalchemy_d,  sqlalchemy_b,  sqlalchemy_h  = ca('sqlalchemy')
githubkit_d,   githubkit_b,   githubkit_h   = ca('githubkit')
httpx_d,       httpx_b,       httpx_h       = ca('httpx')
httpcore_d,    httpcore_b,    httpcore_h    = ca('httpcore')
anyio_d,       anyio_b,       anyio_h       = ca('anyio')
multipart_d,   multipart_b,   multipart_h   = ca('multipart')
jose_d,        jose_b,        jose_h        = ca('jose')
passlib_d,     passlib_b,     passlib_h     = ca('passlib')
pypdf_d,       pypdf_b,       pypdf_h       = ca('pypdf')
docx_d,        docx_b,        docx_h        = ca('docx')

# google.* — 하위 패키지만 선택적 수집 (전체 google은 수 GB)
google_genai_d,    google_genai_b,    google_genai_h    = ca('google.genai')
google_ai_d,       google_ai_b,       google_ai_h       = ca('google.generativeai')
google_api_d,      google_api_b,      google_api_h      = ca('google.api_core')
google_auth_d,     google_auth_b,     google_auth_h     = ca('google.auth')
google_proto_d,    google_proto_b,    google_proto_h    = ca('google.protobuf')

all_datas = (
    uvicorn_d + fastapi_d + starlette_d + pydantic_d + pydantic_s_d +
    langchain_d + lc_core_d + lc_comm_d + lc_google_d +
    langgraph_d + lg_ckpt_d + structlog_d + sqlalchemy_d +
    githubkit_d + httpx_d + httpcore_d + anyio_d + multipart_d +
    jose_d + passlib_d + pypdf_d + docx_d +
    google_genai_d + google_ai_d + google_api_d + google_auth_d + google_proto_d
)
all_binaries = (
    uvicorn_b + fastapi_b + starlette_b + pydantic_b + pydantic_s_b +
    langchain_b + lc_core_b + lc_comm_b + lc_google_b +
    langgraph_b + lg_ckpt_b + structlog_b + sqlalchemy_b +
    githubkit_b + httpx_b + httpcore_b + anyio_b + multipart_b +
    jose_b + passlib_b + pypdf_b + docx_b +
    google_genai_b + google_ai_b + google_api_b + google_auth_b + google_proto_b
)
all_hidden = (
    uvicorn_h + fastapi_h + starlette_h + pydantic_h + pydantic_s_h +
    langchain_h + lc_core_h + lc_comm_h + lc_google_h +
    langgraph_h + lg_ckpt_h + structlog_h + sqlalchemy_h +
    githubkit_h + httpx_h + httpcore_h + anyio_h + multipart_h +
    jose_h + passlib_h + pypdf_h + docx_h +
    google_genai_h + google_ai_h + google_api_h + google_auth_h + google_proto_h
    + [
        # SQLAlchemy — SQLite 다이얼렉트는 문자열로 동적 로드됨
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.dialects.sqlite.pysqlite',
        # passlib — bcrypt 핸들러는 문자열로 동적 로드됨
        'passlib.handlers.bcrypt',
        'passlib.handlers.sha2_crypt',
        'passlib.handlers.pbkdf2',
        # python-jose — cryptography 백엔드
        'jose.backends',
        'jose.backends.cryptography_backend',
        'jose.backends.native',
        # uvicorn 프로토콜 (동적 선택)
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.protocols.websockets.websockets_impl',
        'uvicorn.protocols.websockets.wsproto_impl',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'uvicorn.lifespan.on',
        'uvicorn.lifespan.off',
        # anyio 백엔드
        'anyio._backends._asyncio',
        # 네트워크
        'sniffio', 'h11', 'h2', 'hpack', 'hyperframe',
        'websockets', 'websockets.legacy', 'websockets.server',
        'websockets.client',
        # multiprocessing (freeze_support)
        'multiprocessing.resource_sharer',
        'multiprocessing.resource_tracker',
        # openai (선택적 사용)
        'openai',
        'tiktoken', 'tiktoken_ext', 'tiktoken_ext.openai_public',
        # 기타
        'networkx', 'networkx.algorithms', 'networkx.classes',
        'tabulate', 'email_validator',
        'prometheus_client',
        'python_multipart',
        'chardet', 'charset_normalizer',
        'certifi',
    ]
)

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', '_tkinter', 'tk', 'tcl',
        'test', 'unittest',
        'IPython', 'jupyter', 'matplotlib', 'PIL', 'numpy', 'pandas',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='navigator-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,        # UPX는 macOS .dylib 손상 위험 — 절대 True로 바꾸지 말 것
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None, # None = 현재 빌드 머신 아키텍처 (x86_64 or arm64)
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='navigator-backend',
)
