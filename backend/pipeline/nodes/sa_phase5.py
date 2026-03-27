import json
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


def _infer_layer_from_path(module_name: str) -> str:
    name = (module_name or "").lower()
    if any(token in name for token in ["view", "page", "screen", "component", "ui", "route", "controller", "api"]):
        return "Presentation"
    if any(token in name for token in ["domain", "entity", "model", "core", "rule"]):
        return "Domain"
    if any(token in name for token in ["db", "repo", "client", "infra", "storage", "auth", "config", "adapter"]):
        return "Infrastructure"
    return "Application"


def _build_reverse_module_mapping(sa_phase1: dict) -> list[dict]:
    sample_functions = sa_phase1.get("sample_functions", []) or []
    key_modules = sa_phase1.get("key_modules", []) or []

    modules = []
    seen = set()
    for fn in sample_functions:
        file_path = (fn.get("file") or "").strip()
        if not file_path or file_path in seen:
            continue
        seen.add(file_path)
        modules.append(file_path)
        if len(modules) >= 8:
            break

    for module in key_modules:
        name = (module or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        modules.append(name)
        if len(modules) >= 8:
            break

    mapped = []
    for index, module_name in enumerate(modules, start=1):
        mapped.append({
            "REQ_ID": f"MOD-{index:03d}",
            "layer": _infer_layer_from_path(module_name),
            "description": f"핵심 분석 모듈: {module_name}",
            "depends_on": [],
            "mapping_reason": "reverse 모드에서 코드 스캔 결과를 기반으로 핵심 모듈을 계층별로 분류했습니다.",
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
            reverse_mapping = _build_reverse_module_mapping(sa_phase1)
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
            mapping_info = mapped_dict.get(req_id, {"layer": "Application", "reason": "매핑 누락으로 인한 기본값 할당"})
            
            final_mapped.append({
                "REQ_ID": req_id,
                "layer": mapping_info["layer"],
                "description": req.get("description", ""),
                "depends_on": req.get("depends_on", []) or [],
                "mapping_reason": mapping_info["reason"]
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
            layer = _LAYER_BY_CATEGORY.get(req.get("category", ""), "Application")
            final_mapped.append({
                "REQ_ID": req.get("REQ_ID", ""), "layer": layer,
                "description": req.get("description", ""), "depends_on": req.get("depends_on", []) or [],
                "mapping_reason": "LLM 매핑 실패로 카테고리 기반 자동 할당"
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