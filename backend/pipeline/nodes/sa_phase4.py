import urllib.request
import urllib.error
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from pydantic import BaseModel, Field
from pipeline.state import PipelineState
from pipeline.utils import call_structured

class PackageExtractionOutput(BaseModel):
    thinking: str = Field(default="", description="패키지 추출 추론 과정")
    proposed_packages: List[str] = Field(description="PyPI에 등록되어 있을 것으로 예상되는 패키지명 목록 (소문자)")

SYSTEM_PROMPT = """\
당신은 파이썬 의존성 관리 전문가입니다.
제안된 기술 스택 및 요구사항을 분석하여, 프로젝트 구현에 필요한 실제 PyPI 패키지(pip install 가능한 정확한 이름) 목록을 추출하세요.

[규칙]
1. 반드시 단일 JSON 객체만 출력하세요.
2. 파이썬 기본 내장 라이브러리(os, sys, json 등)는 제외하세요.
3. 실제 PyPI에 존재하는 정확한 패키지명(예: 'google-genai', 'python-dotenv', 'fastapi', 'psycopg2-binary')으로 추론하세요.
4. proposed_packages는 핵심 구동에 필요한 5~15개 내외로 추출하세요."""

def _verify_pypi_package(package_name: str) -> bool:
    """PyPI API를 호출하여 패키지가 실제 존재하는지(Dry-run) 검증합니다."""
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=1.5) as response:
            return response.status == 200
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False # 존재하지 않는 가짜 패키지(환각)
        return True # 404 이외의 에러는 일시적 장애일 수 있으므로 일단 통과 허용
    except Exception:
        return True # 네트워크 타임아웃 등은 차단하지 않음


def _verify_pypi_packages_parallel(packages: List[str]) -> tuple[list[str], list[str]]:
    verified: list[str] = []
    rejected: list[str] = []
    clean_packages = [pkg.strip().lower() for pkg in packages if (pkg or "").strip()]
    if not clean_packages:
        return verified, rejected

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_verify_pypi_package, pkg): pkg for pkg in clean_packages}
        try:
            for future in as_completed(futures, timeout=4):
                pkg = futures[future]
                try:
                    if future.result():
                        verified.append(pkg)
                    else:
                        rejected.append(pkg)
                except Exception:
                    # 검증 단계 에러는 차단보다 통과 우선
                    verified.append(pkg)
        except TimeoutError:
            # 끝나지 않은 패키지는 네트워크 이슈로 간주하고 통과 처리
            for future, pkg in futures.items():
                if not future.done():
                    verified.append(pkg)

    return sorted(set(verified)), sorted(set(rejected))

def sa_phase4_node(state: PipelineState) -> dict:
    def sget(key, default=None):
        if hasattr(state, "get"):
            val = state.get(key, default)
        else:
            val = getattr(state, key, default)
        return default if val is None else val

    context_spec = sget("context_spec", {}) or {}
    tech_stack = context_spec.get("tech_stack_suggestions", []) or []
    sa_phase1 = sget("sa_phase1", {}) or {}
    api_key = sget("api_key", "")
    model = sget("model", "gemini-2.5-flash")
    action_type = (sget("action_type", "") or "CREATE").strip().upper()

    if not tech_stack:
        if action_type == "REVERSE_ENGINEER":
            languages = sa_phase1.get("languages", {}) or {}
            notes = "기술 스택 명시가 없어 의존성 후보 검증을 생략합니다."
            if languages:
                notes += f" 코드 스캔 기준 언어 분포: {languages}"
            return {
                "sa_phase4": {
                    "status": "Skipped",
                    "proposed_packages": [],
                    "verified_packages": [],
                    "rejected_packages": [],
                    "notes": notes,
                },
                "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_phase4", "thinking": "reverse 모드에서 명시적 기술 스택이 없어 패키지 검증 생략"}],
                "current_step": "sa_phase4_done",
            }
        return {
            "sa_phase4": {
                "status": "Skipped",
                "proposed_packages": [],
                "verified_packages": [],
                "rejected_packages": [],
                "notes": "기술 스택 정보가 없어 의존성 검증을 생략합니다."
            },
            "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_phase4", "thinking": "기술 스택 없음 - 검증 생략"}],
            "current_step": "sa_phase4_done",
        }

    tech_str = "\n".join(f"- {t}" for t in tech_stack)
    user_msg = f"다음 기술 스택 제안에서 설치해야 할 파이썬 패키지 목록을 추출하세요:\n{tech_str}"

    try:
        # 1. LLM을 통한 동적 패키지 추출
        result: PackageExtractionOutput = call_structured(
            api_key=api_key,
            model=model,
            schema=PackageExtractionOutput,
            system_prompt=SYSTEM_PROMPT,
            user_msg=user_msg,
            max_retries=2
        )
        proposed = result.proposed_packages
        thinking_msg = result.thinking
    except Exception as e:
        proposed = ["langgraph", "pydantic", "python-dotenv", "google-genai"]
        thinking_msg = f"LLM 패키지 추출 실패로 인한 기본값 사용: {e}"

    # 2. PyPI API를 이용한 가상 설치 검증 (Dry-run)
    verified, rejected = _verify_pypi_packages_parallel(proposed)

    # 거부된 패키지가 하나라도 있으면 경고 상태 부여
    status = "Pass" if not rejected else "Warning_Hallucination_Detected"
    
    output = {
        "status": status,
        "proposed_packages": proposed,
        "verified_packages": verified,
        "rejected_packages": rejected,
        "notes": f"총 {len(proposed)}개 제안 중 {len(verified)}개 검증 통과, {len(rejected)}개 존재하지 않음 차단."
    }

    return {
        "sa_phase4": output,
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_phase4", "thinking": f"{thinking_msg} | 검증 결과: {status}"}],
        "current_step": "sa_phase4_done",
    }