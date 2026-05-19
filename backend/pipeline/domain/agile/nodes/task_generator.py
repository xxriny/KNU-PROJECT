"""
Task Generator Node
SA 설계 산출물(컴포넌트/API/DB/테스트 전략/프로젝트 구조)과 PM 산출물(RTM/기술스택)을
구현 태스크로 분해하여 unassigned 상태로 agile_tasks DB에 저장한다.

- 중복 방지: 이미 존재하는 feature_ref는 스킵
- 추가만: 기존 태스크 수정/삭제 없음
"""
from __future__ import annotations

import json

from pipeline.core.utils import call_structured
from pipeline.domain.agile.schemas import TaskGeneratorOutput
from pipeline.domain.agile.task_coordinator import create_task, get_existing_feature_refs
from observability.logger import get_logger

logger = get_logger()

SYSTEM_PROMPT = """# Role: Agile Task Decomposition Specialist

## Goal
Convert software architecture design artifacts into concrete, implementable development tasks.
Each task must be specific enough for a developer to start immediately.

## Input Artifacts
- components: Frontend(F) / Backend(B) components with roles
- apis: API endpoint definitions
- tables: DB table definitions
- project_structure: Directory/file layout for initial setup tasks
- test_strategy: risk_zones, unit/integration/system/acceptance specs
- tech_stacks: global_stacks (FastAPI, React, etc.) — use these in task titles/descriptions
- rtm: Requirements Traceability Matrix — link each task to a FEAT_ID via feature_ref

## Task Type Rules
- feature: Component implementation, API development, DB migration
- test: Unit/integration/system/acceptance test implementation (from test_strategy)
- infra: Project setup, CI/CD, DevOps configuration (from project_structure)
- doc_sync: Documentation tasks

## Area Assignment Rules
- Backend component (domain=B) → area=backend
- Frontend component (domain=F) → area=frontend
- DevOps/infra tasks → area=devops
- Tasks spanning both → area=fullstack

## Priority Rules
- risk_level=critical/high components → priority=high
- Core feature RTM items → priority=medium
- Setup/infra/doc tasks → priority=low

## Effort Rules (story points proxy)
- S: < 2 hours (simple config, single endpoint)
- M: 2–8 hours (standard CRUD, single component)
- L: 1–3 days (complex business logic, multi-table)
- XL: > 3 days (auth system, real-time feature, major integration)

## Output Rules
- thinking (th): Brief rationale for decomposition decisions (Korean)
- tasks (tk): List of ALL tasks derived from the artifacts
- summary (sm): Total count summary by type (Korean)

## Important
- Use tech stack names in titles: "FastAPI router 구현" not just "API 구현"
- One task per component/endpoint/table when possible — avoid mega-tasks
- Test tasks must reference the component/endpoint they test
- feature_ref must match an RTM FEAT_ID exactly, or leave empty if no direct mapping
"""


def _build_user_msg(
    sa_bundle: dict,
    pm_bundle: dict,
    existing_refs: set[str],
) -> str:
    data = sa_bundle.get("data", {})
    components = data.get("components", [])
    apis = data.get("apis", [])
    tables = data.get("tables", [])
    project_structure = data.get("project_structure", {})
    test_strategy = data.get("test_strategy", {})

    pm_data = pm_bundle.get("data", {}) if pm_bundle else {}
    tech_stacks = pm_data.get("tech_stacks", []) or []
    rtm = (pm_bundle.get("plan", {}) or {}).get("requirements_rtm", []) if pm_bundle else []

    skip_note = ""
    if existing_refs:
        skip_note = (
            f"\n## Already Generated (SKIP these feature_refs)\n"
            f"{json.dumps(sorted(existing_refs), ensure_ascii=False)}\n"
            "Do NOT generate tasks for the above feature_refs — they already exist.\n"
        )

    return (
        f"{skip_note}"
        f"## Tech Stacks\n```json\n{json.dumps(tech_stacks, ensure_ascii=False)[:1500]}\n```\n\n"
        f"## Components ({len(components)})\n```json\n{json.dumps(components, ensure_ascii=False, indent=2)[:2500]}\n```\n\n"
        f"## APIs ({len(apis)})\n```json\n{json.dumps(apis, ensure_ascii=False, indent=2)[:2000]}\n```\n\n"
        f"## DB Tables ({len(tables)})\n```json\n{json.dumps(tables, ensure_ascii=False, indent=2)[:1500]}\n```\n\n"
        f"## Project Structure\n```json\n{json.dumps(project_structure, ensure_ascii=False)[:1000]}\n```\n\n"
        f"## Test Strategy\n```json\n{json.dumps(test_strategy, ensure_ascii=False, indent=2)[:2500]}\n```\n\n"
        f"## RTM ({len(rtm)} features)\n```json\n{json.dumps(rtm[:30], ensure_ascii=False, indent=2)[:2000]}\n```\n\n"
        "위 산출물을 기반으로 구현 태스크를 생성하세요."
    )


def run_task_generator(
    sa_bundle: dict,
    pm_bundle: dict,
    team_id: str,
    api_key: str,
    model: str,
    created_by: str = "",
) -> dict:
    """
    SA/PM 산출물 → unassigned 태스크 생성.
    이미 존재하는 feature_ref는 스킵 (추가만, 삭제 없음).
    """
    existing_refs = get_existing_feature_refs(team_id)
    user_msg = _build_user_msg(sa_bundle, pm_bundle, existing_refs)

    res = call_structured(
        api_key=api_key,
        model=model,
        schema=TaskGeneratorOutput,
        system_prompt=SYSTEM_PROMPT,
        user_msg=user_msg,
        compress_prompt=False,
        temperature=0.1,
    )

    if not res.parsed:
        logger.warning("[task_generator] LLM 파싱 실패")
        return {"created": 0, "skipped": 0, "tasks": []}

    output = res.parsed
    created_tasks = []
    skipped = 0

    for task in output.tasks:
        # feature_ref 중복 스킵 (빈 ref는 중복 체크 제외)
        if task.feature_ref and task.feature_ref in existing_refs:
            skipped += 1
            continue

        record = create_task(
            task_type=task.task_type,
            title=task.title,
            description=task.description,
            area=task.area,
            feature_ref=task.feature_ref,
            effort=task.effort,
            team_id=team_id,
            created_by=created_by,
            status="unassigned",
            payload={"priority": task.priority},
        )
        created_tasks.append(record)
        if task.feature_ref:
            existing_refs.add(task.feature_ref)

    logger.info(f"[task_generator] 완료: 생성={len(created_tasks)}, 스킵={skipped}")
    return {
        "created": len(created_tasks),
        "skipped": skipped,
        "tasks": created_tasks,
        "summary": output.summary,
        "thinking": output.thinking,
    }
