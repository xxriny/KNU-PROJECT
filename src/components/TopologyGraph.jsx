/**
 * TopologyGraph — ReactFlow 기반 인터랙티브 의존성 그래프
 *
 * v1 topology_view.py (Tkinter 캔버스)의 핵심 로직을 ReactFlow로 포팅.
 *
 * 기능:
 * - BFS 위상 정렬 기반 계층형 레이아웃 (v1 _layout_layered 직접 포팅)
 * - 카테고리별 SVG 도형 (Backend:직사각형, Frontend/AI:원, Infra/DB:다이아몬드, Security:육각형)
 * - 우선순위별 색상 (Must-have:빨강, Should-have:노랑, Could-have:초록)
 * - 노드 드래그/줌/팬 (ReactFlow 기본 제공)
 * - 노드 클릭 → 우측 사이드 패널 상세 정보 + 의존성 노드 클릭 네비게이션
 */

import React, { useMemo, useState, useCallback, useEffect, useRef } from "react";
import ReactFlow, {
  Background,
  MarkerType,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
} from "reactflow";
import "reactflow/dist/style.css";

// ─── 상수 (v1 CATEGORY_SHAPES / PRIORITY_COLORS 대응) ─────────────────────────

const PRIORITY_COLORS = {
  "Must-have":   "#ef4444",
  "Should-have": "#eab308",
  "Could-have":  "#22c55e",
};
const DEFAULT_COLOR = "#64748b";

const CATEGORY_SHAPES = {
  Backend:        "rect",
  Frontend:       "oval",
  Infrastructure: "hexagon",
  Database:       "hexagon",
  Security:       "hexagon",
  "AI/ML":        "oval",
};

// v1: NODE_R=26, H_GAP=130, V_GAP=90 → ReactFlow 노드 크기에 맞춰 스케일업
const NODE_W = 332;
const NODE_H = 162;
const H_GAP  = 230;
const V_GAP  = 110;

// ─── BFS 위상 정렬 기반 계층형 레이아웃 (v1 _layout_layered 포트) ────────────

function computeLayeredLayout(nodes, rtmMap) {
  if (!nodes.length) return {};

  const nodeIds = new Set(nodes.map((n) => n.id));

  // 의존성 맵 (RTM depends_on 기반, v1과 동일)
  const depMap = {};
  for (const n of nodes) {
    const rtm = rtmMap[n.id] || {};
    depMap[n.id] = (rtm.depends_on || []).filter((d) => nodeIds.has(d));
  }

  // 역방향 맵 — 누가 나를 의존하는가
  const revMap = {};
  for (const nid of nodeIds) revMap[nid] = [];
  for (const [nid, deps] of Object.entries(depMap)) {
    for (const dep of deps) {
      if (revMap[dep]) revMap[dep].push(nid);
    }
  }

  // BFS로 레이어 할당
  const layer = {};
  const inDeg = {};
  for (const nid of nodeIds) inDeg[nid] = (depMap[nid] || []).length;

  const queue = [];
  for (const nid of nodeIds) {
    if (inDeg[nid] === 0) { layer[nid] = 0; queue.push(nid); }
  }

  let head = 0;
  while (head < queue.length) {
    const cur = queue[head++];
    for (const child of revMap[cur] || []) {
      layer[child] = Math.max(layer[child] ?? 0, (layer[cur] ?? 0) + 1);
      inDeg[child]--;
      if (inDeg[child] === 0) queue.push(child);
    }
  }

  // 순환 의존성 노드 처리 (v1 max_layer + 1)
  const vals = Object.values(layer);
  const maxL = vals.length ? Math.max(...vals) : 0;
  for (const nid of nodeIds) {
    if (layer[nid] === undefined) layer[nid] = maxL + 1;
  }

  // 레이어별 그룹화 + 우선순위 정렬 (v1 priority_order)
  const pOrd = { "Must-have": 0, "Should-have": 1, "Could-have": 2 };
  const groups = {};
  for (const [nid, lv] of Object.entries(layer)) {
    if (!groups[lv]) groups[lv] = [];
    groups[lv].push(nid);
  }
  for (const lv of Object.keys(groups)) {
    groups[lv].sort((a, b) => {
      const pa = pOrd[rtmMap[a]?.priority] ?? 2;
      const pb = pOrd[rtmMap[b]?.priority] ?? 2;
      return pa - pb || a.localeCompare(b);
    });
  }

  // 좌표 계산: x = 레이어, y = 세로 중앙 정렬 (v1 start_y 로직 대응)
  const positions = {};
  const sortedLvs = Object.keys(groups).map(Number).sort((a, b) => a - b);
  for (const lv of sortedLvs) {
    const nids = groups[lv];
    const x = lv * (NODE_W + H_GAP) + 60;
    const totalH = nids.length * (NODE_H + V_GAP) - V_GAP;
    const startY = Math.max(40, 350 - totalH / 2);
    nids.forEach((nid, i) => {
      positions[nid] = { x, y: startY + i * (NODE_H + V_GAP) };
    });
  }

  return positions;
}

// ─── 커스텀 노드 컴포넌트: SVG 도형 + 텍스트 ─────────────────────────────────

function ShapeNode({ data, selected }) {
  const { label, nodeId, category, priority } = data;
  const accentColor = PRIORITY_COLORS[priority] || DEFAULT_COLOR;
  const shape = CATEGORY_SHAPES[category] || "oval";
  const nodeWidth = NODE_W;
  const nodeHeight = NODE_H;

  const renderShape = () => {
    if (shape === "oval") {
      return (
        <ellipse
          cx={nodeWidth / 2}
          cy={nodeHeight / 2}
          rx={nodeWidth / 2 - 4}
          ry={nodeHeight / 2 - 4}
          fill="#0f172a"
          stroke={accentColor}
          strokeWidth={selected ? 3 : 2}
        />
      );
    }

    if (shape === "hexagon") {
      return (
        <polygon
          points={`44,4 ${nodeWidth - 44},4 ${nodeWidth - 4},${nodeHeight / 2} ${nodeWidth - 44},${nodeHeight - 4} 44,${nodeHeight - 4} 4,${nodeHeight / 2}`}
          fill="#0f172a"
          stroke={accentColor}
          strokeWidth={selected ? 3 : 2}
        />
      );
    }

    if (shape === "diamond") {
      return (
        <polygon
          points={`${nodeWidth / 2},4 ${nodeWidth - 4},${nodeHeight / 2} ${nodeWidth / 2},${nodeHeight - 4} 4,${nodeHeight / 2}`}
          fill="#0f172a"
          stroke={accentColor}
          strokeWidth={selected ? 3 : 2}
        />
      );
    }

    return (
      <rect
        x={4}
        y={4}
        width={nodeWidth - 8}
        height={nodeHeight - 8}
        rx={14}
        fill="#0f172a"
        stroke={accentColor}
        strokeWidth={selected ? 3 : 2}
      />
    );
  };

  return (
    <div className="relative" style={{ width: nodeWidth, height: nodeHeight }}>
      <Handle
        type="target" position={Position.Left}
        style={{ width: 6, height: 6, background: accentColor, border: "none", opacity: 0.7 }}
      />
      <Handle
        type="source" position={Position.Right}
        style={{ width: 6, height: 6, background: accentColor, border: "none", opacity: 0.7 }}
      />
      <svg
        className="absolute inset-0 h-full w-full"
        viewBox={`0 0 ${nodeWidth} ${nodeHeight}`}
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        {renderShape()}
      </svg>

      <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-10 py-6 pointer-events-none">
        <span className="font-mono text-[13px] font-semibold leading-none tracking-wide text-slate-100">
          {nodeId}
        </span>
        <span className="text-center text-[15px] leading-relaxed tracking-wide text-slate-200">
          {label && label.length > 46 ? label.slice(0, 44) + ".." : label}
        </span>
        <span className="text-sm tracking-wide text-slate-200">{category || "Uncategorized"}</span>
      </div>
    </div>
  );
}

const nodeTypes = { shapeNode: ShapeNode };

// ─── 메인 컴포넌트 ────────────────────────────────────────────────────────────

export default function TopologyGraph({ semanticGraph, requirementsRtm }) {
  const [selectedId, setSelectedId] = useState(null);
  const flowRef = useRef(null);
  const didAutoFitRef = useRef(false);

  // RTM 맵 (REQ_ID → RTM 항목)
  const rtmMap = useMemo(() => {
    const m = {};
    for (const r of requirementsRtm || []) {
      m[r.REQ_ID || r.id] = r;
    }
    return m;
  }, [requirementsRtm]);

  // ReactFlow용 노드/엣지 계산
  const { initNodes, initEdges } = useMemo(() => {
    const gNodes = semanticGraph?.nodes || [];
    const gEdges = semanticGraph?.edges  || [];
    if (!gNodes.length) return { initNodes: [], initEdges: [] };

    const positions = computeLayeredLayout(gNodes, rtmMap);

    const initNodes = gNodes.map((n) => {
      const rtm = rtmMap[n.id] || {};
      return {
        id:       n.id,
        type:     "shapeNode",
        position: positions[n.id] || { x: 0, y: 0 },
        data: {
          label:    n.label || n.id,
          nodeId:   n.id,
          category: n.category || rtm.category || "",
          priority: rtm.priority || "Could-have",
        },
      };
    });

    const initEdges = gEdges.map((e, i) => ({
      id:     `e${i}-${e.source}-${e.target}`,
      source: e.source,
      target: e.target,
      type:   "smoothstep",
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: "#475569",
        width: 14, height: 14,
      },
      style: { stroke: "#334155", strokeWidth: 1.5 },
    }));

    return { initNodes, initEdges };
  }, [semanticGraph, rtmMap]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initEdges);

  // semanticGraph 변경 시 동기화 (useNodesState 초깃값은 최초 1회만 적용)
  useEffect(() => { setNodes(initNodes); }, [initNodes, setNodes]);
  useEffect(() => { setEdges(initEdges); }, [initEdges, setEdges]);

  // 그래프 데이터가 갱신되면 자동 맞춤을 다시 허용하되, 렌더 사이클마다 반복 실행되지는 않도록 한다.
  useEffect(() => {
    didAutoFitRef.current = false;
  }, [semanticGraph]);

  // 데이터 로드 직후 1회만 fitView를 실행해 초기 배율을 안정화한다.
  useEffect(() => {
    if (!flowRef.current || didAutoFitRef.current || nodes.length === 0) return;

    didAutoFitRef.current = true;
    requestAnimationFrame(() => {
      flowRef.current?.fitView({ padding: 0.14, maxZoom: 1.25, duration: 260 });
    });
  }, [nodes.length, edges.length]);

  const onNodeClick = useCallback((_, node) => {
    setSelectedId((prev) => (prev === node.id ? null : node.id));
  }, []);

  // 선택된 노드의 RTM/그래프 데이터
  const selRtm  = selectedId ? (rtmMap[selectedId]  || {}) : null;
  const selNode = selectedId
    ? ((semanticGraph?.nodes || []).find((n) => n.id === selectedId) || null)
    : null;

  return (
    <div className="flex h-full bg-slate-950">
      {/* ── ReactFlow 캔버스 ─────────────────────────────────────────────────── */}
      <div className="relative flex-1">
        <ReactFlow
          onInit={(instance) => { flowRef.current = instance; }}
          proOptions={{ hideAttribution: true }}
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          minZoom={0.42}
          maxZoom={2.4}
          deleteKeyCode={null}
          style={{ background: "#0b0f1a" }}
        >
          <Background color="#1e293b" gap={24} size={1} />

          {/* 범례 (좌측 상단 고정) */}
          <div className="absolute left-4 top-4 z-10 flex flex-wrap items-center gap-3 rounded-lg border border-slate-700 bg-slate-900/95 px-3 py-2 shadow-lg backdrop-blur-sm">
            <span className="text-sm text-slate-300">우선순위</span>
            {[
              ["Must-have",   "#ef4444"],
              ["Should-have", "#eab308"],
              ["Could-have",  "#22c55e"],
            ].map(([lbl, col]) => (
              <span key={lbl} className="flex items-center gap-1.5 text-sm text-slate-200">
                <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: col }} />
                {lbl}
              </span>
            ))}
            <span className="text-slate-600">│</span>
            <span className="text-sm text-slate-300">도형</span>
            {["▭ Backend", "◯ Front/AI", "◆ Infra/DB", "⬡ Security"].map((lbl) => (
              <span key={lbl} className="text-sm text-slate-300">{lbl}</span>
            ))}
          </div>
        </ReactFlow>
      </div>

      {/* ── 사이드 상세 패널 (v1 _select_node 대응) ─────────────────────────── */}
      {selectedId && (
        <div className="w-80 border-l border-slate-800 bg-slate-900 px-4 py-5 pb-7 text-slate-300 overflow-y-auto flex flex-col gap-6">
          {/* 헤더 */}
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <span className="font-mono text-sm font-bold text-slate-100">
                {selectedId}
              </span>
              <p className="mt-2 text-[15px] tracking-wide text-slate-200 leading-relaxed">
                {selRtm?.description || selNode?.label || selectedId}
              </p>
            </div>
            <button
              onClick={() => setSelectedId(null)}
              className="shrink-0 rounded px-1.5 py-0.5 text-slate-500 hover:text-slate-200"
            >
              ✕
            </button>
          </div>

          {/* 카테고리 + 우선순위 뱃지 */}
          <div className="flex flex-wrap gap-2">
            {selRtm?.category && (
              <span className="rounded bg-slate-800 px-2 py-1 text-sm text-slate-300">
                {selRtm.category}
              </span>
            )}
            {selRtm?.priority && (
              <span className="rounded bg-slate-800 px-2 py-1 text-sm font-semibold text-slate-100">
                {selRtm.priority}
              </span>
            )}
          </div>

          {/* 우선순위 근거 */}
          {selRtm?.rationale && (
            <SideSection title="우선순위 근거">
              <p className="text-slate-200 leading-relaxed">{selRtm.rationale}</p>
            </SideSection>
          )}

          {/* 테스트 기준 */}
          {selRtm?.test_criteria && (
            <SideSection title="테스트 기준">
              <p className="text-slate-200 leading-relaxed">{selRtm.test_criteria}</p>
            </SideSection>
          )}

          {/* 의존성 — 클릭 시 해당 노드로 이동 */}
          <SideSection title="의존성">
            {(selRtm?.depends_on || []).length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {selRtm.depends_on.map((dep) => (
                  <button
                    key={dep}
                    onClick={() => setSelectedId(dep)}
                    className="rounded bg-slate-800 px-2 py-1 text-sm font-mono text-blue-300 hover:bg-slate-700/70"
                  >
                    {dep}
                  </button>
                ))}
              </div>
            ) : (
              <span className="text-slate-500">없음</span>
            )}
          </SideSection>

          {/* 시맨틱 태그 (semantic_indexer 결과) */}
          {selNode?.tags?.length > 0 && (
            <SideSection title="태그">
              <div className="flex flex-wrap gap-2">
                {selNode.tags.map((t) => (
                  <span key={t} className="rounded bg-slate-800 px-2 py-1 text-sm text-slate-300">
                    {t}
                  </span>
                ))}
              </div>
            </SideSection>
          )}
        </div>
      )}
    </div>
  );
}

function SideSection({ title, children }) {
  return (
    <div className="mb-2">
      <div className="mb-2 text-sm tracking-wide text-slate-400">
        {title}
      </div>
      {children}
    </div>
  );
}
