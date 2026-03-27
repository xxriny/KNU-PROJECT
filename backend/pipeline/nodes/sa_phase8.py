from pipeline.state import PipelineState

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
    def sget(key, default=None):
        if hasattr(state, "get"):
            val = state.get(key, default)
        else:
            val = getattr(state, key, default)
        return default if val is None else val

    rtm = sget("requirements_rtm", []) or sget("rtm_matrix", []) or []
    if not rtm:
        phase5 = sget("sa_phase5", {}) or {}
        rtm = phase5.get("mapped_requirements", []) or []
    
    # 3. 개선된 토폴로지 정렬 함수 호출
    queue, parallel_batches, cycles = _topo_sort_with_batches(rtm)

    status = "Fail" if cycles else ("Pass" if queue else "Needs_Clarification")
    output = {
        "status": status,
        "topo_queue": queue,
        "cyclic_requirements": cycles,
        "parallel_batches": parallel_batches,  # [[REQ-1, REQ-2], [REQ-3], ...] 형태로 병렬 최적화됨
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