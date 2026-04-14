"""
PM Agent Pipeline — 채팅 수정 노드 v9.0
기존 RTM 결과를 사용자 요청에 따라 수정하는 LangGraph 노드.
Patch 출력과 하이브리드 컨텍스트 선택으로 토큰 사용량을 줄인다.
"""

import json
import re

from pydantic import BaseModel, Field
from pipeline.core.state import PipelineState, make_sget
from pipeline.core.utils import call_structured, to_serializable
from observability.logger import get_logger
from version import DEFAULT_MODEL


class RTMRevision(BaseModel):
    REQ_ID: str = Field(default="", description="고유 ID. 신규 항목은 비워둘 수 있음")
    category: str = Field(default="", description="Backend|Frontend|Infrastructure|Database|Security|AI/ML")
    description: str = Field(default="", description="기능 설명")
    priority: str = Field(default="", description="Must-have|Should-have|Could-have")
    rationale: str = Field(default="", description="우선순위 근거")
    depends_on: list[str] = Field(default_factory=list, description="선행 REQ_ID 목록")
    test_criteria: str = Field(default="", description="테스트 기준")


class RTMRequirementPatch(BaseModel):
    REQ_ID: str = Field(description="수정 대상 REQ ID")
    category: str | None = Field(default=None, description="변경 시에만 채움")
    description: str | None = Field(default=None, description="변경 시에만 채움")
    priority: str | None = Field(default=None, description="변경 시에만 채움")
    rationale: str | None = Field(default=None, description="변경 시에만 채움")
    depends_on: list[str] | None = Field(default=None, description="변경 시에만 채움")
    test_criteria: str | None = Field(default=None, description="변경 시에만 채움")


class ChatRevisionPatchOutput(BaseModel):
    thinking: str = Field(default="", description="수정 추론 과정 (2줄 이내)")
    agent_reply: str = Field(default="", description="사용자에게 보여줄 수정 완료 메시지")
    added_requirements: list[RTMRevision] = Field(default_factory=list)
    modified_requirements: list[RTMRequirementPatch] = Field(default_factory=list)
    deleted_req_ids: list[str] = Field(default_factory=list)
    summary: str = Field(default="", description="수정된 프로젝트 요약. 유지 시 빈 문자열")
    key_decisions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    tech_stack_suggestions: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


SYSTEM_PROMPT = """당신은 PM(프로젝트 매니저) 에이전트입니다.
사용자가 기존 RTM(Requirements Traceability Matrix) 결과에 대한 수정 요청을 보냅니다.

## 핵심 원칙
1. 전체 RTM을 재작성하지 말고 변경 사항만 Patch 형태로 반환하세요.
2. 변경되지 않은 요구사항은 절대 다시 출력하지 마세요.
3. 삭제는 deleted_req_ids에만 기록하세요.
4. 수정은 modified_requirements에 필요한 필드만 채우세요.
5. 추가는 added_requirements에만 기록하세요. 신규 항목은 REQ_ID를 비워도 됩니다.
6. 사용자가 특정 REQ를 언급하면 그 주변 의존관계만 고려해 최소 수정으로 반영하세요.
7. 제공된 RTM 컨텍스트가 partial_scope이면 제공되지 않은 항목은 직접 수정하지 마세요.
8. 반드시 단일 JSON 객체만 출력하세요.
9. 모든 설명은 한국어로 작성하세요.

## 응답 형식
반드시 아래 JSON 스키마를 따르세요.
- agent_reply: 무엇을 바꿨는지 1~2문장 요약
- added_requirements: 새 요구사항 목록
- modified_requirements: 수정된 필드만 포함한 patch 목록
- deleted_req_ids: 삭제할 REQ_ID 목록
- summary, key_decisions, open_questions, tech_stack_suggestions, risk_factors, next_steps:
  컨텍스트 명세가 실제로 바뀌는 경우에만 채우고, 아니면 빈 문자열/빈 배열 유지
"""


def chat_revision_node(state: PipelineState) -> dict:
    """채팅 수정 노드 — 기존 RTM을 Patch 기반으로 수정"""
    try:
        sget = make_sget(state)
        api_key = sget("api_key", "")
        model = sget("model", DEFAULT_MODEL)
        user_request = sget("user_request", "")
        previous = sget("previous_result", {})
        history = sget("chat_history", [])

        if not user_request:
            return {"error": "수정 요청이 비어있습니다.", "current_step": "chat_revision"}

        prev_rtm = _normalize_rtm(previous.get("requirements_rtm", []))
        prev_meta = _serialize(previous.get("metadata", {})) or {}
        prev_graph = _normalize_semantic_graph(previous.get("semantic_graph", {}), prev_rtm)
        prev_spec = _serialize(previous.get("context_spec", {})) or {}

        selected_rtm, scope_meta = _select_revision_context(prev_rtm, prev_graph, user_request)
        context_payload = {
            "context_scope": scope_meta["scope"],
            "scope_reason": scope_meta["reason"],
            "selected_req_ids": [item["REQ_ID"] for item in selected_rtm],
            "requirements": selected_rtm,
            "metadata": prev_meta,
            "context_spec": prev_spec,
        }

        history_ctx = ""
        if history:
            recent = history[-8:]
            history_ctx = json.dumps(recent, ensure_ascii=False, indent=2)

        user_msg = (
            f"## revision_context\n{json.dumps(context_payload, ensure_ascii=False, indent=2)}\n\n"
            f"## recent_chat_history\n{history_ctx or '[]'}\n\n"
            f"## user_request\n{user_request}\n\n"
            "위 정보를 바탕으로 Patch만 반환하세요."
        )

        llm_result = call_structured(
            api_key=api_key,
            model=model,
            schema=ChatRevisionPatchOutput,
            system_prompt=SYSTEM_PROMPT,
            user_msg=user_msg,
            max_retries=3,
            temperature=0.2,
        )
        patch = llm_result.parsed

        new_rtm = _apply_revision_patch(prev_rtm, patch)
        new_graph = _normalize_semantic_graph(prev_graph, new_rtm)
        new_spec = _merge_context_spec(prev_spec, patch)
        new_meta = {**prev_meta, "status": "Revised"}
        agent_reply = patch.agent_reply or "수정이 완료되었습니다."

        new_history = list(history)
        new_history.append({"role": "user", "content": user_request})
        new_history.append({"role": "assistant", "content": agent_reply})

        return {
            "requirements_rtm": new_rtm,
            "rtm_matrix": new_rtm,
            "semantic_graph": new_graph,
            "metadata": new_meta,
            "context_spec": new_spec,
            "agent_reply": agent_reply,
            "chat_history": new_history,
            "thinking_log": [{"node": "chat_revision", "thinking": llm_result.thinking or agent_reply}],
            "current_step": "chat_revision",
        }

    except Exception as e:
        get_logger().exception("chat_revision_node failed")
        return {
            "error": str(e),
            "thinking_log": [{"node": "chat_revision", "thinking": f"오류: {e}"}],
            "current_step": "chat_revision",
        }


def _serialize(obj):
    return to_serializable(obj)


def _normalize_rtm(requirements) -> list:
    normalized = []
    for index, item in enumerate(requirements or [], start=1):
        data = _serialize(item) or {}
        req_id = data.get("REQ_ID") or data.get("id") or f"REQ-{index:03d}"
        normalized.append({
            **data,
            "REQ_ID": req_id,
            "depends_on": list(data.get("depends_on") or []),
        })
        normalized[-1].pop("id", None)
    return normalized


def _normalize_semantic_graph(graph, requirements) -> dict:
    graph_data = _serialize(graph) or {}
    valid_ids = {item["REQ_ID"] for item in requirements or [] if item.get("REQ_ID")}
    if not valid_ids:
        return {"nodes": [], "edges": []}

    nodes = []
    seen_nodes = set()
    for item in graph_data.get("nodes") or []:
        node = _serialize(item) or {}
        node_id = node.get("id") or node.get("REQ_ID")
        if not node_id or node_id not in valid_ids or node_id in seen_nodes:
            continue
        nodes.append({
            **node,
            "id": node_id,
        })
        nodes[-1].pop("REQ_ID", None)
        seen_nodes.add(node_id)

    req_map = {item["REQ_ID"]: item for item in requirements if item.get("REQ_ID")}
    for req_id, req in req_map.items():
        if req_id not in seen_nodes:
            nodes.append({
                "id": req_id,
                "label": req.get("description", req_id),
                "category": req.get("category", ""),
                "tags": [],
            })
            seen_nodes.add(req_id)

    edges = []
    seen_edges = set()
    for item in graph_data.get("edges") or []:
        edge = _serialize(item) or {}
        source = edge.get("source")
        target = edge.get("target")
        edge_key = (source, target, edge.get("relation", "depends_on"))
        if not source or not target or source not in valid_ids or target not in valid_ids or edge_key in seen_edges:
            continue
        edges.append({
            "source": source,
            "target": target,
            "relation": edge.get("relation", "depends_on"),
        })
        seen_edges.add(edge_key)

    for req in requirements:
        target = req.get("REQ_ID")
        for source in req.get("depends_on") or []:
            edge_key = (source, target, "depends_on")
            if source in valid_ids and target in valid_ids and edge_key not in seen_edges:
                edges.append({
                    "source": source,
                    "target": target,
                    "relation": "depends_on",
                })
                seen_edges.add(edge_key)

    return {"nodes": nodes, "edges": edges}


def _extract_req_ids(text: str) -> list[str]:
    return list(dict.fromkeys(match.upper() for match in re.findall(r"REQ-\d{3}", text or "", re.IGNORECASE)))


def _tokenize_request(text: str) -> list[str]:
    tokens = []
    for token in re.split(r"[^0-9A-Za-z가-힣_-]+", text or ""):
        cleaned = token.strip().lower()
        if len(cleaned) < 2:
            continue
        if cleaned in {"req", "추가", "삭제", "수정", "변경", "해주세요", "해줘", "하고", "그리고"}:
            continue
        tokens.append(cleaned)
    return list(dict.fromkeys(tokens))


def _build_adjacency(requirements: list[dict], graph: dict) -> dict[str, set[str]]:
    adjacency = {item["REQ_ID"]: set(item.get("depends_on") or []) for item in requirements if item.get("REQ_ID")}
    for item in requirements:
        req_id = item.get("REQ_ID")
        for dep in item.get("depends_on") or []:
            adjacency.setdefault(dep, set()).add(req_id)
            adjacency.setdefault(req_id, set()).add(dep)
    for edge in (graph or {}).get("edges") or []:
        source = edge.get("source")
        target = edge.get("target")
        if source and target:
            adjacency.setdefault(source, set()).add(target)
            adjacency.setdefault(target, set()).add(source)
    return adjacency


def _is_broad_revision_request(text: str) -> bool:
    lowered = (text or "").lower()
    broad_keywords = [
        "전체", "전부", "모두", "전체적으로", "전반", "전체 rtm", "전체 요구사항",
        "재구성", "재작성", "전면", "전체 검토", "대규모", "모든",
    ]
    return any(keyword in lowered for keyword in broad_keywords)


def _select_revision_context(requirements: list[dict], graph: dict, user_request: str) -> tuple[list[dict], dict]:
    if len(requirements) <= 12:
        return requirements, {"scope": "full_scope", "reason": "small_rtm"}

    if _is_broad_revision_request(user_request):
        return requirements, {"scope": "full_scope", "reason": "broad_request"}

    mentioned_ids = set(_extract_req_ids(user_request))
    adjacency = _build_adjacency(requirements, graph)
    selected_ids = set(mentioned_ids)

    for req_id in list(mentioned_ids):
        selected_ids.update(adjacency.get(req_id, set()))

    if not selected_ids:
        tokens = _tokenize_request(user_request)
        scored = []
        for item in requirements:
            haystack = " ".join([
                str(item.get("REQ_ID", "")),
                str(item.get("description", "")),
                str(item.get("category", "")),
                str(item.get("priority", "")),
            ]).lower()
            score = sum(1 for token in tokens if token in haystack)
            if score > 0:
                scored.append((score, item["REQ_ID"]))
        scored.sort(reverse=True)
        selected_ids.update(req_id for _, req_id in scored[:6])
        for req_id in list(selected_ids):
            selected_ids.update(list(adjacency.get(req_id, set()))[:2])

    if not selected_ids:
        return requirements, {"scope": "full_scope", "reason": "no_confident_match"}

    selected = [item for item in requirements if item.get("REQ_ID") in selected_ids]
    if len(selected) >= max(18, int(len(requirements) * 0.6)):
        return requirements, {"scope": "full_scope", "reason": "selection_too_large"}

    return selected, {"scope": "partial_scope", "reason": "targeted_subset"}


def _next_req_id(existing_ids: set[str]) -> str:
    numbers = [int(match.group(1)) for req_id in existing_ids for match in [re.match(r"REQ-(\d{3,})$", req_id or "")] if match]
    next_number = (max(numbers) if numbers else 0) + 1
    return f"REQ-{next_number:03d}"


def _apply_revision_patch(previous_rtm: list[dict], patch: ChatRevisionPatchOutput) -> list[dict]:
    ordered_ids = [item["REQ_ID"] for item in previous_rtm if item.get("REQ_ID")]
    req_map = {item["REQ_ID"]: {**item} for item in previous_rtm if item.get("REQ_ID")}
    reserved_ids = set(ordered_ids)
    deleted_ids = {req_id for req_id in patch.deleted_req_ids if req_id in req_map}

    for req_id in deleted_ids:
        req_map.pop(req_id, None)

    for modified in patch.modified_requirements:
        req_id = modified.REQ_ID
        if req_id not in req_map:
            continue
        current = req_map[req_id]
        patch_data = modified.model_dump(exclude_none=True)
        patch_data.pop("REQ_ID", None)
        current.update(patch_data)
        if "depends_on" in patch_data:
            current["depends_on"] = list(patch_data.get("depends_on") or [])

    existing_ids = set(req_map.keys())
    appended_ids = []
    for added in patch.added_requirements:
        item = _serialize(added) or {}
        candidate_id = (item.get("REQ_ID") or "").strip().upper()
        if not candidate_id or candidate_id in reserved_ids:
            candidate_id = _next_req_id(reserved_ids)
        normalized_item = _normalize_rtm([{**item, "REQ_ID": candidate_id}])[0]
        req_map[candidate_id] = normalized_item
        existing_ids.add(candidate_id)
        reserved_ids.add(candidate_id)
        appended_ids.append(candidate_id)

    valid_ids = set(req_map.keys())
    normalized = []
    seen_ids = set()
    for req_id in ordered_ids + appended_ids:
        if req_id not in req_map or req_id in seen_ids:
            continue
        item = req_map[req_id]
        item["depends_on"] = [dep for dep in item.get("depends_on") or [] if dep in valid_ids and dep != req_id]
        normalized.append(item)
        seen_ids.add(req_id)

    return normalized


def _merge_context_spec(previous_spec: dict, patch: ChatRevisionPatchOutput) -> dict:
    merged = dict(previous_spec or {})
    if patch.summary:
        merged["summary"] = patch.summary
    for field in [
        "key_decisions",
        "open_questions",
        "tech_stack_suggestions",
        "risk_factors",
        "next_steps",
    ]:
        value = getattr(patch, field, None)
        if value:
            merged[field] = value
    return merged
