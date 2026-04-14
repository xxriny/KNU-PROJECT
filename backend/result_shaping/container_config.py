"""
Container Diagram 설정 — 프로젝트별 컨테이너 그룹, 에지, 외부 시스템 정의

이 파일을 교체하면 다른 프로젝트의 아키텍처 다이어그램도 생성할 수 있다.
"""

from typing import Any

LAYER_ORDER = ["Presentation", "Application", "Domain", "Infrastructure", "Security"]

# 파일 경로 패턴 → 논리 컨테이너 매핑 규칙
# path_prefixes: 전방 일치 / exact_paths: 완전 일치 (우선 체크)
CONTAINER_GROUPS: list[dict[str, Any]] = [
    {
        "id": "electron-shell",
        "label": "Electron Shell",
        "layer": "Presentation",
        "description": "데스크탑 앱 컨테이너 (프로세스 관리, IPC, 창 제어)",
        "path_prefixes": ["electron/"],
    },
    {
        "id": "react-ui",
        "label": "React UI",
        "layer": "Presentation",
        "description": "사용자 인터페이스 (컴포넌트, 라우팅, 상태 관리)",
        "path_prefixes": ["src/"],
    },
    {
        "id": "fastapi-server",
        "label": "FastAPI Server",
        "layer": "Application",
        "description": "HTTP/WebSocket 서버 엔트리포인트 및 라이프사이클 관리",
        "exact_paths": ["backend/main.py"],
    },
    {
        "id": "transport-layer",
        "label": "Transport Layer",
        "layer": "Application",
        "description": "WebSocket / REST 수신, 세션 관리, 연결 풀",
        "path_prefixes": ["backend/transport/"],
    },
    {
        "id": "pipeline-orchestrator",
        "label": "Pipeline Orchestrator",
        "layer": "Application",
        "description": "LangGraph 파이프라인 흐름 제어 및 라우팅",
        "path_prefixes": ["backend/orchestration/"],
        "exact_paths": ["backend/pipeline/facade.py"],
    },
    {
        "id": "sa-pipeline",
        "label": "SA Pipeline",
        "layer": "Application",
        "description": "시스템 아키텍처 분석 노드 체인 (sa_phase1 ~ sa_phase8, merge_project)",
        "path_prefixes": ["backend/pipeline/sa/nodes/sa_"],
    },
    {
        "id": "pm-pipeline",
        "label": "PM Pipeline",
        "layer": "Application",
        "description": "PM 분석 및 채팅 노드 (pm_phase1~5, atomizer, prioritizer, chat)",
        "path_prefixes": [
            "backend/pipeline/pm/nodes/pm_",
            "backend/pipeline/pm/nodes/atomizer",
            "backend/pipeline/pm/nodes/prioritizer",
            "backend/pipeline/analysis/idea_chat",
            "backend/pipeline/analysis/chat_revision",
        ],
    },
    {
        "id": "result-shaper",
        "label": "Result Shaper",
        "layer": "Application",
        "description": "파이프라인 결과 컴파일 및 시각화 산출물 정형화",
        "path_prefixes": ["backend/result_shaping/"],
    },
    {
        "id": "core-domain",
        "label": "Core Domain",
        "layer": "Domain",
        "description": "AST 스캐너, LLM 유틸리티 래퍼, 상태·스키마 정의",
        "exact_paths": [
            "backend/pipeline/ast_scanner.py",
            "backend/pipeline/utils.py",
            "backend/pipeline/schemas.py",
            "backend/pipeline/state.py",
        ],
    },
    {
        "id": "data-connectors",
        "label": "Data Connectors",
        "layer": "Infrastructure",
        "description": "ChromaDB 클라이언트, 결과 로거, 폴더 스캐너",
        "path_prefixes": ["backend/connectors/"],
        "exact_paths": ["backend/pipeline/chroma_client.py"],
    },
    {
        "id": "observability",
        "label": "Observability",
        "layer": "Infrastructure",
        "description": "구조화 로깅(structlog) 및 Prometheus 메트릭 수집",
        "path_prefixes": ["backend/observability/"],
    },
]

# 컨테이너 간 사전 정의된 통신 엣지 (프로토콜 명시)
CONTAINER_EDGES: list[dict[str, Any]] = [
    {"source": "electron-shell", "target": "react-ui",         "protocol": "Electron IPC",       "edge_type": "ipc"},
    {"source": "electron-shell", "target": "fastapi-server",   "protocol": "spawn / HTTP",        "edge_type": "process"},
    {"source": "react-ui",        "target": "transport-layer",  "protocol": "WebSocket / REST",    "edge_type": "http"},
    {"source": "transport-layer", "target": "fastapi-server",  "protocol": "ASGI routing",        "edge_type": "internal"},
    {"source": "transport-layer", "target": "pipeline-orchestrator", "protocol": "Python call",   "edge_type": "internal"},
    {"source": "pipeline-orchestrator", "target": "sa-pipeline",    "protocol": "node dispatch",  "edge_type": "internal"},
    {"source": "pipeline-orchestrator", "target": "pm-pipeline",    "protocol": "node dispatch",  "edge_type": "internal"},
    {"source": "pipeline-orchestrator", "target": "core-domain",    "protocol": "function call",  "edge_type": "internal"},
    {"source": "pipeline-orchestrator", "target": "result-shaper",  "protocol": "function call",  "edge_type": "internal"},
    {"source": "sa-pipeline",  "target": "core-domain",     "protocol": "function call",          "edge_type": "internal"},
    {"source": "sa-pipeline",  "target": "data-connectors", "protocol": "vector query",           "edge_type": "data"},
    {"source": "sa-pipeline",  "target": "llm-api",         "protocol": "HTTPS (Gemini API)",     "edge_type": "external"},
    {"source": "pm-pipeline",  "target": "core-domain",     "protocol": "function call",          "edge_type": "internal"},
    {"source": "pm-pipeline",  "target": "llm-api",         "protocol": "HTTPS (Gemini API)",     "edge_type": "external"},
    {"source": "result-shaper","target": "data-connectors", "protocol": "write result JSON",      "edge_type": "data"},
    {"source": "data-connectors","target": "chromadb",      "protocol": "Vector Query (local)",   "edge_type": "external"},
    {"source": "data-connectors","target": "file-system",   "protocol": "File I/O",               "edge_type": "external"},
    {"source": "core-domain",  "target": "file-system",     "protocol": "AST parse",              "edge_type": "external"},
    {"source": "observability", "target": "fastapi-server", "protocol": "ASGI middleware",        "edge_type": "internal"},
]

# raw_import 신호 → 외부 시스템 탐지 규칙
EXTERNAL_SYSTEM_SIGNALS: list[dict[str, Any]] = [
    {
        "id": "users",
        "label": "Users",
        "description": "시스템을 사용하는 최종 사용자 진입점",
        "signals": [],
        "always_include": True,
    },
    {
        "id": "llm-api",
        "label": "LLM API",
        "description": "Google Gemini 등 외부 LLM 서비스 (HTTPS)",
        "signals": ["google.generativeai", "google-generativeai", "langchain", "openai", "anthropic", "gemini"],
    },
    {
        "id": "chromadb",
        "label": "ChromaDB",
        "description": "로컬 벡터 데이터베이스 (임베딩 저장 및 유사도 검색)",
        "signals": ["chromadb"],
    },
    {
        "id": "file-system",
        "label": "File System",
        "description": "사용자 프로젝트 소스코드 (AST 스캔 대상)",
        "signals": [],
        "always_include": True,
    },
]

# file_path 단서가 비어 있을 때 layer 기반으로 최소 컨테이너를 복원한다.
LAYER_FALLBACK_CONTAINERS: dict[str, list[str]] = {
    "presentation": ["react-ui"],
    "application": ["pipeline-orchestrator"],
    "domain": ["core-domain"],
    "infrastructure": ["data-connectors"],
    "security": ["observability"],
    "unknown": ["pipeline-orchestrator"],
}
