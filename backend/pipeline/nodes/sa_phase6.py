import json
from typing import List
from pydantic import BaseModel, Field
from pipeline.node_base import pipeline_node, NodeContext
from pipeline.utils import call_structured_with_thinking


class RoleDefinition(BaseModel):
    role_name: str = Field(description="역할 명칭 (예: Anonymous, FreeUser, ProUser, B2BClient, SystemAdmin 등)")
    description: str = Field(description="해당 역할의 정의 및 권한 수준 (한국어)")

class AuthzMatrixItem(BaseModel):
    req_id: str = Field(description="요구사항 ID")
    allowed_roles: List[str] = Field(description="접근이 허용된 역할(role_name) 목록")
    restriction_level: str = Field(description="Public | Authenticated | Authorized (특정 권한 필요) | InternalOnly")

class TrustBoundary(BaseModel):
    boundary_name: str = Field(description="경계 명칭 (예: Client-Server, Server-DB, Internal-ExternalAPI, OnDevice-Cloud)")
    crossing_data: str = Field(description="이 경계를 넘어가는 주요 데이터 (예: 사용자의 평문 개인정보, 암호화된 벡터 등)")
    security_controls: str = Field(description="이 경계에 적용해야 할 보안 통제 방안 (한국어 1~2문장)")

class SecurityDesignOutput(BaseModel):
    thinking: str = Field(default="", description="보안 설계 추론 과정 (3줄 이내)")
    defined_roles: List[RoleDefinition] = Field(description="프로젝트 요구사항에서 도출된 역할 계층")
    authz_matrix: List[AuthzMatrixItem] = Field(description="요구사항별 권한 인가 매핑")
    trust_boundaries: List[TrustBoundary] = Field(description="시스템의 주요 신뢰 경계 및 통제 방안")

SECURITY_SYSTEM_PROMPT = """\
당신은 소프트웨어 보안 아키텍트입니다.
제공된 요구사항(RTM)과 아키텍처 매핑 정보를 분석하여, 시스템의 권한 계층(RBAC)과 신뢰 경계(Trust Boundaries)를 설계하세요.

[규칙]
1. 요구사항을 깊이 분석하여 시스템에 실제로 필요한 역할(Role)들을 도출하세요. (무료/유료 사용자, 관리자, 외부 시스템 등 비즈니스 요구사항에 맞게 세분화)
2. 각 요구사항(REQ_ID)을 실행하기 위해 어떤 역할의 권한이 필요한지 매핑하세요.
3. 시스템 내부와 외부(사용자 기기, 외부 API, 데이터베이스 등) 간의 신뢰 경계를 정의하고 보호 방안을 마련하세요. 특히 개인정보 보호나 On-Device 처리와 관련된 요구사항이 있다면 이를 경계 설계에 엄격히 반영하세요."""


@pipeline_node("sa_phase6")
def sa_phase6_node(ctx: NodeContext) -> dict:
    action_type = ctx.sget("action_type", "CREATE")

    if action_type == "CREATE":
        return {
            "sa_phase6": {
                "status": "Skipped",
                "defined_roles": [],
                "rbac_roles": [],
                "authz_matrix": [],
                "trust_boundaries": [],
                "notes": "CREATE 모드: 초기 보안 설계 생략 가능 단계"
            },
            "_thinking": "CREATE 모드 감지. 보안 설계 스킵(선택적).",
        }

    phase5 = ctx.sget("sa_phase5", {}) or {}
    mapped_reqs = phase5.get("mapped_requirements", []) or []

    if not mapped_reqs:
        return {
            "sa_phase6": {
                "status": "Needs_Clarification",
                "defined_roles": [],
                "rbac_roles": [],
                "authz_matrix": [],
                "trust_boundaries": []
            },
            "_thinking": "매핑된 요구사항이 없어 보안 설계 생략",
        }

    req_summary = json.dumps(
        [{"REQ_ID": r.get("REQ_ID"), "layer": r.get("layer"), "desc": r.get("description")} for r in mapped_reqs],
        ensure_ascii=False
    )

    user_msg = f"다음 아키텍처 매핑 결과를 바탕으로 시스템 권한 및 보안 경계를 설계하세요:\n```json\n{req_summary}\n```"

    try:
        result, thinking = call_structured_with_thinking(
            api_key=ctx.api_key,
            model=ctx.model,
            schema=SecurityDesignOutput,
            system_prompt=SECURITY_SYSTEM_PROMPT,
            user_msg=user_msg,
            max_retries=2
        )

        return {
            "sa_phase6": {
                "status": "Pass",
                "defined_roles": [r.model_dump() for r in result.defined_roles],
                "rbac_roles": [r.role_name for r in result.defined_roles],
                "authz_matrix": [m.model_dump() for m in result.authz_matrix],
                "trust_boundaries": [t.model_dump() for t in result.trust_boundaries],
            },
            "_thinking": f"보안 설계 완료: 역할 {len(result.defined_roles)}개, 신뢰 경계 {len(result.trust_boundaries)}개 도출.",
        }

    except Exception as e:
        return {
            "sa_phase6": {
                "status": "Error",
                "defined_roles": [{"role_name": "admin", "description": "시스템 관리자"}, {"role_name": "user", "description": "일반 사용자"}],
                "rbac_roles": ["admin", "user"],
                "authz_matrix": [{"req_id": r.get("REQ_ID", ""), "allowed_roles": ["admin", "user"], "restriction_level": "Authenticated"} for r in mapped_reqs],
                "trust_boundaries": [],
                "error_msg": f"LLM 설계 실패로 기본값 적용: {e}"
            },
            "_thinking": f"LLM 호출 실패로 Fallback 적용: {e}",
        }

