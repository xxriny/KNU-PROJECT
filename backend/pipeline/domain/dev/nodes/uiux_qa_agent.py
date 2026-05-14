from __future__ import annotations

import json
from typing import Any

from pipeline.core.node_base import NodeContext, pipeline_node
from pipeline.core.utils import call_structured
from pipeline.domain.dev.schemas import DomainQAPlanningOutput


SYSTEM_PROMPT = """# 역할: UI/UX QA Agent
## 목표
- UI/UX agent 산출물을 검토하고 pass 또는 rework를 결정한다.

## 규칙
- 출력은 반드시 구조화된 JSON만 반환한다.
- domain은 반드시 uiux로 설정한다.
- status는 pass 또는 rework만 사용한다.
- findings는 확인된 문제 또는 확인 결과를 작성한다.
- fixes_required는 재작업이 필요할 때만 구체적으로 작성한다.
- 요구사항, 화면 흐름, shared component 일관성을 우선 검토한다.
- thinking은 반드시 한국어 핵심 단어 3개 이내로 작성한다.
"""


LEGACY_SYSTEM_PROMPT = SYSTEM_PROMPT

SYSTEM_PROMPT = """
당신은 '수석 UIUX QA 검증자'입니다. UIUX 산출물이 PM 요구사항과 SA 산출물을 프론트엔드 구현 가능한 핸드오프로 변환했는지 검증하십시오.

[1. 검증 기준 (MANDATORY)]
- 화면 커버리지: 주요 요구사항은 screen, route, state, primary_action으로 연결되어야 합니다.
- 사용자 흐름: user_flows는 steps, success_criteria, requirement_ids를 가져야 합니다.
- 컴포넌트 계약: component_tree는 source_component와 화면 사용처를 명시해야 합니다.
- 상태 설계: loading, error, empty, validation, accessibility 요구가 누락되면 rework입니다.
- 프론트 핸드오프: routes, api_client_needs, data_contracts가 SA API/DB와 추적되어야 합니다.

[2. 출력 규칙]
- structured JSON만 반환하십시오.
- domain은 반드시 "uiux"입니다.
- status는 "pass" 또는 "rework"만 사용하십시오.
- findings는 실제 결함 또는 확인 결과만 작성하십시오.
- fixes_required는 rework를 해결하기 위한 구체적 작업만 작성하십시오.
- thinking은 한국어 핵심 단어 3개 이내입니다.

[3. 출력 규격(JSON)]
{
  "thinking": "단어 3개",
  "status": "pass|rework",
  "domain": "uiux",
  "findings": ["검증 결과"],
  "fixes_required": ["필요 수정"]
}
"""


def _build_user_message(result: dict, spec: dict, project_rag_context: dict, artifact_rag_context: dict) -> str:
    return json.dumps({
        "task_spec": spec,
        "domain_result": result,
        "project_rag_context": project_rag_context,
        "artifact_rag_context": artifact_rag_context,
    }, ensure_ascii=False)


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in items if str(item or "").strip()))


def _looks_like_endpoint(value: Any) -> bool:
    text = str(value or "").strip()
    upper = text.upper()
    methods = ("GET ", "POST ", "PUT ", "PATCH ", "DELETE ")
    return upper.startswith(methods) or text.startswith("/api/") or text.startswith("/")


def _table_names(spec: dict, artifact_rag_context: dict) -> set[str]:
    dev_task = spec.get("dev_task") or {}
    dev_context = dev_task.get("context") or {}
    tables = dev_context.get("target_table_specs") or artifact_rag_context.get("tables") or []
    names = set()
    for table in tables:
        if isinstance(table, dict):
            name = str(table.get("table_name") or table.get("name") or table.get("nm") or "").strip()
            if name:
                names.add(name)
    return names


def _contract_findings(artifact: dict, spec: dict, artifact_rag_context: dict) -> tuple[list[str], list[str]]:
    findings = []
    fixes_required = []
    screens = artifact.get("screens") or []
    flows = artifact.get("user_flows") or []
    components = artifact.get("component_tree") or []
    handoff = artifact.get("frontend_handoff") or {}
    table_names = _table_names(spec, artifact_rag_context)

    api_values = [
        *handoff.get("api_client_needs", []),
        *[api for screen in screens for api in (screen.get("api_dependencies") or [])],
    ]
    bad_api_values = [str(value) for value in api_values if not _looks_like_endpoint(value)]
    if bad_api_values:
        findings.append("UI/UX artifact includes non-endpoint values in API dependencies.")
        fixes_required.append("Keep api_dependencies and api_client_needs limited to concrete SA endpoint strings.")

    data_contracts = [
        *handoff.get("data_contracts", []),
        *[dep for screen in screens for dep in (screen.get("data_dependencies") or [])],
    ]
    bad_contracts = []
    for contract in data_contracts:
        text = str(contract or "")
        table, sep, field = text.partition(".")
        if not sep or not table.strip() or not field.strip() or (table_names and table not in table_names):
            bad_contracts.append(text)
    if bad_contracts:
        findings.append("UI/UX artifact includes data contracts outside SA table.field contracts.")
        fixes_required.append("Limit data_contracts to SA table.field values from the SA DB output.")

    roles = {str(component.get("role") or "").lower() for component in components if isinstance(component, dict)}
    if components and not {"layout", "page", "component"}.issubset(roles):
        findings.append("UI/UX component tree does not expose the Layout > Page > Component hierarchy.")
        fixes_required.append("Represent component_tree with layout, page, and component roles.")

    flow_steps = " ".join(
        str(step).lower()
        for flow in flows
        for step in (flow.get("steps") or [])
    )
    if flows and ("success" not in flow_steps or not any(token in flow_steps for token in ("fail", "error", "validation"))):
        findings.append("UI/UX user flows do not define concrete success and failure feedback behavior.")
        fixes_required.append("Add API success and failure feedback steps to user_flows.")

    return findings, fixes_required


def _artifact_findings(artifact: dict) -> tuple[list[str], list[str]]:
    findings = []
    fixes_required = []
    screens = artifact.get("screens") or []
    flows = artifact.get("user_flows") or []
    components = artifact.get("component_tree") or []
    handoff = artifact.get("frontend_handoff") or {}

    if not screens:
        findings.append("UI/UX artifact does not define screens.")
        fixes_required.append("Add screens with purpose, route, states, and primary actions.")
    else:
        for screen in screens:
            missing = [
                key
                for key in ("name", "purpose", "route")
                if not str(screen.get(key) or "").strip()
            ]
            if missing:
                findings.append(f"Screen {screen.get('id') or screen.get('name') or 'unknown'} misses {', '.join(missing)}.")
                fixes_required.append("Complete required screen metadata for frontend handoff.")
            states = screen.get("states") or []
            if not {"loading", "error"}.issubset(set(states)):
                findings.append(f"Screen {screen.get('name') or 'unknown'} lacks loading/error states.")
                fixes_required.append("Define loading and error states for each screen.")
            if not screen.get("requirement_ids"):
                findings.append(f"Screen {screen.get('name') or 'unknown'} is not traced to PM requirements.")
                fixes_required.append("Trace each screen to requirement_ids.")
            if not screen.get("acceptance_criteria"):
                findings.append(f"Screen {screen.get('name') or 'unknown'} lacks acceptance criteria.")
                fixes_required.append("Attach PM acceptance criteria to each screen.")

    if not flows:
        findings.append("UI/UX artifact does not define user flows.")
        fixes_required.append("Add user flows with steps and success criteria.")
    elif any(not flow.get("requirement_ids") for flow in flows):
        findings.append("One or more user flows are not traced to PM requirements.")
        fixes_required.append("Trace user flows to requirement_ids.")
    if not components:
        findings.append("UI/UX artifact does not define a component tree.")
        fixes_required.append("Add component tree entries for frontend implementation.")
    elif any(not component.get("source_component") for component in components):
        findings.append("One or more UI components are not traced to SA/component sources.")
        fixes_required.append("Add source_component references to component tree entries.")
    if not artifact.get("empty_states"):
        findings.append("UI/UX artifact does not define empty states.")
        fixes_required.append("Define empty states.")
    if not artifact.get("error_states"):
        findings.append("UI/UX artifact does not define error states.")
        fixes_required.append("Define error states.")
    if not artifact.get("accessibility_requirements"):
        findings.append("UI/UX artifact does not define accessibility requirements.")
        fixes_required.append("Add accessibility requirements.")
    if not handoff.get("routes"):
        findings.append("Frontend handoff does not define routes.")
        fixes_required.append("Add frontend routes.")
    if not handoff.get("api_client_needs"):
        findings.append("Frontend handoff does not define API client needs.")
        fixes_required.append("Trace UI interactions to SA API endpoints.")

    return findings, fixes_required


@pipeline_node("develop_uiux_qa_agent")
def develop_uiux_qa_agent_node(ctx: NodeContext) -> dict:
    result = ctx.sget("uiux_result", {}) or {}
    artifact = ctx.sget("uiux_artifact", {}) or {}
    spec = ctx.sget("uiux_task_spec", {}) or {}
    dev_task = spec.get("dev_task") or {}
    dev_context = dev_task.get("context") or {}
    findings = []
    fixes_required = []
    if not result.get("files"):
        findings.append("No UI/UX target files or areas were identified.")
        fixes_required.append("Specify target screens or shared components.")
    if not result.get("requirement_ids"):
        findings.append("UI/UX result is not mapped to requirement IDs.")
        fixes_required.append("Link UI/UX scope to explicit requirement IDs.")
    if len(result.get("proposed_changes", []) or []) < 2:
        findings.append("UI/UX result does not describe enough concrete changes.")
        fixes_required.append("List at least two concrete UI/UX changes.")
    if len(result.get("test_plan", []) or []) < len(spec.get("acceptance_criteria", []) or []):
        findings.append("UI/UX test plan does not cover the declared acceptance criteria.")
        fixes_required.append("Expand the UI/UX test plan to cover all acceptance criteria.")
    artifact_findings, artifact_fixes = _artifact_findings(artifact)
    findings.extend(artifact_findings)
    fixes_required.extend(artifact_fixes)
    contract_findings, contract_fixes = _contract_findings(
        artifact,
        spec,
        ctx.sget("artifact_rag_context", {}) or {},
    )
    findings.extend(contract_findings)
    fixes_required.extend(contract_fixes)
    if (dev_context.get("approved_stack") or spec.get("approved_stack")) and not result.get("approved_stack"):
        findings.append("UI/UX result does not carry approved_stack from the Main Agent task spec.")
        fixes_required.append("Pass approved_stack through UI/UX planning so downstream agents can reject unapproved design/runtime assumptions.")
    if (dev_task.get("constraints") or spec.get("generation_policy")) and not result.get("generation_policy"):
        findings.append("UI/UX result does not carry generation_policy from the Main Agent task spec.")
        fixes_required.append("Pass generation_policy through UI/UX planning and preserve no-dummy/no-placeholder constraints.")
    policy = result.get("policy_enforcement") or {}
    if policy.get("status") == "failed":
        policy_findings = policy.get("findings") or ["UI/UX policy enforcement failed."]
        findings.extend(policy_findings)
        fixes_required.append("Resolve UI/UX policy enforcement findings before passing the domain gate.")
    fallback = {
        "status": "rework" if fixes_required else "pass",
        "domain": "uiux",
        "findings": findings,
        "fixes_required": fixes_required,
    }
    if ctx.api_key:
        res = call_structured(
            api_key=ctx.api_key,
            model=ctx.model,
            schema=DomainQAPlanningOutput,
            system_prompt=SYSTEM_PROMPT,
            user_msg=_build_user_message(
                {"uiux_result": result, "uiux_artifact": artifact},
                spec,
                ctx.sget("project_rag_context", {}) or {},
                ctx.sget("artifact_rag_context", {}) or {},
            ),
            max_retries=3,
            temperature=0.1,
            compress_prompt=True,
        )
        planned = res.parsed.model_dump()
        planned["domain"] = "uiux"
        if fixes_required:
            planned["status"] = "rework"
            planned["findings"] = _dedupe([*planned.get("findings", []), *findings])
            planned["fixes_required"] = _dedupe([*planned.get("fixes_required", []), *fixes_required])
        elif planned.get("status") == "rework":
            planned["status"] = "pass"
            planned["advisory_findings"] = _dedupe(planned.get("fixes_required", []))
            planned["findings"] = _dedupe([
                "Mandatory deterministic UI/UX handoff contract checks passed.",
                *planned.get("findings", []),
            ])
            planned["fixes_required"] = []
        return {"uiux_qa_result": planned, "_thinking": res.parsed.thinking or "uiux-qa, flow, consistency"}
    return {"uiux_qa_result": fallback, "_thinking": "uiux-coverage, ui-contract, implementation-handoff"}
