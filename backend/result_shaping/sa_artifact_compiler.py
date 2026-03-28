"""
SA Artifact Compiler

LLM 추가 호출 없이 SA phase 결과를 시각화 친화적인 산출물로 컴파일한다.
"""

from __future__ import annotations

from typing import Any

from result_shaping.container_config import (
    LAYER_ORDER as _LAYER_ORDER,
    CONTAINER_GROUPS as _CONTAINER_GROUPS,
    CONTAINER_EDGES as _CONTAINER_EDGES,
    EXTERNAL_SYSTEM_SIGNALS as _EXTERNAL_SYSTEM_SIGNALS,
    LAYER_FALLBACK_CONTAINERS as _LAYER_FALLBACK_CONTAINERS,
)


def compile_sa_artifacts(result: dict[str, Any]) -> dict[str, Any]:
    sa_phase1 = result.get("sa_phase1") or {}
    sa_phase3 = result.get("sa_phase3") or {}
    sa_phase5 = result.get("sa_phase5") or {}
    sa_phase6 = result.get("sa_phase6") or {}
    sa_phase7 = result.get("sa_phase7") or {}
    sa_phase8 = result.get("sa_phase8") or {}

    container_diagram_spec = _build_container_diagram_spec(sa_phase1, sa_phase5)
    flowchart_spec = _build_flowchart_spec(sa_phase8)
    uml_component_spec = _build_uml_component_spec(sa_phase5, sa_phase7, sa_phase8)
    interface_definition_doc = _build_interface_definition_doc(sa_phase7)
    decision_table = _build_decision_table(sa_phase3, sa_phase5, sa_phase6, sa_phase7)

    return {
        "status": "Pass",
        "version": "1.0",
        "container_diagram_spec": container_diagram_spec,
        "flowchart_spec": flowchart_spec,
        "uml_component_spec": uml_component_spec,
        "interface_definition_doc": interface_definition_doc,
        "decision_table": decision_table,
    }


def _build_flowchart_spec(sa_phase8: dict[str, Any]) -> dict[str, Any]:
    batches = sa_phase8.get("parallel_batches") or []
    queue = sa_phase8.get("topo_queue") or []
    cycles = sa_phase8.get("cyclic_requirements") or []

    stages = []
    for index, batch in enumerate(batches, start=1):
        stages.append(
            {
                "stage": index,
                "kind": "parallel" if len(batch) > 1 else "sequential",
                "req_ids": batch,
            }
        )

    quality = _data_quality(["parallel_batches", "topo_queue"], {
        "parallel_batches": batches,
        "topo_queue": queue,
    })

    return {
        "stages": stages,
        "topo_queue": queue,
        "cycles": cycles,
        "summary": {
            "stage_count": len(stages),
            "parallel_stage_count": len([stage for stage in stages if stage["kind"] == "parallel"]),
            "cycle_count": len(cycles),
        },
        "data_quality": quality,
    }


def _build_uml_component_spec(
    sa_phase5: dict[str, Any],
    sa_phase7: dict[str, Any],
    sa_phase8: dict[str, Any],
) -> dict[str, Any]:
    mapped_requirements = sa_phase5.get("mapped_requirements") or []
    contracts = sa_phase7.get("interface_contracts") or []
    dependency_sources = sa_phase8.get("dependency_sources") or {}

    components = []
    req_ids = set()
    for req in mapped_requirements:
        req_id = req.get("REQ_ID")
        if not req_id:
            continue
        req_ids.add(req_id)
        components.append(
            {
                "id": req_id,
                "name": req_id,
                "layer": req.get("layer") or "Application",
                "description": req.get("description") or "",
                "file_path": req.get("file_path") or "",
                "canonical_id": req.get("canonical_id") or req_id,
                "source_kind": req.get("source_kind") or "code_scan",
            }
        )

    provided_interfaces = []
    for contract in contracts:
        contract_id = contract.get("contract_id") or ""
        req_id = contract_id[3:] if contract_id.startswith("IF-") else contract_id
        provided_interfaces.append(
            {
                "contract_id": contract_id,
                "component_id": req_id,
                "interface_name": contract.get("interface_name") or "",
                "input_spec": contract.get("input_spec") or "",
                "output_spec": contract.get("output_spec") or "",
                "layer": contract.get("layer") or "",
            }
        )

    relations = []
    for target, dep_entries in dependency_sources.items():
        for entry in dep_entries or []:
            source = entry.get("from")
            if not source:
                continue
            relations.append(
                {
                    "source": source,
                    "target": target,
                    "relation": "depends_on",
                    "relation_type": entry.get("source") or "data_flow",
                    "confidence": entry.get("confidence"),
                    "canonical": bool(entry.get("applied_to_canonical")),
                    "synthetic": entry.get("source") == "execution_order",
                }
            )

    quality = _data_quality(["mapped_requirements", "interface_contracts", "dependency_sources"], {
        "mapped_requirements": mapped_requirements,
        "interface_contracts": contracts,
        "dependency_sources": dependency_sources,
    })

    return {
        "components": components,
        "provided_interfaces": provided_interfaces,
        "relations": relations,
        "summary": {
            "component_count": len(components),
            "interface_count": len(provided_interfaces),
            "relation_count": len(relations),
        },
        "data_quality": quality,
    }


def _data_quality(required_keys: list[str], context: dict[str, Any]) -> dict[str, Any]:
    missing = [key for key in required_keys if not context.get(key)]
    total = max(1, len(required_keys))
    completeness = round(max(0.0, 1.0 - (len(missing) / total)), 2)
    return {
        "completeness": completeness,
        "missing_fields": missing,
    }


def _strip_module_prefix(text: str) -> str:
    """'핵심 분석 모듈: ' 접두사를 제거하고 마지막 경로 세그먼트(파일명)만 반환."""
    cleaned = (text or "").strip()
    if cleaned.startswith("핵심 분석 모듈:"):
        cleaned = cleaned.split(":", 1)[1].strip()
    parts = cleaned.replace("\\", "/").split("/")
    return parts[-1] if len(parts) > 1 else cleaned


def _match_container(file_path: str) -> str | None:
    """파일 경로를 논리 컨테이너 ID로 매핑. 매핑 불가 시 None."""
    path = (file_path or "").replace("\\", "/").lower().rstrip("/")
    for group in _CONTAINER_GROUPS:
        for exact in group.get("exact_paths") or []:
            if path == exact.lower():
                return group["id"]
    for group in _CONTAINER_GROUPS:
        for prefix in group.get("path_prefixes") or []:
            if path.startswith(prefix.lower()):
                return group["id"]
    return None


def _normalize_layer_name(layer: str) -> str:
    key = (layer or "").strip().lower()
    if "present" in key:
        return "presentation"
    if "app" in key:
        return "application"
    if "domain" in key or "business" in key:
        return "domain"
    if "infra" in key or "data" in key:
        return "infrastructure"
    if "security" in key or "auth" in key:
        return "security"
    return "unknown"


def _build_container_diagram_spec(
    sa_phase1: dict[str, Any],
    sa_phase5: dict[str, Any],
) -> dict[str, Any]:
    """파일 인벤토리를 논리 컨테이너로 그룹화한 Container-level 시스템 다이어그램 생성."""
    file_inventory = sa_phase1.get("file_inventory") or []
    detected_frameworks = sa_phase1.get("detected_frameworks") or []
    mapped_requirements = sa_phase5.get("mapped_requirements") or []

    # 1. 파일별 컨테이너 소속 집계 + raw imports 수집
    group_file_counts: dict[str, int] = {g["id"]: 0 for g in _CONTAINER_GROUPS}
    group_files: dict[str, list[str]] = {g["id"]: [] for g in _CONTAINER_GROUPS}
    group_req_ids: dict[str, list[str]] = {g["id"]: [] for g in _CONTAINER_GROUPS}
    all_raw_imports: set[str] = set()

    for file_entry in file_inventory:
        file_path = (file_entry.get("file") or "").replace("\\", "/").lower()
        container_id = _match_container(file_path)
        if container_id:
            group_file_counts[container_id] = group_file_counts.get(container_id, 0) + 1
            group_files.setdefault(container_id, []).append((file_entry.get("file") or "").replace("\\", "/"))
        for raw_import in file_entry.get("raw_imports") or []:
            all_raw_imports.add((raw_import or "").lower())

    # file_inventory 없을 때 mapped_requirements fallback
    if not file_inventory:
        for req in mapped_requirements:
            file_path = (req.get("file_path") or "").replace("\\", "/").lower()
            container_id = _match_container(file_path)
            if container_id:
                group_file_counts[container_id] = group_file_counts.get(container_id, 0) + 1
                if req.get("file_path"):
                    group_files.setdefault(container_id, []).append((req.get("file_path") or "").replace("\\", "/"))

    for req in mapped_requirements:
        req_id = req.get("REQ_ID")
        file_path = (req.get("file_path") or "").replace("\\", "/").lower()
        container_id = _match_container(file_path)
        if container_id and req_id:
            group_req_ids.setdefault(container_id, []).append(req_id)

    # file_path가 비어 컨테이너 매칭이 실패한 경우 layer 기준으로 최소 구성 복원
    if not any(group_file_counts.values()) and mapped_requirements:
        for req in mapped_requirements:
            req_id = req.get("REQ_ID")
            if not req_id:
                continue
            normalized_layer = _normalize_layer_name(req.get("layer") or "")
            target_containers = _LAYER_FALLBACK_CONTAINERS.get(normalized_layer, _LAYER_FALLBACK_CONTAINERS["unknown"])
            for container_id in target_containers:
                group_file_counts[container_id] = group_file_counts.get(container_id, 0) + 1
                group_req_ids.setdefault(container_id, []).append(req_id)
                group_files.setdefault(container_id, []).append(f"[layer-fallback] {req_id}")

    # 2. 존재하는 컨테이너만 component 노드로 변환
    present_ids: set[str] = {gid for gid, cnt in group_file_counts.items() if cnt > 0}
    components: list[dict[str, Any]] = []
    for group in _CONTAINER_GROUPS:
        if group["id"] not in present_ids:
            continue
        components.append({
            "id": group["id"],
            "label": group["label"],
            "layer": group["layer"],
            "description": group["description"],
            "file_count": group_file_counts.get(group["id"], 0),
            "files": sorted(dict.fromkeys(group_files.get(group["id"], []))),
            "mapped_requirements": sorted(dict.fromkeys(group_req_ids.get(group["id"], []))),
            "node_kind": "container",
        })

    # 3. 외부 시스템 탐지 (raw import 신호 + always_include)
    external_systems: list[dict[str, Any]] = []
    framework_str = " ".join(fw.lower() for fw in detected_frameworks)
    for ext in _EXTERNAL_SYSTEM_SIGNALS:
        if ext.get("always_include"):
            external_systems.append({
                "id": ext["id"],
                "label": ext["label"],
                "layer": "External",
                "description": ext["description"],
                "node_kind": "external",
            })
            continue
        detected = (
            any(sig in raw_imp for sig in ext["signals"] for raw_imp in all_raw_imports)
            or any(sig in framework_str for sig in ext["signals"])
        )
        if detected:
            external_systems.append({
                "id": ext["id"],
                "label": ext["label"],
                "layer": "External",
                "description": ext["description"],
                "node_kind": "external",
            })

    # 4. 엣지: 양쪽 노드가 모두 존재하는 경우만 포함
    all_node_ids = {c["id"] for c in components} | {e["id"] for e in external_systems}
    connections: list[dict[str, Any]] = []

    entrypoint_id = None
    for candidate in ["electron-shell", "react-ui", "fastapi-server", "transport-layer"]:
        if candidate in all_node_ids:
            entrypoint_id = candidate
            break

    for edge in _CONTAINER_EDGES:
        if edge["source"] in all_node_ids and edge["target"] in all_node_ids:
            connections.append({
                "source": edge["source"],
                "target": edge["target"],
                "protocol": edge["protocol"],
                "edge_type": edge["edge_type"],
            })

    if "users" in all_node_ids and entrypoint_id:
        connections.insert(
            0,
            {
                "source": "users",
                "target": entrypoint_id,
                "protocol": "User Interaction",
                "edge_type": "external",
            },
        )

    return {
        "components": components,
        "external_systems": external_systems,
        "connections": connections,
        "summary": {
            "component_count": len(components),
            "external_count": len(external_systems),
            "connection_count": len(connections),
        },
        "data_quality": {
            "completeness": 1.0 if components else 0.0,
            "missing_fields": [],
        },
    }


def _build_interface_definition_doc(sa_phase7: dict[str, Any]) -> dict[str, Any]:
    contracts = sa_phase7.get("interface_contracts") or []
    guardrails = sa_phase7.get("guardrails") or []

    normalized_contracts = []
    for contract in contracts:
        normalized_contracts.append(
            {
                "contract_id": contract.get("contract_id"),
                "layer": contract.get("layer"),
                "interface_name": contract.get("interface_name"),
                "input_spec": contract.get("input_spec"),
                "output_spec": contract.get("output_spec"),
                "error_handling": contract.get("error_handling"),
            }
        )

    quality = _data_quality(["interface_contracts"], {
        "interface_contracts": contracts,
    })

    return {
        "title": "SA Interface Definition",
        "contracts": normalized_contracts,
        "guardrails": guardrails,
        "summary": {
            "contract_count": len(normalized_contracts),
            "guardrail_count": len(guardrails),
        },
        "data_quality": quality,
    }


def _build_decision_table(
    sa_phase3: dict[str, Any],
    sa_phase5: dict[str, Any],
    sa_phase6: dict[str, Any],
    sa_phase7: dict[str, Any],
) -> dict[str, Any]:
    feasibility_status = sa_phase3.get("status") or "Needs_Clarification"
    authz_matrix = sa_phase6.get("authz_matrix") or []
    guardrails = sa_phase7.get("guardrails") or []
    mapped_requirements = sa_phase5.get("mapped_requirements") or []

    req_to_layer = {
        req.get("REQ_ID"): req.get("layer")
        for req in mapped_requirements
        if req.get("REQ_ID")
    }

    rows: list[dict[str, Any]] = []

    if authz_matrix:
        for item in authz_matrix:
            req_id = item.get("req_id") or item.get("REQ_ID") or "-"
            restriction = item.get("restriction_level") or "Authenticated"
            has_targeted_guardrail = any(req_id in text for text in guardrails)
            action = "ALLOW"
            if restriction in {"Authorized", "InternalOnly"}:
                action = "REVIEW"
            if feasibility_status not in {"Pass", "Skipped"}:
                action = "REVIEW"

            rows.append(
                {
                    "req_id": req_id,
                    "layer": req_to_layer.get(req_id) or "Unknown",
                    "restriction_level": restriction,
                    "allowed_roles": item.get("allowed_roles") or [],
                    "feasibility_status": feasibility_status,
                    "guardrail_applied": has_targeted_guardrail,
                    "action": action,
                }
            )
    else:
        for req in mapped_requirements:
            req_id = req.get("REQ_ID") or "-"
            rows.append(
                {
                    "req_id": req_id,
                    "layer": req.get("layer") or "Unknown",
                    "restriction_level": "Unknown",
                    "allowed_roles": [],
                    "feasibility_status": feasibility_status,
                    "guardrail_applied": False,
                    "action": "REVIEW",
                }
            )

    quality = _data_quality(["sa_phase3", "sa_phase6", "sa_phase7"], {
        "sa_phase3": sa_phase3,
        "sa_phase6": sa_phase6,
        "sa_phase7": sa_phase7,
    })

    return {
        "columns": [
            "req_id",
            "layer",
            "restriction_level",
            "allowed_roles",
            "feasibility_status",
            "guardrail_applied",
            "action",
        ],
        "rows": rows,
        "guardrails": guardrails,
        "data_quality": quality,
    }
