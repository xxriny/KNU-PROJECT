import re

from pipeline.state import PipelineState, make_sget


TOKEN_ALIASES = {
    "file_contents": "files",
    "processed_data": "analysis_result",
    "final_result_uri": "analysis_result",
}
TOKEN_STOPWORDS = {
    "str", "int", "dict", "list", "bool", "null", "float", "any",
    "status", "message", "error", "errors", "success", "timestamp",
    "config", "context", "metadata", "summary", "details", "response",
    "result", "data", "request_id", "job_id", "user_id", "session_id",
    "trace_id", "params", "options", "settings", "code", "info",
}
LOW_SIGNAL_TOKENS = {
    "analysis_config", "analysis_type", "output_data", "input_data",
    "error_details", "level", "tags", "metric_name", "value",
}
MIN_CANONICAL_CONFIDENCE = 0.65


def _extract_contract_tokens(spec_text: str, structured_fields: list[dict] | None = None) -> set[str]:
    text = (spec_text or "").lower()
    tokens = set(re.findall(r"[a-z_]{3,}", text))
    for field in structured_fields or []:
        name = (field.get("name") or "").lower()
        role = (field.get("role") or "").lower()
        type_spec = (field.get("type_spec") or field.get("type") or "").lower()
        tokens.update(re.findall(r"[a-z_]{3,}", " ".join(part for part in (name, role, type_spec) if part)))
    normalized = set()
    for token in tokens:
        if token in TOKEN_STOPWORDS:
            continue
        normalized.add(token)
        alias = TOKEN_ALIASES.get(token)
        if alias:
            normalized.add(alias)
    return normalized


def _collect_contract_token_frequency(contracts: list[dict]) -> dict[str, int]:
    frequency: dict[str, int] = {}
    for contract in contracts:
        output_tokens = _extract_contract_tokens(contract.get("output_spec", ""), contract.get("output_fields"))
        for token in output_tokens:
            frequency[token] = frequency.get(token, 0) + 1
    return frequency


def _is_cross_cutting_contract(contract: dict) -> bool:
    name = (contract.get("interface_name") or "").lower()
    layer = (contract.get("layer") or "").lower()
    return any(token in name for token in ["log", "metric", "record_metric", "log_event", "logger"]) or layer == "infrastructure"


def _calculate_dependency_confidence(common_tokens: list[str], token_frequency: dict[str, int], module_count: int, source_contract: dict, target_contract: dict) -> float:
    strong_tokens = [token for token in common_tokens if token not in LOW_SIGNAL_TOKENS]
    weak_tokens = [token for token in common_tokens if token in LOW_SIGNAL_TOKENS]
    base = 0.55 + min(0.2, len(strong_tokens) * 0.08)
    frequency_penalty = 0.0
    for token in common_tokens:
        if token_frequency.get(token, 0) > max(1, module_count // 2):
            frequency_penalty -= 0.2
    if _is_cross_cutting_contract(source_contract) or _is_cross_cutting_contract(target_contract):
        frequency_penalty -= 0.15
    if not strong_tokens:
        frequency_penalty -= 0.15
    return round(max(0.3, min(0.92, base + frequency_penalty)), 2)


def _parse_req_id_from_contract(contract_id: str) -> str:
    if not contract_id:
        return ""
    if contract_id.startswith("IF-"):
        return contract_id[3:]
    return contract_id


def _normalize_module_path(value: str) -> str:
    return (value or "").strip().replace("\\", "/").lower().rstrip("/")


def _module_aliases(item: dict) -> set[str]:
    aliases: set[str] = set()
    file_path = _normalize_module_path(item.get("file_path") or item.get("description") or "")
    if file_path.startswith("핵심 분석 모듈:"):
        file_path = _normalize_module_path(file_path.split(":", 1)[1])
    canonical_id = (item.get("canonical_id") or "").strip().lower()
    if canonical_id:
        aliases.add(canonical_id)
    if file_path:
        aliases.add(file_path)
        no_ext = file_path
        for suffix in (".py", ".js", ".jsx", ".ts", ".tsx"):
            if no_ext.endswith(suffix):
                no_ext = no_ext[: -len(suffix)]
                aliases.add(no_ext)
                break
        aliases.add(file_path.rsplit("/", 1)[-1])
        aliases.add(no_ext.rsplit("/", 1)[-1])
        if no_ext.endswith("/__init__"):
            aliases.add(no_ext[: -len("/__init__")])
    return {alias for alias in aliases if alias}


def _synthesize_import_dependencies(items: list[dict], dependency_sources: dict[str, list[dict]], inferred_dependencies: list[dict]) -> list[dict]:
    merged_items = [{**item, "depends_on": list(item.get("depends_on", []) or [])} for item in items]
    alias_to_req: dict[str, str] = {}

    for item in merged_items:
        req_id = item.get("REQ_ID", "")
        for alias in _module_aliases(item):
            alias_to_req.setdefault(alias, req_id)

    for item in merged_items:
        target_req = item.get("REQ_ID", "")
        target_imports = item.get("import_hints", []) or []
        seen_sources = {entry.get("from") for entry in dependency_sources.get(target_req, [])}
        for import_hint in target_imports:
            source_req = alias_to_req.get(_normalize_module_path(import_hint))
            if not source_req or source_req == target_req or source_req in seen_sources:
                continue
            dependency_sources[target_req].append({
                "source": "code_import",
                "from": source_req,
                "confidence": 0.88,
                "tokens": [],
                "applied_to_canonical": True,
            })
            inferred_dependencies.append({
                "target": target_req,
                "depends_on": source_req,
                "source": "code_import",
                "confidence": 0.88,
                "tokens": [],
            })
            if source_req not in item["depends_on"]:
                item["depends_on"].append(source_req)
            seen_sources.add(source_req)

        item["depends_on"] = sorted(dict.fromkeys(item["depends_on"]))

    return merged_items


def _synthesize_dependencies(items: list[dict], semantic_graph: dict, sa_phase7: dict) -> tuple[list[dict], dict, list[dict]]:
    id_set = {item.get("REQ_ID") for item in items if item.get("REQ_ID")}
    dependency_sources: dict[str, list[dict]] = {rid: [] for rid in id_set}
    inferred_dependencies: list[dict] = []
    merged_items = []

    for item in items:
        req_id = item.get("REQ_ID", "")
        deps = []
        for dep in item.get("depends_on", []) or []:
            if dep in id_set and dep not in deps:
                deps.append(dep)
                dependency_sources[req_id].append({"source": "explicit", "from": dep, "confidence": 1.0})

        for edge in (semantic_graph.get("edges", []) or []):
            if edge.get("relation") == "depends_on" and edge.get("target") == req_id:
                dep = edge.get("source")
                if dep in id_set:
                    dependency_sources[req_id].append({"source": "semantic", "from": dep, "confidence": 0.8})

        merged_items.append({**item, "depends_on": deps})
    merged_items = _synthesize_import_dependencies(merged_items, dependency_sources, inferred_dependencies)

    contract_by_req = {}
    for contract in sa_phase7.get("interface_contracts", []) or []:
        req_id = _parse_req_id_from_contract(contract.get("contract_id", ""))
        if req_id in id_set:
            contract_by_req[req_id] = contract

    token_frequency = _collect_contract_token_frequency(list(contract_by_req.values()))
    module_count = max(1, len(contract_by_req))

    for target in merged_items:
        target_req = target.get("REQ_ID", "")
        target_contract = contract_by_req.get(target_req)
        if not target_contract:
            continue
        input_tokens = _extract_contract_tokens(target_contract.get("input_spec", ""), target_contract.get("input_fields"))
        if not input_tokens:
            continue
        for source_req, source_contract in contract_by_req.items():
            if source_req == target_req:
                continue
            output_tokens = _extract_contract_tokens(source_contract.get("output_spec", ""), source_contract.get("output_fields"))
            common = sorted(input_tokens & output_tokens)
            if not common:
                continue
            confidence = _calculate_dependency_confidence(common, token_frequency, module_count, source_contract, target_contract)
            strong_common = [token for token in common if token not in LOW_SIGNAL_TOKENS]
            applied_to_canonical = bool(strong_common and confidence >= MIN_CANONICAL_CONFIDENCE)
            dependency_sources[target_req].append({
                "source": "data_flow",
                "from": source_req,
                "confidence": confidence,
                "tokens": common[:4],
                "applied_to_canonical": applied_to_canonical,
            })
            inferred_dependencies.append({
                "target": target_req,
                "depends_on": source_req,
                "source": "data_flow",
                "confidence": confidence,
                "tokens": common[:4],
            })
            if applied_to_canonical and source_req not in target["depends_on"]:
                target["depends_on"].append(source_req)
        target["depends_on"] = sorted(dict.fromkeys(target["depends_on"]))

    return merged_items, dependency_sources, inferred_dependencies

def _topo_sort_with_batches(items: list[dict]) -> tuple[list[str], list[list[str]], list[str]]:
    ids = [item.get("REQ_ID", "") for item in items if item.get("REQ_ID")]
    id_set = set(ids)

    indeg = {rid: 0 for rid in ids}
    adj = {rid: [] for rid in ids}

    for item in items:
        rid = item.get("REQ_ID", "")
        if not rid:
            continue
        for dep in item.get("depends_on", []) or []:
            if dep in id_set:
                adj[dep].append(rid)
                indeg[rid] += 1

    # 1. 결정론적 실행을 위해 정렬하여 큐 초기화
    current_batch = sorted([rid for rid, d in indeg.items() if d == 0])
    
    order = []
    parallel_batches = []

    # 2. 세대별(Generation) BFS 탐색으로 진정한 병렬 그룹 생성
    while current_batch:
        parallel_batches.append(current_batch)
        next_batch = []
        
        for cur in current_batch:
            order.append(cur)
            for nxt in adj[cur]:
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    next_batch.append(nxt)
        
        # 다음 배치도 일관된 순서를 위해 정렬
        current_batch = sorted(next_batch)

    cycles = sorted([rid for rid, d in indeg.items() if d > 0])
    return order, parallel_batches, cycles


def sa_phase8_node(state: PipelineState) -> dict:
    sget = make_sget(state)

    rtm = sget("requirements_rtm", [])
    if not rtm:
        phase5 = sget("sa_phase5", {}) or {}
        rtm = phase5.get("mapped_requirements", []) or []
    semantic_graph = sget("semantic_graph", {}) or {}
    sa_phase7 = sget("sa_phase7", {}) or {}
    synthesized_items, dependency_sources, inferred_dependencies = _synthesize_dependencies(rtm, semantic_graph, sa_phase7)
    
    # 3. 개선된 토폴로지 정렬 함수 호출
    queue, parallel_batches, cycles = _topo_sort_with_batches(synthesized_items)

    status = "Fail" if cycles else ("Pass" if queue else "Needs_Clarification")
    output = {
        "status": status,
        "topo_queue": queue,
        "cyclic_requirements": cycles,
        "parallel_batches": parallel_batches,  # [[REQ-1, REQ-2], [REQ-3], ...] 형태로 병렬 최적화됨
        "dependency_sources": dependency_sources,
        "inferred_dependencies": inferred_dependencies,
    }

    sa_output = {
        "code_analysis": sget("sa_phase1", {}),
        "impact_analysis": sget("sa_phase2", {}),
        "feasibility": sget("sa_phase3", {}),
        "dependency_sandbox": sget("sa_phase4", {}),
        "architecture_mapping": sget("sa_phase5", {}),
        "security_boundary": sget("sa_phase6", {}),
        "interface_contracts": sget("sa_phase7", {}),
        "topology_queue": output,
    }

    return {
        "sa_phase8": output,
        "sa_output": sa_output,
        "thinking_log": (sget("thinking_log", []) or []) + [{"node": "sa_phase8", "thinking": f"위상 정렬 완료 (총 {len(parallel_batches)}개의 병렬 개발 페이즈 생성)"}],
        "current_step": "sa_phase8_done",
    }

