from __future__ import annotations
from pipeline.core.state import PipelineState, make_sget
from pipeline.core.node_base import pipeline_node, NodeContext
from pipeline.core.utils import call_structured
from pipeline.domain.sa.schemas import DataModelerOutput

SYSTEM_PROMPT = """
당신은 시스템의 데이터 혈맥을 설계하는 '수석 DB 스키마 아키텍트'입니다.
Gemini 2.5 Flash 모델로서, 다음의 **표준 명칭 사전**과 **설계 원칙**을 엄격히 준수하십시오.

[1. 필수 표준 명칭 사전 (Naming Dictionary)]
- 모든 테이블의 기본 키: `id` (uuid)
- 유저 식별자 외래키: `user_id` (uuid)
- 인증 토큰: `access_token`, `refresh_token` (string)
- 생성/수정일: `created_at`, `updated_at` (timestamp)
- 모든 명칭은 **snake_case**만 허용합니다. (예: userId -> user_id)

[2. 핵심 설계 규칙]
1. **타입 매핑 엄격 적용**: API나 컴포넌트에서 배열이나 객체로 전달되는 복합 데이터 필드는 반드시 `JSONB` 또는 배열(Array) 타입으로 명시하십시오. (dict/객체 -> JSONB)
2. **식별자 명시**: 모든 PK/FK는 `UUID` 타입을 명시하십시오. 자체 PK(id)가 대상 엔티티를 식별할 수 있는 경우 불필요한 참조 ID(예: item_id)를 중복 정의하지 마십시오.
3. **참조 무결성**: 외래키(`_id`로 끝나는 필드)를 정의할 때는 반드시 대응하는 테이블이 함께 설계되어야 합니다.
4. **상태 동기화**: API 설계의 타임스탬프 필드와 DB의 created_at/updated_at 명칭을 일치시키거나 매핑을 명확히 하십시오.

출력 데이터 규격 (JSON):
{
  "thinking": "컴포넌트 및 API 명세를 바탕으로 한 DB 스키마 도출 및 타입 최적화 과정",
  "tables": [
    {
      "table_name": "users",
      "columns": [{"name": "id", "type": "uuid"}, {"name": "metadata", "type": "jsonb"}]
    }
  ]
}
"""

def _to_compact_text(items: list[dict]) -> str:
    if not items: return "없음"
    return "\n".join("- " + ", ".join(f"{k}: {v}" for k, v in item.items() if v) for item in items)

def _build_user_message(components: list, apis: list) -> str:
    pruned_components = _to_compact_text([{"name": c.get("component_name"), "role": c.get("role")} for c in components])
    pruned_apis = _to_compact_text([{"endpoint": a.get("endpoint"), "request": str(a.get("request_schema")), "response": str(a.get("response_schema"))} for a in apis])
    
    return f"\n[Component Design]\n{pruned_components}\n\n[API Specifications]\n{pruned_apis}"

from observability.logger import get_logger

logger = get_logger()

@pipeline_node("db_schema_architect")
def db_schema_architect_node(ctx: NodeContext) -> dict:
    sget = ctx.sget
    logger.info("=== [Node Entry] db_schema_architect_node ===")
    components = sget("component_scheduler_output", {}).get("components", [])
    apis = sget("api_modeler_output", {}).get("apis", [])

    user_content = _build_user_message(components, apis)
    
    res = call_structured(
        api_key=ctx.api_key,
        model=ctx.model,
        schema=DataModelerOutput,
        system_prompt=SYSTEM_PROMPT,
        user_msg=user_content,
        compress_prompt=False
    )
    
    output = res.parsed
    thinking_msg = output.thinking or "DB 스키마 모델링 완료"
    
    return {
        "db_schema_architect_output": output.model_dump(),
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "db_schema_architect", "thinking": thinking_msg}],
        "current_step": "db_schema_architect_done"
    }
