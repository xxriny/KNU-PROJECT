"""
Stack Planner Node
분석된 요구사항(Features)을 승인된 기술 스택(RAG)과 매핑하여 기술 설계를 확정합니다.
"기술 스택 가디언" 페르소나를 사용하여 프로젝트의 기술적 일관성을 책임집니다.
"""

from typing import List, Dict, Any, Optional
from pipeline.core.state import PipelineState, make_sget
from pipeline.core.utils import call_structured_with_usage
from pipeline.domain.pm.schemas import StackPlannerOutput
from observability.logger import get_logger
from version import DEFAULT_MODEL

logger = get_logger()

STACK_PLANNER_SYSTEM_PROMPT = """당신은 프로젝트의 기술적 일관성을 책임지는 '스택 설계자'이자 '기술 스택 가디언'입니다.
Requirement Analyzer가 넘겨준 기능 목록에 대해, 제공된 'STACK_RAG' 컨텍스트 안에서만 기술을 선택합니다.

[핵심 규칙]
1. RAG 컨텍스트(approved_stacks)에 없는 라이브러리는 절대로 추천하지 마세요.
2. 특정 기능에 꼭 필요한 라이브러리가 RAG에 없다면, 해당 항목의 status를 'PENDING_CRAWL' 상태로 마킹하세요. 이것은 가디언 노드의 개입을 요청하는 신호입니다.
3. 동일한 도메인(예: Frontend) 내에서는 반드시 동일한 상태 관리/스타일 라이브러리를 사용하도록 강제하세요. 기능마다 다른 라이브러리를 쓰면 안 됩니다.
4. 각 선택에 대해 'reason' 필드에 명확한 기술적 근거(RAG 매핑 이유 등)를 기술하세요.
5. 'PENDING_CRAWL' 상태인 항목은 반드시 'suggested_query' 필드에 크롤러가 NPM이나 PyPI에서 즉시 조회할 수 있는 **정확한 단일 패키지 영문명(Exact Package Name)**을 추론하여 기입하세요. 절대 문장형으로 작성하면 안 됩니다.
   - ❌ 나쁜 예 (문장형): "React 환경에서 사용 가능한 실시간 차트 라이브러리 추천", "고성능 시계열 데이터베이스"
   - ⭕ 좋은 예 (패키지명): "recharts", "lightweight-charts", "influxdb", "timescaledb"
"""

def stack_planner_node(state: PipelineState) -> Dict[str, Any]:
    sget = make_sget(state)
    logger.info("=== [Node Entry] stack_planner_node ===")
    logger.info(f"Input Keys: {list(state.keys()) if hasattr(state, 'keys') else 'N/A'}")
    
    # 1. 루프 횟수 관리
    current_loop = sget("loop_count", 0)
    
    # 2. 입력 데이터 준비
    features = sget("features", [])
    
    # RAG 컨텍스트: 기본 컨텍스트 + 이전 루프에서 수집된 새로운 지식들
    base_rag_context = sget("stack_rag_context", "No approved stacks found in RAG.")
    
    # 이전 루프의 성공적인 가디언 승인 데이터가 있다면 컨텍스트에 추가
    guardian_out = sget("guardian_output", {})
    new_knowledge = ""
    if guardian_out.get("status") == "APPROVED" and guardian_out.get("final_data"):
        data = guardian_out["final_data"]
        new_knowledge = f"\n[NEWLY DISCOVERED] {data['name']}: {data['description']} (v{data['version']}, License: {data['license']})"
    
    integrated_context = base_rag_context + new_knowledge
    
    if not features:
        return {
            "stack_planner_output": {"thinking": "No features.", "stack_mapping": []},
            "loop_count": current_loop + 1
        }

    # 3. LLM 호출
    user_msg = f"""### [요구사항 기능 목록]
{features}

### [APPROVED_STACK_FROM_RAG]
{integrated_context}

위 기능들을 구현하기 위해 최적의 기술 스택을 매핑하세요. 
만약 새로 발견된(NEWLY DISCOVERED) 기술이 있다면 적극적으로 활용하세요.
"""

    try:
        out, usage = call_structured_with_usage(
            api_key=sget("api_key", ""),
            model=sget("model", DEFAULT_MODEL),
            schema=StackPlannerOutput,
            system_prompt=STACK_PLANNER_SYSTEM_PROMPT,
            user_msg=user_msg,
            temperature=0.1
        )
        
        thinking_msg = out.thinking
        
        # 4. 회귀 로직을 위한 크롤러 입력 생성 (사용자 제안 반영)
        pending_items = [m for m in out.stack_mapping if m.status == "PENDING_CRAWL"]
        next_crawler_inputs = []
        for item in pending_items:
            next_crawler_inputs.append({
                "target": "npm" if item.domain == "Frontend" else "pypi",
                "query": item.suggested_query or item.package
            })

        return {
            "stack_planner_output": out.model_dump(),
            "next_crawler_inputs": next_crawler_inputs, # 이 데이터를 가지고 Crawling 노드로 회귀
            "loop_count": current_loop + 1,
            "stack_rag_context": integrated_context, 
            "thinking_log": (sget("thinking_log", []) or []) + [{"node": "stack_planner", "thinking": thinking_msg}]
        }
        
    except Exception as e:
        logger.exception("stack_planner_node failure")
        return {
            "stack_planner_output": {
                "thinking": f"오류 발생: {str(e)}",
                "stack_mapping": []
            }
        }
