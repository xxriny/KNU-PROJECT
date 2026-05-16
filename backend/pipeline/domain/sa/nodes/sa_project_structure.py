"""
SA Project Structure Node
기술 스택 + 컴포넌트 목록 + RTM을 조합하여 최적화된 디렉토리 구조를 설계합니다.
component_mapping은 GitHub Commit Analyzer의 파일→컴포넌트 매핑 기준이 됩니다.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from pipeline.core.node_base import pipeline_node, NodeContext
from pipeline.core.utils import call_structured
from pipeline.domain.sa.schemas import SAProjectStructureOutput
from observability.logger import get_logger

logger = get_logger()

SYSTEM_PROMPT = """# Role: Software Architecture Directory Designer

## Goal
Design an optimal project directory structure based on:
1. Selected tech stack (from PM analysis)
2. Component list (from component_scheduler)
3. RTM features (from PM analysis)

The output must be a realistic, implementable directory tree — not generic boilerplate.
Every directory and file must map to a specific component or architectural concern.

## Design Principles
- **Component-first**: Each component must have a clear home directory/file
- **Convention-based**: Follow framework conventions (FastAPI: routers/services/models; React: pages/components/hooks/store)
- **Test-aligned**: Mirror the test_strategy layers (unit/, integration/, system/) in test directories
- **No placeholders**: Only include paths that would actually exist for this specific project

## Output Fields
- thinking (th): Rationale for structure decisions (Korean)
- tree (tr): Root DirectoryNode with full recursive structure
  - name (nm): directory or file name
  - type_ (tp): "dir" or "file"
  - component_id (ci): which component this path belongs to (empty if shared)
  - children (ch): child nodes (only for dirs)
  - rationale (rt): why this path exists (optional, 1 sentence)
- component_mapping (cm): {component_name: [file_path_list]} for GitHub Commit Analyzer
- conventions (cv): List of naming/placement conventions used

## Example component_mapping format
{
  "AuthService": [
    "backend/app/api/v1/auth.py",
    "backend/app/services/auth_service.py",
    "backend/tests/unit/test_auth_service.py"
  ]
}
"""


def _build_user_msg(sa_bundle: dict, pm_bundle: dict, rtm: list, action_type: str) -> str:
    data = sa_bundle.get("data", {})
    components = data.get("components", [])

    pm_data = pm_bundle.get("data", {}) if pm_bundle else {}
    tech_stacks = pm_data.get("tech_stacks", []) or []

    components_text = json.dumps(components, ensure_ascii=False, indent=2)[:2500]
    stacks_text = json.dumps(tech_stacks, ensure_ascii=False, indent=2)[:1500]
    rtm_text = json.dumps(rtm[:15], ensure_ascii=False, indent=2)[:1500]

    return (
        f"## Action Type: {action_type}\n\n"
        f"## Tech Stacks ({len(tech_stacks)}개)\n```json\n{stacks_text}\n```\n\n"
        f"## Components ({len(components)}개)\n```json\n{components_text}\n```\n\n"
        f"## RTM Features ({len(rtm)}개)\n```json\n{rtm_text}\n```\n\n"
        "위 정보를 기반으로 이 프로젝트의 최적 디렉토리 구조를 설계하세요. "
        "component_mapping은 GitHub Commit Analyzer에서 사용됩니다."
    )


@pipeline_node("sa_project_structure")
def sa_project_structure_node(ctx: NodeContext) -> dict:
    sget = ctx.sget
    logger.info("=== [Node Entry] sa_project_structure_node ===")

    sa_bundle = sget("sa_arch_bundle", {}) or {}
    pm_bundle = sget("pm_bundle", {}) or {}
    merged_project = sget("merged_project", {}) or {}
    rtm = (merged_project.get("plan", {}) or {}).get("requirements_rtm", []) or []
    action_type = sget("action_type", "CREATE")

    if not sa_bundle:
        logger.warning("[sa_project_structure] sa_arch_bundle이 비어 있어 스킵합니다.")
        return {"current_step": "sa_project_structure_done"}

    user_msg = _build_user_msg(sa_bundle, pm_bundle, rtm, action_type)

    res = call_structured(
        schema=SAProjectStructureOutput,
        system_prompt=SYSTEM_PROMPT,
        user_msg=user_msg,
        ctx=ctx,
        compress_prompt=False,
        temperature=0.0,
    )

    if not res.parsed:
        logger.warning("[sa_project_structure] LLM 파싱 실패, 빈 결과 반환")
        return {"current_step": "sa_project_structure_done"}

    output_dict = res.parsed.model_dump()

    # sa_arch_bundle에 project_structure 섹션 병합
    sa_bundle.setdefault("data", {})["project_structure"] = output_dict
    component_count = len(res.parsed.component_mapping)
    logger.info(f"[sa_project_structure] 완료: component_mapping={component_count}개 컴포넌트")

    return {
        "sa_project_structure_output": output_dict,
        "sa_arch_bundle": sa_bundle,
        "current_step": "sa_project_structure_done",
        "thinking_log": (sget("thinking_log", []) or []) + [
            {"node": "sa_project_structure", "thinking": res.parsed.thinking or "프로젝트 구조 설계 완료"}
        ],
    }
