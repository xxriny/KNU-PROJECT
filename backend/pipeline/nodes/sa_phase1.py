import json
import os
from pathlib import Path
from collections import defaultdict
from pydantic import BaseModel, Field
from pipeline.ast_scanner import extract_file_inventory, extract_functions
from pipeline.state import PipelineState, make_sget
from pipeline.utils import call_structured
from version import DEFAULT_MODEL

class SAPhase1LLMOutput(BaseModel):
    thinking: str = Field(default="", description="분석 추론")
    status: str = Field(description="Pass | Needs_Clarification | Fail")
    confidence: float = Field(default=0.7, description="0.0 ~ 1.0")
    architecture_assessment: str = Field(default="", description="구조 평가 요약")
    key_modules: list[str] = Field(default_factory=list, description="핵심 모듈/영역")
    concerns: list[str] = Field(default_factory=list, description="구조적 우려사항")
    recommended_focus: list[str] = Field(default_factory=list, description="다음 단계 분석 포인트")

SYSTEM_PROMPT = """당신은 소프트웨어 아키텍처 분석 전문가입니다.

입력으로 전달된 프로젝트 배경과 코드 함수 요약을 바탕으로 현재 시스템 구조를 평가하세요.

[규칙]
1. 반드시 단일 JSON 객체만 출력하세요.
2. status는 Pass | Needs_Clarification | Fail 중 하나를 선택하세요.
3. architecture_assessment는 프로젝트의 목적과 비교하여 현재 구조가 적절한지 한국어 2~3문장으로 작성하세요.
4. key_modules/concerns/recommended_focus는 각각 1~5개 범위로 간결하게 작성하세요.
5. thinking은 2줄 이내로 작성하세요.
"""


def _safe_read_text(path: Path, limit: int = 200_000) -> str:
    try:
        data = path.read_text(encoding="utf-8", errors="replace")
        return data[:limit]
    except OSError:
        return ""


def _detect_framework_evidence(source_dir: str) -> tuple[list[str], list[dict], dict]:
    """manifest/entrypoint 기반 프레임워크 단서 수집 (LLM 비의존)."""
    frameworks: set[str] = set()
    evidence: list[dict] = []
    coverage = {
        "path_exists": False,
        "manifest_files_found": 0,
        "framework_signals": 0,
    }

    root = Path(source_dir)
    if not source_dir or not root.is_dir():
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


def _build_representative_function_sample(functions: list[dict], max_items: int = 180) -> list[dict]:
    by_file: dict[str, list[dict]] = defaultdict(list)
    for fn in functions:
        file_path = (fn.get("file") or "").strip()
        if file_path:
            by_file[file_path].append(fn)

    sample: list[dict] = []
    for file_path in sorted(by_file.keys()):
        ranked = sorted(
            by_file[file_path],
            key=lambda item: (-len(item.get("docstring", "") or ""), item.get("lineno", 0), item.get("func_name", "")),
        )
        sample.append(ranked[0])

    if len(sample) >= max_items:
        return sample[:max_items]

    seen = {
        ((item.get("file") or ""), item.get("func_name") or "", item.get("lineno") or 0)
        for item in sample
    }
    for fn in functions:
        key = ((fn.get("file") or ""), fn.get("func_name") or "", fn.get("lineno") or 0)
        if key in seen:
            continue
        sample.append(fn)
        seen.add(key)
        if len(sample) >= max_items:
            break

    return sample[:max_items]

def sa_phase1_node(state: PipelineState) -> dict:
    sget = make_sget(state)

    action_type = (sget("action_type", "CREATE") or "CREATE").strip().upper()
    source_dir = (sget("source_dir", "") or "").strip()
    
    # 1. CREATE 모드 방어 로직 (기존 코드가 없으므로 분석 생략)
    if action_type == "CREATE":
        return {
            "sa_phase1": {
                "status": "Skipped",
                "confidence": 1.0,
                "architecture_assessment": "신규 프로젝트(CREATE 모드)로 기존 코드 구조 분석을 생략합니다.",
                "scanned_functions": 0,
                "scanned_files": 0,
                "key_modules": [],
                "concerns": [],
                "recommended_focus": ["초기 아키텍처 설계 및 기술 스택 선정에 집중"]
            },
            "thinking_log": sget("thinking_log", []) + [{"node": "sa_phase1", "thinking": "CREATE 모드 감지. 코드 스캔 스킵."}],
            "current_step": "sa_phase1_done",
        }

    api_key = sget("api_key", "")
    model = sget("model", DEFAULT_MODEL)

    detected_frameworks, framework_evidence, coverage = _detect_framework_evidence(source_dir)

    if not source_dir:
        output = {
            "status": "Needs_Clarification",
            "diagnostic_code": "SOURCE_DIR_MISSING",
            "confidence": 0.4,
            "source_dir": source_dir,
            "scanned_functions": 0,
            "scanned_files": 0,
            "scan_coverage": coverage,
            "languages": {},
            "sample_functions": [],
            "detected_frameworks": detected_frameworks,
            "framework_evidence": framework_evidence,
            "architecture_assessment": "source_dir가 비어 있어 기존 코드 구조 분석을 수행할 수 없습니다.",
            "key_modules": [],
            "concerns": ["분석 대상 디렉터리가 지정되지 않았습니다."],
            "recommended_focus": ["프로젝트 루트를 선택한 뒤 다시 실행하세요."],
        }
        msg = "source_dir 누락으로 sa_phase1 진단 보류"
        return {
            "sa_phase1": output,
            "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_phase1", "thinking": msg}],
            "current_step": "sa_phase1_done",
        }

    if not os.path.isdir(source_dir):
        output = {
            "status": "Needs_Clarification",
            "diagnostic_code": "SOURCE_DIR_INVALID",
            "confidence": 0.4,
            "source_dir": source_dir,
            "scanned_functions": 0,
            "scanned_files": 0,
            "scan_coverage": coverage,
            "languages": {},
            "sample_functions": [],
            "detected_frameworks": detected_frameworks,
            "framework_evidence": framework_evidence,
            "architecture_assessment": "지정한 source_dir 경로가 유효하지 않아 구조 평가를 수행할 수 없습니다.",
            "key_modules": [],
            "concerns": [f"유효하지 않은 source_dir: {source_dir}"],
            "recommended_focus": ["프로젝트 루트를 다시 선택해 주세요."],
        }
        msg = "source_dir 경로가 유효하지 않아 sa_phase1 진단 보류"
        return {
            "sa_phase1": output,
            "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_phase1", "thinking": msg}],
            "current_step": "sa_phase1_done",
        }

    functions = extract_functions(source_dir, max_functions=300)
    file_inventory = extract_file_inventory(source_dir, max_files=600)
    representative_functions = _build_representative_function_sample(functions)

    by_lang = {}
    files = set()
    for fn in functions:
        lang = fn.get("lang", "unknown")
        by_lang[lang] = by_lang.get(lang, 0) + 1
        if fn.get("file"):
            files.add(fn["file"])

    if not functions and not detected_frameworks:
        output = {
            "status": "Needs_Clarification",
            "diagnostic_code": "NO_SCANNABLE_FUNCTIONS",
            "confidence": 0.4,
            "source_dir": source_dir,
            "scanned_functions": 0,
            "scanned_files": 0,
            "scan_coverage": coverage,
            "languages": {},
            "sample_functions": [],
            "file_inventory": [],
            "detected_frameworks": detected_frameworks,
            "framework_evidence": framework_evidence,
            "architecture_assessment": "소스 스캔 결과가 부족하여 구조 평가를 수행할 수 없습니다.",
            "key_modules": [],
            "concerns": ["소스 코드 함수 추출 결과가 없습니다."],
            "recommended_focus": ["프로젝트 루트 또는 source_dir 경로와 파일 확장자 구성을 확인하세요."],
        }
        msg = "함수 추출 결과 및 프레임워크 단서가 없어 sa_phase1 진단 보류"
    else:
        compact = [
            {
                "file": fn.get("file", ""),
                "func_name": fn.get("func_name", ""),
                "lang": fn.get("lang", "unknown"),
                "doc": (fn.get("docstring") or "")[:200],
            }
            for fn in functions[:120]
        ]
        
        # 2. 컨텍스트 기아 해결을 위한 배경 정보 주입
        project_context = sget("project_context", "") or "정보 없음"
        
        # 3. f-string 리스트 변환 버그 해결 (json.dumps 사용)
        user_msg = (
            f"## 프로젝트 배경 (Context)\n{project_context}\n\n"
            f"## source_dir\n{source_dir}\n\n"
            f"## scanned_stats\n"
            f"- scanned_functions: {len(functions)}\n"
            f"- scanned_files: {len(files)}\n"
            f"- languages: {by_lang}\n\n"
            f"## framework_signals\n"
            f"- detected_frameworks: {json.dumps(detected_frameworks, ensure_ascii=False)}\n"
            f"- framework_evidence: {json.dumps(framework_evidence, ensure_ascii=False)}\n"
            f"- scan_coverage: {json.dumps(coverage, ensure_ascii=False)}\n\n"
            f"## function_samples\n{json.dumps(compact, ensure_ascii=False, indent=2)}"
        )

        try:
            llm_result = call_structured(
                api_key=api_key,
                model=model,
                schema=SAPhase1LLMOutput,
                system_prompt=SYSTEM_PROMPT,
                user_msg=user_msg,
            )
            result = llm_result.parsed
            output = {
                "status": result.status,
                "diagnostic_code": "",
                "confidence": result.confidence,
                "source_dir": source_dir,
                "scanned_functions": len(functions),
                "scanned_files": len(files),
                "scan_coverage": coverage,
                "languages": by_lang,
                "sample_functions": representative_functions,
                "sample_files_count": len({fn.get("file") for fn in representative_functions if fn.get("file")}),
                "file_inventory": file_inventory,
                "detected_frameworks": detected_frameworks,
                "framework_evidence": framework_evidence,
                "architecture_assessment": result.architecture_assessment,
                "key_modules": result.key_modules,
                "concerns": result.concerns,
                "recommended_focus": result.recommended_focus,
            }
            msg = f"기존 코드 구조 분석 완료 ({result.status})"
        except Exception as e:
            # Fallback 로직 유지...
            output = {
                "status": "Needs_Clarification",
                "diagnostic_code": "LLM_ANALYSIS_FAILED",
                "confidence": 0.5,
                "source_dir": source_dir,
                "scanned_functions": len(functions),
                "scanned_files": len(files),
                "scan_coverage": coverage,
                "languages": by_lang,
                "sample_functions": representative_functions,
                "sample_files_count": len({fn.get("file") for fn in representative_functions if fn.get("file")}),
                "file_inventory": file_inventory,
                "detected_frameworks": detected_frameworks,
                "framework_evidence": framework_evidence,
                "architecture_assessment": "LLM 분석이 실패해 통계 기반 결과로 대체했습니다.",
                "key_modules": sorted(list(files))[:10],
                "concerns": [f"LLM 호출 실패: {str(e)[:200]}"],
                "recommended_focus": ["API 키/모델 설정을 확인한 뒤 재실행하세요."],
            }
            msg = "기존 코드 구조 분석 완료 (통계 기반 폴백)"

    return {
        "sa_phase1": output,
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_phase1", "thinking": msg}],
        "current_step": "sa_phase1_done",
    }

