"""
노드 4 — 지식 그래프 기반 시맨틱 인덱싱 (Semantic Indexer)

Pydantic 구조화 출력 강제. RTM의 의존성을 시맨틱 엣지로 변환.
source_dir이 주어지면 AST 스캔으로 REQ_ID ↔ 소스코드 함수 단위 시맨틱 링크를 생성한다.
"""

import json
from typing import List
from pydantic import BaseModel, Field
from pipeline.state import PipelineState
from pipeline.schemas import SemanticIndexerOutput, CodeFunctionLink
from pipeline.utils import call_structured_with_thinking, call_structured
from pipeline.ast_scanner import extract_functions, summarize_for_llm
from pipeline.chroma_client import add_knowledge

GRAPH_SYSTEM_PROMPT = """\
당신은 시맨틱 지식 그래프(Semantic Knowledge Graph) 생성 전문가입니다.
RTM 요구사항들을 지식 그래프로 변환하세요.

[규칙]
1. 노드(Nodes): 각 요구사항을 {id, label, category, tags[2~3개의 한국어 키워드]} 형태로 변환하세요.
2. 엣지(Edges): 의존성 → "depends_on", 의미적 유사성 → "related_to", 하위 기능 → "part_of"로 관계를 정의하세요.
3. "related_to"는 무방향 관계로 간주하고, A→B 단방향 한 번만 작성하세요. B→A 중복은 만들지 마세요.
4. 내부 추론(thinking)은 3줄 이내로 간결하게 작성하세요."""


def _dedupe_semantic_edges(edges: list[dict]) -> list[dict]:
    deduped = []
    seen_edges = set()
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        relation = edge.get("relation", "depends_on")
        if not source or not target:
            continue

        if relation == "related_to":
            edge_key = (relation, *sorted((source, target)))
        else:
            edge_key = (relation, source, target)

        if edge_key in seen_edges:
            continue

        deduped.append({
            "source": source,
            "target": target,
            "relation": relation,
        })
        seen_edges.add(edge_key)

    return deduped

# REQ_ID ↔ 함수 매핑용 스키마 (semantic_indexer 내부 전용)
class _FuncMapping(BaseModel):
    req_id: str = Field(description="REQ_ID (예: REQ-001)")
    file: str = Field(description="소스파일 상대 경로")
    func_name: str = Field(description="함수명")
    lineno: int = Field(description="함수 시작 라인")
    confidence: float = Field(description="매핑 신뢰도 0.0 ~ 1.0")
    reason: str = Field(default="", description="매핑 근거 (한국어 1문장)")

class _CodeMappingOutput(BaseModel):
    thinking: str = Field(default="", description="매핑 추론 (3줄 이내)")
    mappings: List[_FuncMapping] = Field(default_factory=list, description="REQ_ID-함수 매핑 목록")

CODE_MAPPING_SYSTEM_PROMPT = """\
당신은 PM이 정의한 요구사항(REQ_ID)과 소스코드 함수를 연결하는 시맨틱 링크 전문가입니다.

[규칙]
1. 각 함수의 이름, 파일 경로, docstring을 읽고 가장 관련성 높은 REQ_ID와 매핑하세요.
2. 명확한 연관이 없으면 mappings에 포함하지 마세요 (confidence < 0.4 제외).
3. 하나의 함수는 하나의 REQ_ID에만 매핑하세요 (가장 관련성 높은 것 선택).
4. confidence: 1.0=완전 일치, 0.7=강한 관련, 0.5=보통, 0.4=약한 관련.
5. reason은 한국어 1문장으로 작성하세요.
6. thinking은 3줄 이내."""


def semantic_indexer_node(state: PipelineState) -> dict:
    def sget(key, default=None):
        if hasattr(state, "get"):
            val = state.get(key, default)
        else:
            val = getattr(state, key, default)
        return default if val is None else val

    reqs = sget("rtm_matrix", [])
    if not reqs:
        return {
            "semantic_graph": {"nodes": [], "edges": []},
            "current_step": "semantic_indexer_done",
            "thinking_log": sget("thinking_log", []) + [{"node": "semantic_indexer", "thinking": "No requirements."}],
        }

    compact = [{"REQ_ID": r.get("REQ_ID"), "description": r.get("description"),
                "category": r.get("category"), "depends_on": r.get("depends_on", [])}
               for r in reqs]
    user_msg = f"Build semantic knowledge graph:\n```json\n{json.dumps(compact, ensure_ascii=False)}\n```"

    try:
        result, thinking = call_structured_with_thinking(
            api_key=sget("api_key", ""),
            model=sget("model", "gemini-2.5-flash"),
            schema=SemanticIndexerOutput,
            system_prompt=GRAPH_SYSTEM_PROMPT,
            user_msg=user_msg,
            max_retries=3,
        )

        nodes = [n.model_dump() for n in result.nodes]
        edges = _dedupe_semantic_edges([e.model_dump() for e in result.edges])

    except Exception as e:
        # 폴백: RTM 의존성에서 직접 그래프 생성
        nodes = [{"id": r["REQ_ID"], "label": r.get("description", ""),
                  "category": r.get("category", ""), "tags": [], "code_links": []} for r in reqs]
        edges = []
        for r in reqs:
            for dep in r.get("depends_on", []):
                edges.append({"source": dep, "target": r["REQ_ID"], "relation": "depends_on"})
        edges = _dedupe_semantic_edges(edges)
        thinking = f"Fallback from deps: {e}"

    # ── AST 기반 코드 링크 (source_dir가 있을 때만) ──────────────
    code_links_by_req: dict[str, list] = {}
    source_dir = sget("source_dir", "")
    ast_thinking = ""

    if source_dir:
        functions = extract_functions(source_dir, max_functions=300)
        if functions:
            # [수정 1] JSON 문자열 절단 방지: 전체를 다 넘기기
            req_summary = json.dumps(
                [{"REQ_ID": r.get("REQ_ID"), "description": r.get("description")} for r in reqs],
                ensure_ascii=False
            )
            func_summary = summarize_for_llm(functions, max_chars=6000)

            mapping_msg = (
                f"=== 요구사항 목록 ===\n{req_summary}\n\n"
                f"=== 소스코드 함수 목록 (file:func_name:line — docstring) ===\n{func_summary}\n\n"
                f"각 함수가 어떤 REQ_ID를 구현하는지 매핑하세요."
            )
            try:
                mapping_result = call_structured(
                    api_key=sget("api_key", ""),
                    model=sget("model", "gemini-2.5-flash"),
                    schema=_CodeMappingOutput,
                    system_prompt=CODE_MAPPING_SYSTEM_PROMPT,
                    user_msg=mapping_msg,
                    max_retries=2,
                    temperature=0.2,
                )
                ast_thinking = mapping_result.thinking
                for m in mapping_result.mappings:
                    if m.confidence >= 0.4:
                        code_links_by_req.setdefault(m.req_id, []).append({
                            "file": m.file,
                            "func_name": m.func_name,
                            "lineno": m.lineno,
                            "confidence": round(m.confidence, 2),
                            "reason": m.reason,
                        })
            except Exception as map_err:
                ast_thinking = f"코드 매핑 실패: {map_err}"

    # 노드에 code_links 병합
    for node in nodes:
        req_id = node.get("id", "")
        node.setdefault("code_links", [])
        if req_id in code_links_by_req:
            node["code_links"] = code_links_by_req[req_id]

    graph = {"nodes": nodes, "edges": edges}
    combined_thinking = thinking + (f"\n[AST] {ast_thinking}" if ast_thinking else "")

    # ── ChromaDB에 저장 ──────────────────────
    run_id = sget("run_id", "")
    project_name = sget("metadata", {}).get("project_name", "unknown") if sget("metadata") else "unknown"
    
    if run_id:
        # [수정 2] 실패에 대한 내구성(Resilience) 확보: try-except를 for 루프 내부로 이동
        for node in nodes:
            req_id = node.get("id", "")
            description = node.get("label", "")
            code_links = node.get("code_links", [])
            
            if req_id and description:
                try:
                    add_knowledge(
                        run_id=run_id,
                        req_id=req_id,
                        description=description,
                        code_links=code_links,
                        project_name=project_name,
                        node="semantic_indexer"
                    )
                except Exception as chroma_err:
                    # 개별 노드 저장 실패 시 로그만 남기고 다음 노드로 계속 진행
                    combined_thinking += f"\n[ChromaDB] {req_id} 저장 실패: {chroma_err}"

    return {
        "semantic_graph": graph,
        "thinking_log": sget("thinking_log", []) + [{"node": "semantic_indexer", "thinking": combined_thinking}],
        "current_step": "semantic_indexer_done",
    }
