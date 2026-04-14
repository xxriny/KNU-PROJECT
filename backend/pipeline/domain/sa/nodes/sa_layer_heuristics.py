"""SA Phase 5 — 레이어 분류 휴리스틱 (코드 스캔 기반 계층 추론)"""

import re
from collections import defaultdict

LAYER_ORDER = ["Presentation", "Application", "Domain", "Infrastructure"]

LAYER_KEYWORDS = {
    "Presentation": {"view", "page", "screen", "component", "ui", "route", "controller", "api", "handler", "electron", "react", "websocket", "rest"},
    "Application": {"service", "runner", "pipeline", "orchestr", "usecase", "workflow", "process", "handle", "execute"},
    "Domain": {"domain", "entity", "model", "rule", "schema", "graph", "state", "scanner", "parser", "validate", "calculate", "analy"},
    "Infrastructure": {"db", "repo", "client", "infra", "storage", "auth", "config", "adapter", "logger", "metric", "connector", "transport", "socket", "file", "chroma"},
}

FRAMEWORK_LAYER_HINTS = {
    "react": "Presentation",
    "electron": "Presentation",
    "vite": "Presentation",
    "fastapi": "Application",
    "flask": "Application",
    "django": "Application",
}

BACKEND_FRAMEWORKS = {"fastapi", "flask", "django", "streamlit"}
FRONTEND_FRAMEWORKS = {"react", "electron", "vite", "next.js", "vue", "angular"}

MODULE_SIGNAL_HINTS = {
    "Application": {"main", "pipeline_runner", "orchestration", "workflow", "runner"},
    "Domain": {"ast_scanner", "scanner", "parser", "graph", "schema", "state"},
    "Infrastructure": {"connector", "logger", "metrics", "metric", "observability", "storage", "client", "chroma"},
}

LAYER_BY_CATEGORY = {
    "Frontend": "Presentation", "Backend": "Application", "Architecture": "Domain",
    "Database": "Infrastructure", "Security": "Infrastructure", "AI/ML": "Domain",
    "Infrastructure": "Infrastructure",
}


def infer_layer_from_path(module_name: str) -> str:
    name = (module_name or "").lower()
    if "backend/main.py" in name or "/main.py" in name or name.endswith("main.py"):
        return "Application"
    if any(token in name for token in ["view", "page", "screen", "component", "ui", "route", "controller", "api"]):
        return "Presentation"
    if any(token in name for token in ["domain", "entity", "model", "core", "rule"]):
        return "Domain"
    if any(token in name for token in ["db", "repo", "client", "infra", "storage", "auth", "config", "adapter", "connector", "logger", "metric", "metrics", "observability", "chroma"]):
        return "Infrastructure"
    return "Application"


def tokenize_text(*parts: str) -> list[str]:
    tokens = []
    for part in parts:
        if not part:
            continue
        lowered = part.lower().replace("/", " ").replace("\\", " ").replace("_", " ").replace("-", " ")
        tokens.extend(re.findall(r"[a-zA-Z]{2,}", lowered))
    return tokens


def normalize_module_path(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    text = text.split(" (", 1)[0].strip()
    return text.replace("\\", "/").lower().rstrip("/")


def canonical_module_id(module_name: str) -> str:
    normalized = normalize_module_path(module_name)
    if not normalized:
        return "unknown-module"
    base = normalized.rsplit("/", 1)[-1]
    for suffix in (".py", ".js", ".jsx", ".ts", ".tsx"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base or "unknown-module"


def framework_scope_map(framework_evidence: list[dict]) -> dict[str, set[str]]:
    scope_map: dict[str, set[str]] = defaultdict(set)
    for item in framework_evidence or []:
        framework = (item.get("framework") or "").strip().lower()
        file_path = (item.get("file") or "").replace("\\", "/").lower()
        if not framework or not file_path:
            continue
        if "/" in file_path:
            scope_map[framework].add(file_path.rsplit("/", 1)[0] + "/")
        else:
            scope_map[framework].add(file_path)
    return scope_map


def module_family(module_name: str, language: str) -> str:
    name = (module_name or "").replace("\\", "/").lower()
    lang = (language or "").lower()
    if name.startswith("backend/"):
        return "backend"
    if name.startswith("electron/"):
        return "electron"
    if name.startswith("src/") or any(token in name for token in ["component", "page", "screen", "frontend"]):
        return "frontend"
    if lang in {"javascript", "typescript"}:
        return "frontend"
    if lang == "python":
        return "backend"
    return "unknown"


def _path_is_close(module_name: str, scoped_path: str) -> bool:
    module_path = (module_name or "").replace("\\", "/").lower()
    scope_path = (scoped_path or "").replace("\\", "/").lower()
    return bool(scope_path) and (module_path.startswith(scope_path) or scope_path.startswith(module_path.rsplit("/", 1)[0] + "/"))


def scoped_frameworks_for_module(module_name: str, language: str, detected_frameworks: list[str], framework_evidence: list[dict]) -> list[str]:
    family = module_family(module_name, language)
    scope_map = framework_scope_map(framework_evidence)
    scoped: list[str] = []

    for framework_name in detected_frameworks or []:
        framework = (framework_name or "").strip().lower()
        if not framework:
            continue
        if family == "backend" and framework not in BACKEND_FRAMEWORKS:
            continue
        if family in {"frontend", "electron"} and framework not in FRONTEND_FRAMEWORKS:
            continue
        scoped_paths = scope_map.get(framework, set())
        if scoped_paths:
            if any(_path_is_close(module_name, sp) for sp in scoped_paths if "/" in sp):
                scoped.append(framework_name)
                continue
            if family == "backend" and framework in BACKEND_FRAMEWORKS:
                scoped.append(framework_name)
                continue
            if family in {"frontend", "electron"} and framework in FRONTEND_FRAMEWORKS:
                scoped.append(framework_name)
                continue
            continue
        scoped.append(framework_name)

    return scoped


def score_layers(
    *, module_name: str = "", description: str = "", category: str = "",
    language: str = "", frameworks: list[str] | None = None, functions: list[dict] | None = None,
) -> tuple[str, int, list[str]]:
    """멀티 시그널 기반 레이어 스코어링. (layer, confidence, evidence) 반환."""
    scores = {layer: 0 for layer in LAYER_ORDER}
    evidence: list[str] = []
    frameworks = [fw.lower() for fw in (frameworks or [])]
    functions = functions or []

    tokens = tokenize_text(module_name, description, category)
    for layer, keywords in LAYER_KEYWORDS.items():
        matched = sorted({token for token in tokens if token in keywords})
        if matched:
            weight = 10 if layer == "Infrastructure" else 8
            scores[layer] += weight * len(matched)
            evidence.append(f"{layer} 키워드 감지: {', '.join(matched[:4])}")

    lowered_name = (module_name or "").lower()
    for layer, hints in MODULE_SIGNAL_HINTS.items():
        matched = sorted({hint for hint in hints if hint in lowered_name})
        if matched:
            boost = {"Application": 18, "Domain": 16, "Infrastructure": 22}[layer]
            scores[layer] += boost
            evidence.append(f"모듈 신호: {layer} <- {', '.join(matched[:3])}")

    if any(token in tokens for token in ["scanner", "parser", "parse", "graph", "schema", "state"]):
        scores["Domain"] += 18
        evidence.append("도메인 분석/파싱 신호 감지")

    path_hint = infer_layer_from_path(lowered_name)
    path_weight = 22 if path_hint == "Infrastructure" else 18 if path_hint == "Application" else 15
    scores[path_hint] += path_weight
    evidence.append(f"경로 기반 힌트: {path_hint}")

    for framework in frameworks:
        hinted = FRAMEWORK_LAYER_HINTS.get(framework)
        if hinted:
            scores[hinted] += 12
            evidence.append(f"프레임워크 힌트: {framework} -> {hinted}")

    if language.lower() in {"javascript", "typescript"}:
        scores["Presentation"] += 10
        evidence.append(f"언어 힌트: {language} -> Presentation")
    elif language.lower() == "python":
        scores["Application"] += 8
        scores["Infrastructure"] += 6
        evidence.append("언어 힌트: python -> Application/Infrastructure")

    for fn in functions[:6]:
        fn_tokens = tokenize_text(fn.get("func_name", ""), fn.get("docstring", ""))
        for layer, keywords in LAYER_KEYWORDS.items():
            matched = sorted({token for token in fn_tokens if token in keywords})
            if matched:
                scores[layer] += 5 * len(matched)
                evidence.append(f"함수/문서 힌트({fn.get('func_name', 'unknown')}): {layer} <- {', '.join(matched[:3])}")
        if any(token in fn_tokens for token in ["parse", "scanner", "graph", "schema", "validate", "analysis"]):
            scores["Domain"] += 10
            evidence.append(f"함수 핵심 로직 신호({fn.get('func_name', 'unknown')}): Domain")

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    layer = ranked[0][0]
    top_score = ranked[0][1]
    second_score = ranked[1][1] if len(ranked) > 1 else 0
    competing_layers = sum(1 for _, score in ranked[1:] if score >= max(10, top_score - 8))
    confidence = min(96, max(35, 58 + (top_score - second_score) * 3 + min(len(evidence), 4) * 2 - competing_layers * 6))
    return layer, confidence, evidence[:5]


def fallback_mapping_info(req: dict) -> dict:
    layer, confidence, evidence = score_layers(
        module_name=req.get("REQ_ID", ""),
        description=req.get("description", ""),
        category=req.get("category", ""),
    )
    return {
        "layer": layer,
        "confidence": confidence,
        "reason": evidence[0] if evidence else "휴리스틱 기반 계층 매핑",
        "evidence": evidence,
    }
