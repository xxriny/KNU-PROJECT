"""
Task Generator Node
SA 설계 산출물(컴포넌트/API/DB/테스트 전략/프로젝트 구조)과 PM 산출물(RTM/기술스택)을
구현 태스크로 분해하여 unassigned 상태로 agile_tasks DB에 저장한다.

중복 방지:
  - feature_ref 기준 (전체 상태 포함)
  - 제목 정규화 기준 (공백·대소문자 무시)
"""
from __future__ import annotations

import json
import re

from pipeline.core.utils import call_structured
from pipeline.domain.agile.schemas import TaskGeneratorOutput
from pipeline.domain.agile.task_coordinator import create_task, list_tasks, update_task_status
from observability.logger import get_logger

logger = get_logger()

SYSTEM_PROMPT = """# Role: Agile Task Decomposition Specialist

## Goal
Given software architecture design artifacts and the FULL current task state,
produce TWO outputs:
1. **New tasks** (tk): tasks not yet covered by any existing task
2. **Update suggestions** (up): unassigned tasks whose title/description/area/effort should change

## Input Sections
- Tech Stacks, Components, APIs, DB Tables, Project Structure, Test Strategy, RTM
- **COVERED** — tasks that already exist in any status (active OR unassigned).
  These are the ground truth of what is already planned or done.
  ⛔ Do NOT create any task whose title or feature_ref appears here.
- **Unassigned Tasks** — subset of COVERED that is still unassigned (modifiable via up)

## Decision Rules
1. If a component / endpoint / table / feature already appears in COVERED → skip it entirely
2. If an unassigned task's details are outdated → suggest update (up)
3. If the design requires something absent from COVERED → create new task (tk)
4. When in doubt about duplication — skip, do NOT create

## Task Type Rules
- feature: Component implementation, API endpoint, DB model/migration
- test: Unit / integration / system / acceptance test
- infra: CI/CD, Docker, project scaffolding, environment setup only
- doc_sync: Documentation

## Area Assignment Rules
- Backend component (domain=B) or DB/API work → area=backend
- Frontend component (domain=F) → area=frontend
- CI/CD, Docker, cloud infra → area=devops
- Tasks spanning both → area=fullstack

## Effort Rules
- S: < 2 hours (simple config, single endpoint)
- M: 2–8 hours (standard CRUD, single component)
- L: 1–3 days (complex business logic, multi-table)
- XL: > 3 days (auth system, real-time, major integration)

## Output Rules
- thinking (th): Brief rationale in Korean
- tasks (tk): NEW tasks only
- updates (up): list of {id, changed fields only, reason} for unassigned tasks needing update
- summary (sm): "신규 N개, 수정 제안 M개" in Korean

## CRITICAL: Coverage Requirements
- Every component NOT in COVERED must get exactly ONE feature task
- Every DB table NOT in COVERED must get ONE feature task (not infra — it's a model/migration)
- Every API endpoint group NOT in COVERED must get ONE feature task
- Every risk zone in test_strategy NOT in COVERED must get at least ONE test task
- Never batch two components into one task

## Important
- Use tech stack names: "FastAPI SplitAgent router 구현" not "API 구현"
- feature_ref must match RTM FEAT_ID exactly, or leave empty
- Only suggest updates when there is a clear design-driven reason
"""


def _normalize(title: str) -> str:
    """제목 정규화: 소문자, 공백·특수문자 제거."""
    return re.sub(r"[\s\-_()（）]", "", title).lower()


def _build_user_msg(
    sa_bundle: dict,
    pm_bundle: dict,
    all_tasks: list[dict],
) -> str:
    data = sa_bundle.get("data", {})
    components        = data.get("components", [])
    apis              = data.get("apis", [])
    tables            = data.get("tables", [])
    project_structure = data.get("project_structure", {})
    test_strategy     = data.get("test_strategy", {})

    pm_data    = pm_bundle.get("data", {}) if pm_bundle else {}
    tech_stacks = pm_data.get("tech_stacks", []) or []
    rtm        = (pm_bundle.get("plan", {}) or {}).get("requirements_rtm", []) if pm_bundle else []

    # ── COVERED: 모든 상태의 태스크 (LLM이 중복 회피에 사용)
    covered = [
        {
            "title": t["title"],
            "status": t["status"],
            "feature_ref": t.get("feature_ref") or "",
            "area": t.get("area") or "",
            "assignee": t.get("assignee") or "",
        }
        for t in all_tasks
    ]

    # ── 미할당 태스크: 수정 제안 대상
    unassigned = [
        {
            "id": t["id"],
            "title": t["title"],
            "area": t.get("area") or "",
            "effort": t.get("effort") or "",
            "task_type": t.get("task_type") or "",
            "feature_ref": t.get("feature_ref") or "",
            "description": (t.get("description") or "")[:200],
        }
        for t in all_tasks if t["status"] == "unassigned"
    ]

    component_names = [c.get("name", c.get("id", "")) for c in components]
    table_names     = [tb.get("name", tb.get("table_name", "")) for tb in tables]

    return (
        f"## Tech Stacks\n```json\n{json.dumps(tech_stacks, ensure_ascii=False)[:2000]}\n```\n\n"
        f"## Components ({len(components)} total)\n"
        f"Names: {json.dumps(component_names, ensure_ascii=False)}\n"
        f"```json\n{json.dumps(components, ensure_ascii=False, indent=2)[:8000]}\n```\n\n"
        f"## APIs ({len(apis)} total)\n```json\n{json.dumps(apis, ensure_ascii=False, indent=2)[:5000]}\n```\n\n"
        f"## DB Tables ({len(tables)} total)\n"
        f"Names: {json.dumps(table_names, ensure_ascii=False)}\n"
        f"```json\n{json.dumps(tables, ensure_ascii=False, indent=2)[:4000]}\n```\n\n"
        f"## Project Structure\n```json\n{json.dumps(project_structure, ensure_ascii=False)[:2000]}\n```\n\n"
        f"## Test Strategy\n```json\n{json.dumps(test_strategy, ensure_ascii=False, indent=2)[:5000]}\n```\n\n"
        f"## RTM ({len(rtm)} features)\n```json\n{json.dumps(rtm[:60], ensure_ascii=False, indent=2)[:5000]}\n```\n\n"
        f"## COVERED — 이미 존재하는 태스크 전체 ({len(covered)}개, 모든 상태 포함)\n"
        f"⛔ 아래 title 또는 feature_ref가 이미 존재하면 절대 중복 생성 금지\n"
        f"```json\n{json.dumps(covered, ensure_ascii=False, indent=2)[:5000]}\n```\n\n"
        f"## Unassigned Tasks — 미할당 태스크 ({len(unassigned)}개, 수정 제안 가능)\n"
        f"```json\n{json.dumps(unassigned, ensure_ascii=False, indent=2)[:4000]}\n```\n\n"
        f"위 정보를 바탕으로 신규 태스크(tk)와 수정 제안(up)을 출력하세요.\n"
        f"COVERED에 없는 컴포넌트 {len(components)}개 + 테이블 {len(tables)}개 기준으로 누락 태스크를 채우세요."
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
    SA/PM 산출물 + 전체 태스크 현황 → 신규 생성 + 수정 제안 적용.
    중복 방지: feature_ref 전체 상태 포함 + 제목 정규화 비교.
    """
    all_tasks = list_tasks(team_id=team_id)

    # 중복 방지 세트 (전체 상태 기준)
    existing_refs_set   = {t["feature_ref"] for t in all_tasks if t.get("feature_ref")}
    existing_title_norm = {_normalize(t["title"]) for t in all_tasks if t.get("title")}

    unassigned_ids = {t["id"] for t in all_tasks if t["status"] == "unassigned"}

    user_msg = _build_user_msg(sa_bundle, pm_bundle, all_tasks)

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
        return {"created": 0, "skipped": 0, "updated": 0, "tasks": []}

    output = res.parsed
    created_tasks = []
    skipped = 0
    updated_count = 0

    # ── 신규 태스크 생성 (이중 중복 방지)
    for task in output.tasks:
        # feature_ref 기준 중복
        if task.feature_ref and task.feature_ref in existing_refs_set:
            logger.info(f"[task_generator] 스킵(ref 중복): {task.feature_ref} — {task.title}")
            skipped += 1
            continue

        # 제목 정규화 기준 중복
        norm = _normalize(task.title)
        if norm in existing_title_norm:
            logger.info(f"[task_generator] 스킵(제목 중복): {task.title}")
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
        if record is None:
            # create_task 내부에서 중복 감지
            skipped += 1
            continue
        created_tasks.append(record)

        # 이번 배치 내 중복 방지용 즉시 등록
        if task.feature_ref:
            existing_refs_set.add(task.feature_ref)
        existing_title_norm.add(norm)

    # ── 수정 제안 적용 (unassigned 태스크만)
    for suggestion in output.updates:
        if suggestion.task_id not in unassigned_ids:
            logger.warning(f"[task_generator] 수정 제안 스킵 — unassigned 아님 또는 없는 id: {suggestion.task_id}")
            continue
        editable = {k: v for k, v in {
            "title":       suggestion.title,
            "description": suggestion.description,
            "area":        suggestion.area,
            "effort":      suggestion.effort,
            "task_type":   suggestion.task_type,
        }.items() if v is not None}
        if editable:
            update_task_status(suggestion.task_id, "unassigned", editable_fields=editable)
            updated_count += 1
            logger.info(f"[task_generator] 태스크 수정: {suggestion.task_id} — {suggestion.reason}")

    logger.info(f"[task_generator] 완료: 생성={len(created_tasks)}, 스킵={skipped}, 수정={updated_count}")
    return {
        "created":  len(created_tasks),
        "skipped":  skipped,
        "updated":  updated_count,
        "tasks":    created_tasks,
        "summary":  output.summary,
        "thinking": output.thinking,
    }
