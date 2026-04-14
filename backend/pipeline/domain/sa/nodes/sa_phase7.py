import json
from typing import List
from pydantic import BaseModel, Field
from pipeline.core.state import PipelineState, make_sget
from pipeline.core.utils import call_structured_with_thinking
from version import DEFAULT_MODEL

class InterfaceContract(BaseModel):
    contract_id: str = Field(description="인터페이스 ID (예: IF-REQ-001)")
    layer: str = Field(description="해당 모듈이 속한 계층 (Presentation, Application, Domain, Infrastructure)")
    interface_name: str = Field(description="추상화된 함수명 또는 API 엔드포인트 명칭")
    input_spec: str = Field(description="입력 파라미터 구조 또는 페이로드 명세")
    output_spec: str = Field(description="출력 데이터 구조 및 반환 타입")
    error_handling: str = Field(description="예상되는 주요 예외 처리 방안 (한국어 1문장)")

class Phase7Output(BaseModel):
    thinking: str = Field(default="", description="인터페이스 설계 추론 과정 (3줄 이내)")
    interface_contracts: List[InterfaceContract] = Field(description="각 요구사항에 대응하는 구체적인 인터페이스 명세")
    guardrails: List[str] = Field(description="아키텍처 및 보안 제약 사항 (프로젝트 맞춤형 가이드라인, 3~5개)")

INTERFACE_SYSTEM_PROMPT = """\
당신은 수석 시스템 아키텍트(SA)입니다.
이전 단계에서 확정된 아키텍처 매핑과 보안 경계 설계를 바탕으로, 소프트웨어 모듈 간의 통신 규약(Interface Contract)과 개발 가이드라인을 설계하세요.

[규칙]
1. 각 요구사항(REQ_ID)이 실제로 수행할 기능에 맞춰 구체적인 interface_name, input_spec, output_spec을 설계하세요. (단순 object 타입 지양, 예: input: {user_id: str, vector_data: list[float]})
2. 각 모듈이 속한 계층(layer)의 성격에 맞는 입출력을 정의하세요. (예: Infrastructure는 외부 API 호출 결과 반환, Presentation은 UI 렌더링을 위한 DTO 반환)
3. guardrails는 일반적인 소프트웨어 원칙이 아닌, 제공된 요구사항과 보안 경계에 특화된 구체적인 제약 사항(예: 데이터 흐름 차단 규칙, 특정 레이어 간 통신 제한 등)을 한국어로 작성하세요."""

def sa_phase7_node(state: PipelineState) -> dict:
    sget = make_sget(state)

    phase5 = sget("sa_phase5", {}) or {}
    phase6 = sget("sa_phase6", {}) or {}
    system_scan = sget("system_scan", {}) or {}
    
    mapped_reqs = phase5.get("mapped_requirements", []) or []
    trust_boundaries = phase6.get("trust_boundaries", []) or []
    
    api_key = sget("api_key", "")
    model = sget("model", DEFAULT_MODEL)

    if not mapped_reqs:
        return {
            "sa_phase7": {
                "status": "Needs_Clarification",
                "interface_contracts": [],
                "guardrails": ["매핑된 요구사항이 없어 가드레일을 생성할 수 없습니다."]
            },
            "thinking_log": sget("thinking_log", []) + [{"node": "sa_phase7", "thinking": "매핑된 요구사항 없음 - 인터페이스 설계 생략"}],
            "current_step": "sa_phase7_done",
        }

    functions_by_file: dict[str, list[str]] = {}
    for fn in system_scan.get("sample_functions", []) or []:
        file_path = (fn.get("file") or "").replace("\\", "/").lower()
        func_name = (fn.get("func_name") or "").strip()
        if not file_path or not func_name:
            continue
        functions_by_file.setdefault(file_path, [])
        if func_name not in functions_by_file[file_path]:
            functions_by_file[file_path].append(func_name)

    req_payload = []
    for req in mapped_reqs:
        file_path = (req.get("file_path") or "").replace("\\", "/").lower()
        req_payload.append({
            "REQ_ID": req.get("REQ_ID"),
            "layer": req.get("layer"),
            "desc": req.get("description"),
            "file_path": req.get("file_path") or "",
            "canonical_id": req.get("canonical_id") or "",
            "function_hints": functions_by_file.get(file_path, [])[:5],
        })

    req_summary = json.dumps(req_payload, ensure_ascii=False)
    boundary_summary = json.dumps(trust_boundaries, ensure_ascii=False)

    user_msg = (
        f"=== 아키텍처 매핑 목록 ===\n{req_summary}\n\n"
        f"=== 보안 신뢰 경계 ===\n{boundary_summary}\n\n"
        f"위 구조를 바탕으로 구현 에이전트가 따를 인터페이스 명세(Contracts)와 구조적 가드레일을 설계하세요."
    )

    try:
        result, thinking = call_structured_with_thinking(
            api_key=api_key,
            model=model,
            schema=Phase7Output,
            system_prompt=INTERFACE_SYSTEM_PROMPT,
            user_msg=user_msg,
            max_retries=2
        )
        
        output = {
            "status": "Pass",
            "interface_contracts": [c.model_dump() for c in result.interface_contracts],
            "guardrails": result.guardrails,
        }
        thinking_msg = f"인터페이스 설계 완료: 계약 {len(result.interface_contracts)}개, 가드레일 {len(result.guardrails)}개 생성."
        
    except Exception as e:
        output = {
            "status": "Error",
            "interface_contracts": [
                {
                    "contract_id": f"IF-{req.get('REQ_ID', '')}",
                    "layer": req.get("layer", "application"),
                    "interface_name": "unknown_function",
                    "input_spec": "unknown",
                    "output_spec": "unknown",
                    "error_handling": f"LLM 설계 실패: {e}"
                } for req in mapped_reqs
            ],
            "guardrails": [
                "presentation 레이어는 infrastructure 직접 호출 금지",
                "모든 외부 I/O는 application 인터페이스를 통해 접근"
            ]
        }
        thinking_msg = f"LLM 호출 실패로 Fallback 더미 설계 적용: {e}"

    return {
        "sa_phase7": output,
        "thinking_log": sget("thinking_log", []) + [{"node": "sa_phase7", "thinking": thinking_msg}],
        "current_step": "sa_phase7_done",
    }

