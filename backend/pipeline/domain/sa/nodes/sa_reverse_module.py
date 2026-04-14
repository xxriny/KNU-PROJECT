"""SA Phase 5 — Reverse Engineering 모드 모듈 프로파일링 및 레이블링"""

import json
from collections import defaultdict

from pipeline.core.utils import call_structured_with_thinking
from version import DEFAULT_MODEL

from .sa_phase5_schemas import ModuleLabelBatchOutput, MODULE_LABEL_SYSTEM_PROMPT
from .sa_layer_heuristics import (
    normalize_module_path,
    canonical_module_id,
    scoped_frameworks_for_module,
    score_layers,
)

MAX_REVERSE_MODULES = 120


def build_reverse_module_profiles(system_scan: dict) -> list[dict]:
    """system_scan 스캔 결과에서 모듈 프로파일 리스트를 구축한다."""
    sample_functions = system_scan.get("sample_functions", []) or []
    key_modules = system_scan.get("key_modules", []) or []
    file_inventory = system_scan.get("file_inventory", []) or []
    detected_frameworks = system_scan.get("detected_frameworks", []) or []
    framework_evidence = system_scan.get("framework_evidence", []) or []

    functions_by_file: dict[str, list[dict]] = defaultdict(list)
    for fn in sample_functions:
        file_path = (fn.get("file") or "").strip()
        normalized = normalize_module_path(file_path)
        if not normalized:
            continue
        functions_by_file[normalized].append(fn)

    profiles_by_file: dict[str, dict] = {}
    for item in file_inventory:
        display_file = (item.get("file") or "").strip().replace("\\", "/")
        file_path = normalize_module_path(display_file)
        if not file_path:
            continue
        profiles_by_file.setdefault(
            file_path,
            {
                "module_name": display_file or file_path,
                "description": f"핵심 분석 모듈: {display_file or file_path}",
                "file_path": file_path,
                "canonical_id": canonical_module_id(file_path),
                "language": item.get("lang", ""),
                "functions": list(functions_by_file.get(file_path, [])),
                "frameworks": scoped_frameworks_for_module(file_path, item.get("lang", ""), detected_frameworks, framework_evidence),
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
            "canonical_id": canonical_module_id(normalized),
            "language": language,
            "functions": list(functions),
            "frameworks": scoped_frameworks_for_module(normalized, language, detected_frameworks, framework_evidence),
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
        normalized = normalize_module_path(name)
        cid = canonical_module_id(normalized)
        if not normalized or cid in seen_canonical:
            continue
        language = "javascript" if any(token in name.lower() for token in ["react", "electron", "frontend"]) else "python"
        profiles.append(
            {
                "module_name": name,
                "description": f"핵심 분석 모듈: {name}",
                "file_path": normalized,
                "canonical_id": cid,
                "language": language,
                "functions": [],
                "frameworks": scoped_frameworks_for_module(name, language, detected_frameworks, framework_evidence),
                "imports": [],
                "raw_imports": [],
                "function_count": 0,
                "source_kind": "key_module",
                "is_entrypoint": False,
            }
        )
        seen_canonical.add(cid)

    profiles.sort(
        key=lambda profile: (
            not profile.get("is_entrypoint", False),
            -int(profile.get("function_count", 0) or len(profile.get("functions", []))),
            profile.get("file_path", "") or profile.get("module_name", ""),
        )
    )
    return profiles[:MAX_REVERSE_MODULES]


def batch_label_modules(profiles: list[dict], api_key: str, model: str) -> dict[str, str]:
    """단일 배치 LLM 호출로 모듈별 기능명 레이블 맵을 반환. 실패 시 빈 dict."""
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


def build_reverse_module_mapping(system_scan: dict, *, api_key: str = "", model: str = DEFAULT_MODEL) -> list[dict]:
    """REVERSE 모드: system_scan 스캔 결과를 아키텍처 매핑 리스트로 변환."""
    profiles = build_reverse_module_profiles(system_scan)
    label_map = batch_label_modules(profiles, api_key, model)

    mapped = []
    for index, profile in enumerate(profiles, start=1):
        layer, confidence, evidence = score_layers(
            module_name=profile["module_name"],
            description=profile["description"],
            language=profile.get("language", ""),
            frameworks=profile.get("frameworks", []),
            functions=profile.get("functions", []),
        )
        cid = profile.get("canonical_id") or canonical_module_id(profile.get("module_name", ""))
        functional_name = label_map.get(cid, "")
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
            "file_path": profile.get("file_path") or normalize_module_path(profile.get("module_name", "")),
            "canonical_id": cid,
            "source_kind": profile.get("source_kind", "code_scan"),
            "import_hints": profile.get("imports", []) or [],
            "raw_import_hints": profile.get("raw_imports", []) or [],
        })
    return mapped
