import json
import os
import re
from collections import defaultdict
from typing import List
from pydantic import BaseModel, Field
from pipeline.state import PipelineState
from pipeline.utils import call_structured_with_thinking

# 1. 아키텍처 매핑을 위한 Pydantic 스키마 (가드레일 역할)
class RequirementMapping(BaseModel):
    REQ_ID: str = Field(description="요구사항 ID")
    layer: str = Field(description="반드시 다음 중 하나: Presentation | Application | Domain | Infrastructure")
    reason: str = Field(description="해당 레이어에 배치한 구체적인 기술적 이유 (한국어 1문장)")

class ArchitectureMappingOutput(BaseModel):
    thinking: str = Field(default="", description="매핑 추론 과정 (3줄 이내)")
    pattern_name: str = Field(default="Clean Architecture", description="적용된 아키텍처 패턴")
    mapped_requirements: List[RequirementMapping] = Field(description="각 요구사항의 레이어 매핑 결과")

class ModuleFunctionalLabel(BaseModel):
    canonical_id: str = Field(description="모듈 canonical ID (입력값 그대로 반환)")
    functional_name: str = Field(description="모듈의 핵심 기능명/역할 (한국어, 15자 이내, 명사형). 예: 파이프라인 오케스트레이터, 코드 AST 스캐너")

class ModuleLabelBatchOutput(BaseModel):
    labels: List[ModuleFunctionalLabel] = Field(description="각 모듈의 기능명 레이블 목록 (입력 모듈 전부 포함)")

# 2. LLM이 구조를 창조하지 못하도록 강력하게 통제하는 시스템 프롬프트
MAPPING_SYSTEM_PROMPT = """\
당신은 소프트웨어 시스템 아키텍트입니다.
제공된 요구사항(RTM)을 분석하여 '클린 아키텍처(Clean Architecture)'의 고정된 4가지 계층 중 하나에 각각 매핑하세요.

[고정된 계층(Layer) 및 매핑 가이드]
1. Presentation: 사용자 UI, 클라이언트 통신, 컨트롤러, API 엔드포인트 (예: 화면 렌더링, API 응답)
2. Application: 유스케이스, 비즈니스 흐름 제어, 트랜잭션 관리 (예: 사용자 인증 로직 흐름, 특정 기능 오케스트레이션)
3. Domain: 시스템의 핵심 비즈니스 룰, 엔티티, 순수 알고리즘 (예: 역량 평가 계산식, 연봉 산정 로직 등 프레임워크에 의존하지 않는 순수 로직)
4. Infrastructure: 외부 DB 연동, API 통신, 파일 I/O, 보안/암호화 등 기술적 구현체 (예: 카카오톡 연동, MongoDB 저장, On-Device 벡터화)

[규칙]
1. 새로운 계층을 절대 임의로 만들어내지 마세요. 오직 위 4개 중 하나만 선택해야 합니다.
2. 요구사항의 'description'을 깊이 읽고, 단순 카테고리(Frontend/Backend)에 속지 말고 실제 수행하는 역할을 바탕으로 배치하세요.
3. 각 매핑의 이유(reason)를 1문장으로 명확히 작성하세요."""

MODULE_LABEL_SYSTEM_PROMPT = """\
당신은 소프트웨어 아키텍트입니다.
제공된 모듈 목록의 파일 경로와 주요 함수명을 분석하여 각 모듈의 핵심 기능명 또는 역할을 한국어로 작성하세요.

[규칙]
1. functional_name은 15자 이내 한국어 명사형으로 작성하세요. (예: "파이프라인 오케스트레이터", "코드 AST 스캐너", "WS 수신 핸들러")
2. canonical_id는 입력값을 절대 변경하지 말고 그대로 반환하세요.
3. 파일 경로와 함수명을 모두 참고하여 역할을 정확히 추론하세요.
4. 입력된 모든 모듈에 대해 빠짐없이 labels를 채워주세요."""


def _infer_layer_from_path(module_name: str) -> str:
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
MAX_REVERSE_MODULES = 120


def _tokenize_text(*parts: str) -> list[str]:
    tokens = []
    for part in parts:
        if not part:
            continue
        lowered = part.lower().replace("/", " ").replace("\\", " ").replace("_", " ").replace("-", " ")
        tokens.extend(re.findall(r"[a-zA-Z]{2,}", lowered))
    return tokens


def _normalize_module_path(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    text = text.split(" (", 1)[0].strip()
    return text.replace("\\", "/").lower().rstrip("/")


def _canonical_module_id(module_name: str) -> str:
    normalized = _normalize_module_path(module_name)
    if not normalized:
        return "unknown-module"
    base = normalized.rsplit("/", 1)[-1]
    for suffix in (".py", ".js", ".jsx", ".ts", ".tsx"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base or "unknown-module"


def _framework_scope_map(framework_evidence: list[dict]) -> dict[str, set[str]]:
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


def _module_family(module_name: str, language: str) -> str:
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


def _scoped_frameworks_for_module(module_name: str, language: str, detected_frameworks: list[str], framework_evidence: list[dict]) -> list[str]:
    family = _module_family(module_name, language)
    scope_map = _framework_scope_map(framework_evidence)
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
            if any(_path_is_close(module_name, scoped_path) for scoped_path in scoped_paths if "/" in scoped_path):
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


def _score_layers(*, module_name: str = "", description: str = "", category: str = "", language: str = "", frameworks: list[str] | None = None, functions: list[dict] | None = None) -> tuple[str, int, list[str]]:
    scores = {layer: 0 for layer in LAYER_ORDER}
    evidence: list[str] = []
    frameworks = [fw.lower() for fw in (frameworks or [])]
    functions = functions or []

    tokens = _tokenize_text(module_name, description, category)
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

    path_hint = _infer_layer_from_path(lowered_name)
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
        fn_tokens = _tokenize_text(fn.get("func_name", ""), fn.get("docstring", ""))
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


def _build_reverse_module_profiles(sa_phase1: dict) -> list[dict]:
    sample_functions = sa_phase1.get("sample_functions", []) or []
    key_modules = sa_phase1.get("key_modules", []) or []
    file_inventory = sa_phase1.get("file_inventory", []) or []
    detected_frameworks = sa_phase1.get("detected_frameworks", []) or []
    framework_evidence = sa_phase1.get("framework_evidence", []) or []

    functions_by_file: dict[str, list[dict]] = defaultdict(list)
    for fn in sample_functions:
        file_path = (fn.get("file") or "").strip()
        normalized = _normalize_module_path(file_path)
        if not normalized:
            continue
        functions_by_file[normalized].append(fn)

    profiles_by_file: dict[str, dict] = {}
    for item in file_inventory:
        display_file = (item.get("file") or "").strip().replace("\\", "/")
        file_path = _normalize_module_path(display_file)
        if not file_path:
            continue
        profiles_by_file.setdefault(
            file_path,
            {
                "module_name": display_file or file_path,
                "description": f"핵심 분석 모듈: {display_file or file_path}",
                "file_path": file_path,
                "canonical_id": _canonical_module_id(file_path),
                "language": item.get("lang", ""),
                "functions": list(functions_by_file.get(file_path, [])),
                "frameworks": _scoped_frameworks_for_module(file_path, item.get("lang", ""), detected_frameworks, framework_evidence),
                "imports": item.get("internal_imports", []) or [],
                "raw_imports": item.get("raw_imports", []) or [],
                "function_count": int(item.get("function_count", 0) or 0),
                "source_kind": "code_scan",
                "is_entrypoint": bool(item.get("is_entrypoint")),
            },
        )

    for normalized, functions in functions_by_file.items():
        if normalized in profiles_by_file:
            continue
        language = functions[0].get("lang", "") if functions else ""
        display_file = (functions[0].get("file") or normalized) if functions else normalized
        profiles_by_file[normalized] = {
            "module_name": display_file,
            "description": f"핵심 분석 모듈: {display_file}",
            "file_path": normalized,
            "canonical_id": _canonical_module_id(normalized),
            "language": language,
            "functions": list(functions),
            "frameworks": _scoped_frameworks_for_module(normalized, language, detected_frameworks, framework_evidence),
            "imports": [],
            "raw_imports": [],
            "function_count": len(functions),
            "source_kind": "function_sample",
            "is_entrypoint": False,
        }

    profiles = list(profiles_by_file.values())
    seen_canonical = {profile.get("canonical_id") for profile in profiles}
    for module in key_modules:
        name = (module or "").strip()
        normalized = _normalize_module_path(name)
        canonical_id = _canonical_module_id(normalized)
        if not normalized or canonical_id in seen_canonical:
            continue
        language = "javascript" if any(token in name.lower() for token in ["react", "electron", "frontend"]) else "python"
        profiles.append(
            {
                "module_name": name,
                "description": f"핵심 분석 모듈: {name}",
                "file_path": normalized,
                "canonical_id": canonical_id,
                "language": language,
                "functions": [],
                "frameworks": _scoped_frameworks_for_module(name, language, detected_frameworks, framework_evidence),
                "imports": [],
                "raw_imports": [],
                "function_count": 0,
                "source_kind": "key_module",
                "is_entrypoint": False,
            }
        )
        seen_canonical.add(canonical_id)

    # 함수 단서가 많은 모듈을 우선 포함해 시각화 누락을 줄인다.
    profiles.sort(
        key=lambda profile: (
            not profile.get("is_entrypoint", False),
            -int(profile.get("function_count", 0) or len(profile.get("functions", []))),
            profile.get("file_path", "") or profile.get("module_name", ""),
        )
    )
    return profiles[:MAX_REVERSE_MODULES]


def _fallback_mapping_info(req: dict) -> dict:
    layer, confidence, evidence = _score_layers(
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


def _batch_label_modules(profiles: list[dict], api_key: str, model: str) -> dict[str, str]:
    """단일 배치 LLM 호출로 모듈별 기능명 레이블 맵을 반환합니다. 실패 시 빈 dict."""
    if not profiles or not api_key:
        return {}

    batch_input = []
    for profile in profiles:
        func_names = [
            fn.get("func_name", "")
            for fn in (profile.get("functions") or [])[:3]
            if fn.get("func_name")
        ]
        batch_input.append({
            "canonical_id": profile["canonical_id"],
            "file_path": profile.get("file_path") or profile.get("module_name", ""),
            "functions": func_names,
        })

    user_msg = (
        f"다음 {len(batch_input)}개 모듈의 기능명을 한국어로 작성해주세요.\n\n"
        f"```json\n{json.dumps(batch_input, ensure_ascii=False, indent=2)}\n```"
    )

    try:
        result, _ = call_structured_with_thinking(
            api_key=api_key,
            model=model,
            schema=ModuleLabelBatchOutput,
            system_prompt=MODULE_LABEL_SYSTEM_PROMPT,
            user_msg=user_msg,
            max_retries=1,
        )
        return {label.canonical_id: label.functional_name for label in result.labels}
    except Exception:
        return {}


def _build_reverse_module_mapping(sa_phase1: dict, *, api_key: str = "", model: str = "gemini-2.5-flash") -> list[dict]:
    profiles = _build_reverse_module_profiles(sa_phase1)
    label_map = _batch_label_modules(profiles, api_key, model)

    mapped = []
    for index, profile in enumerate(profiles, start=1):
        layer, confidence, evidence = _score_layers(
            module_name=profile["module_name"],
            description=profile["description"],
            language=profile.get("language", ""),
            frameworks=profile.get("frameworks", []),
            functions=profile.get("functions", []),
        )
        canonical_id = profile.get("canonical_id") or _canonical_module_id(profile.get("module_name", ""))
        functional_name = label_map.get(canonical_id, "")
        description = functional_name if functional_name else profile["description"]
        mapped.append({
            "REQ_ID": f"MOD-{index:03d}",
            "layer": layer,
            "description": description,
            "functional_name": functional_name,
            "depends_on": [],
            "mapping_reason": "; ".join(evidence[:2]) if evidence else "reverse 모드에서 코드 스캔 결과를 기반으로 계층 매핑",
            "layer_confidence": confidence,
            "layer_evidence": evidence,
            "file_path": profile.get("file_path") or _normalize_module_path(profile.get("module_name", "")),
            "canonical_id": canonical_id,
            "source_kind": profile.get("source_kind", "code_scan"),
            "import_hints": profile.get("imports", []) or [],
            "raw_import_hints": profile.get("raw_imports", []) or [],
        })
    return mapped

def sa_phase5_node(state: PipelineState) -> dict:
    def sget(key, default=None):
        if hasattr(state, "get"):
            val = state.get(key, default)
        else:
            val = getattr(state, key, default)
        return default if val is None else val

    rtm = sget("requirements_rtm", []) or sget("rtm_matrix", []) or []
    action_type = (sget("action_type", "") or "CREATE").strip().upper()
    sa_phase1 = sget("sa_phase1", {}) or {}
    api_key = sget("api_key", "")
    model = sget("model", "gemini-2.5-flash")

    if not rtm:
        if action_type == "REVERSE_ENGINEER":
            reverse_mapping = _build_reverse_module_mapping(sa_phase1, api_key=api_key, model=model)
            status = "Pass" if reverse_mapping else "Needs_Clarification"
            thinking = "reverse 모드에서 코드 스캔 기반 계층 매핑 생성" if reverse_mapping else "reverse 모드이지만 매핑 가능한 핵심 모듈이 없음"
            return {
                "sa_phase5": {
                    "status": status,
                    "pattern": "Clean Architecture",
                    "mapped_requirements": reverse_mapping,
                    "layer_order": ["Presentation", "Application", "Domain", "Infrastructure"],
                },
                "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_phase5", "thinking": thinking}],
                "current_step": "sa_phase5_done",
            }
        return {
            "sa_phase5": {
                "status": "Needs_Clarification",
                "pattern": "Clean Architecture",
                "mapped_requirements": [],
                "layer_order": ["Presentation", "Application", "Domain", "Infrastructure"],
            },
            "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_phase5", "thinking": "RTM 없음 - 매핑 생략"}],
            "current_step": "sa_phase5_done",
        }

    # 프롬프트 토큰 절약을 위한 RTM 요약
    rtm_compact = [
        {
            "REQ_ID": r.get("REQ_ID", ""),
            "category": r.get("category", ""),
            "description": r.get("description", ""),
        }
        for r in rtm
    ]
    
    user_msg = (
        f"다음 요구사항들을 클린 아키텍처 계층에 매핑하세요.\n\n"
        f"```json\n{json.dumps(rtm_compact, ensure_ascii=False, indent=2)}\n```"
    )

    try:
        # LLM을 이용한 정밀 매핑 (구조적 가드레일 내에서 작동)
        result, thinking = call_structured_with_thinking(
            api_key=api_key,
            model=model,
            schema=ArchitectureMappingOutput,
            system_prompt=MAPPING_SYSTEM_PROMPT,
            user_msg=user_msg,
            max_retries=2
        )
        
        # 기존 RTM 정보(depends_on 등)와 LLM의 매핑 결과 병합
        mapped_dict = {m.REQ_ID: {"layer": m.layer, "reason": m.reason} for m in result.mapped_requirements}
        
        final_mapped = []
        for req in rtm:
            req_id = req.get("REQ_ID", "")
            fallback_info = _fallback_mapping_info(req)
            mapping_info = mapped_dict.get(req_id, {"layer": fallback_info["layer"], "reason": fallback_info["reason"]})
            
            final_mapped.append({
                "REQ_ID": req_id,
                "layer": mapping_info["layer"],
                "description": req.get("description", ""),
                "depends_on": req.get("depends_on", []) or [],
                "mapping_reason": mapping_info["reason"],
                "layer_confidence": fallback_info["confidence"],
                "layer_evidence": fallback_info["evidence"],
            })

        output = {
            "status": "Pass",
            "pattern": result.pattern_name,
            "mapped_requirements": final_mapped,
            "layer_order": ["Presentation", "Application", "Domain", "Infrastructure"],
        }
        thinking_msg = f"패턴 매핑 완료 ({len(final_mapped)}개 요구사항) - {thinking[:100]}..."

    except Exception as e:
        # LLM 실패 시 기존의 딕셔너리 기반 하드코딩 방식으로 후퇴(Fallback)
        _LAYER_BY_CATEGORY = {
            "Frontend": "Presentation", "Backend": "Application", "Architecture": "Domain",
            "Database": "Infrastructure", "Security": "Infrastructure", "AI/ML": "Domain", "Infrastructure": "Infrastructure"
        }
        final_mapped = []
        for req in rtm:
            fallback_info = _fallback_mapping_info(req)
            layer = _LAYER_BY_CATEGORY.get(req.get("category", ""), fallback_info["layer"])
            final_mapped.append({
                "REQ_ID": req.get("REQ_ID", ""), "layer": layer,
                "description": req.get("description", ""), "depends_on": req.get("depends_on", []) or [],
                "mapping_reason": "LLM 매핑 실패로 휴리스틱 기반 자동 할당",
                "layer_confidence": fallback_info["confidence"],
                "layer_evidence": fallback_info["evidence"],
            })
            
        output = {
            "status": "Warning_Hallucination_Detected",
            "pattern": "Clean Architecture",
            "mapped_requirements": final_mapped,
            "layer_order": ["Presentation", "Application", "Domain", "Infrastructure"],
        }
        thinking_msg = f"LLM 매핑 실패로 Fallback 적용: {str(e)[:150]}"

    return {
        "sa_phase5": output,
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_phase5", "thinking": thinking_msg}],
        "current_step": "sa_phase5_done",
    }