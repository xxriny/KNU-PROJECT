"""
SA Test Analysis Node
SA 설계 산출물(컴포넌트/API/DB)을 입력으로 받아 SE 관점의 테스트 전략을 분석합니다.
테스트 코드를 생성하지 않으며, "어떻게 검증할 것인가"에 대한 전략 문서를 생성합니다.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from pipeline.core.node_base import pipeline_node, NodeContext
from pipeline.core.utils import call_structured
from pipeline.domain.sa.schemas import SATestAnalysisOutput
from observability.logger import get_logger

logger = get_logger()

SYSTEM_PROMPT = """# Role: Software Engineering Test Strategist

## Goal
Analyze the given software architecture (components, APIs, DB tables) and produce a comprehensive
test strategy from a Software Engineering perspective. You do NOT generate test code — only strategy.

## Analysis Layers

### 1. Risk Zone Classification
For each component, assess risk level (critical/high/medium/low) based on:
- External integrations (payment, auth, 3rd-party APIs) → critical
- Core business logic with complex state → high
- CRUD services with DB → medium
- Utility/config → low

### 2. Unit Test Strategy
Per component: identify key behavioral invariants, what to mock/stub, and boundary/edge cases.
Focus on isolation — what must be decoupled from infrastructure.

### 3. Integration Test Strategy
Per API endpoint: specify DB approach (TestContainers vs in-memory), transaction scenarios,
and contract pairs for inter-service communication.

### 4. System Test Strategy
Based on component dependency graph: identify critical execution paths, SLA targets, and
chaos/failure injection scenarios (circuit breaker, DB disconnect, pod kill).

### 5. Acceptance Test (BDD)
Convert each RTM FEAT_ID into Given-When-Then format. Include at least one edge case per feature.

## Output Rules
- thinking (th): Reasoning about architecture risk profile and test philosophy (Korean)
- test_philosophy (tp): 1-2 sentence overall test philosophy for this architecture
- risk_zones (rz): Risk classification per component
- unit_specs (us): Unit test strategy per component
- integration_specs (is_): Integration test strategy per API endpoint
- system_specs (ss): System-level critical path + chaos scenarios
- acceptance_specs (as_): BDD specs per RTM FEAT_ID
- test_data_strategy (td): How to manage test data (Faker, fixtures, DB rollback, etc.)
- automation_priority (ap): Ordered list of what to automate first and why
"""


def _build_user_msg(sa_bundle: dict, rtm: list, action_type: str) -> str:
    data = sa_bundle.get("data", {})
    components = data.get("components", [])
    apis = data.get("apis", [])
    tables = data.get("tables", [])

    components_text = json.dumps(components, ensure_ascii=False, indent=2)[:3000]
    apis_text = json.dumps(apis, ensure_ascii=False, indent=2)[:2000]
    tables_text = json.dumps(tables, ensure_ascii=False, indent=2)[:1500]
    rtm_text = json.dumps(rtm[:20], ensure_ascii=False, indent=2)[:2000]

    return (
        f"## Action Type: {action_type}\n\n"
        f"## Components ({len(components)}개)\n```json\n{components_text}\n```\n\n"
        f"## APIs ({len(apis)}개)\n```json\n{apis_text}\n```\n\n"
        f"## DB Tables ({len(tables)}개)\n```json\n{tables_text}\n```\n\n"
        f"## Requirements RTM ({len(rtm)}개)\n```json\n{rtm_text}\n```\n\n"
        "위 아키텍처를 기반으로 소프트웨어 공학 관점의 테스트 전략을 분석하세요."
    )


@pipeline_node("sa_test_analysis")
def sa_test_analysis_node(ctx: NodeContext) -> dict:
    sget = ctx.sget
    logger.info("=== [Node Entry] sa_test_analysis_node ===")

    sa_bundle = sget("sa_arch_bundle", {}) or {}
    merged_project = sget("merged_project", {}) or {}
    rtm = (merged_project.get("plan", {}) or {}).get("requirements_rtm", []) or []
    action_type = sget("action_type", "CREATE")

    if not sa_bundle:
        logger.warning("[sa_test_analysis] sa_arch_bundle이 비어 있어 스킵합니다.")
        return {"current_step": "sa_test_analysis_done"}

    user_msg = _build_user_msg(sa_bundle, rtm, action_type)

    res = call_structured(
        schema=SATestAnalysisOutput,
        system_prompt=SYSTEM_PROMPT,
        user_msg=user_msg,
        ctx=ctx,
        compress_prompt=False,
        temperature=0.0,
    )

    if not res.parsed:
        logger.warning("[sa_test_analysis] LLM 파싱 실패, 빈 결과 반환")
        return {"current_step": "sa_test_analysis_done"}

    output_dict = res.parsed.model_dump()

    # sa_arch_bundle에 test_strategy 병합
    sa_bundle.setdefault("data", {})["test_strategy"] = output_dict
    logger.info(f"[sa_test_analysis] 완료: risk_zones={len(res.parsed.risk_zones)}, unit={len(res.parsed.unit_specs)}")

    return {
        "sa_test_analysis_output": output_dict,
        "sa_arch_bundle": sa_bundle,
        "current_step": "sa_test_analysis_done",
        "thinking_log": (sget("thinking_log", []) or []) + [
            {"node": "sa_test_analysis", "thinking": res.parsed.thinking or "테스트 전략 분석 완료"}
        ],
    }
