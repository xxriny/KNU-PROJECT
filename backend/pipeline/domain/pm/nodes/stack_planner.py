"""
Stack Planner Node
분석된 요구사항(Features)을 승인된 기술 스택(RAG)과 매핑하여 기술 설계를 확정합니다.
"기술 스택 가디언" 페르소나를 사용하여 프로젝트의 기술적 일관성을 책임집니다.
"""

from typing import List, Dict, Any, Optional
from pipeline.core.state import PipelineState, make_sget
from pipeline.core.utils import call_structured
from pipeline.domain.pm.schemas import StackPlannerOutput
from observability.logger import get_logger
from version import DEFAULT_MODEL

logger = get_logger()

STACK_PLANNER_SYSTEM_PROMPT = """# 역할: 기술 경제학자 (YAGNI / 최소 권한 원칙)
## 목표: 프로젝트 규모(SCALE)에 맞는 최적/최소의 기술 스택 선정.
## 규칙:
1. 규모 판단: Tiny | Medium | Enterprise 중 선택.
2. 오버엔지니어링 금지: 단순 앱에 DB/서버/무거운 상태관리 도입 시 감점.
3. RAG 준수: 제공된 컨텍스트 내 기술 우선 검색. 없으면 'PENDING_CRAWL'.
4. 논리적 근거: 왜 더 간단한 대안 대신 이 기술을 택했는지 설명.
## 예시:
- 시나리오: "단순 정적 블로그"
  - ❌ Bad: MSA + Kafka + K8s (YAGNI 위반).
  - ✅ Good: Next.js + Supabase/SQLite (규모 적합).
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
        res = call_structured(
            api_key=sget("api_key", ""),
            model=sget("model", DEFAULT_MODEL),
            schema=StackPlannerOutput,
            system_prompt=STACK_PLANNER_SYSTEM_PROMPT,
            user_msg=user_msg,
        )
        out = res.parsed
        retry_count = res.retry_count
        thinking_msg = out.th
        
        # 4. 회귀 로직을 위한 크롤러 입력 생성 (사용자 제안 반영)
        pending_items = [item for item in out.m if item.status == "PENDING_CRAWL"]
        next_crawler_inputs = []
        for item in pending_items:
            next_crawler_inputs.append({
                "target": "npm" if item.dom == "Frontend" else "pypi",
                "query": item.query or item.pkg
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
