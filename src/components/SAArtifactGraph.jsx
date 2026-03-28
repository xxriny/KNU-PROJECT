import React, { useEffect, useMemo, useRef, useState } from "react";
import ReactFlow, {
  Background,
  Handle,
  MarkerType,
  Position,
  useEdgesState,
  useNodesState,
} from "reactflow";
import "reactflow/dist/style.css";

const FIT_VIEW_OPTIONS = { padding: 0.1, minZoom: 0.05, maxZoom: 1.5 };

function SAArtifactNode({ data, selected }) {
  const accent = data?.accent || "#64748b";
  const dimmed = Boolean(data?.dimmed);
  const highlighted = Boolean(data?.highlighted);
  const titleClass = "text-[12px] font-bold";
  const containerPadding = "px-2 py-2";

  return (
    <div
      className={`relative w-fit h-fit max-w-[104px] rounded-xl border bg-slate-900/95 transition-opacity duration-150 ${containerPadding}`}
      style={{
        borderColor: accent,
        opacity: dimmed ? 0.28 : 1,
        boxShadow: highlighted ? `0 0 0 1px ${accent}55, 0 0 24px ${accent}22` : "none",
      }}
    >
      <Handle type="target" position={Position.Left} style={{ width: 7, height: 7, background: accent, border: "none" }} />
      <Handle type="source" position={Position.Right} style={{ width: 7, height: 7, background: accent, border: "none" }} />
      <div className={`${titleClass} text-slate-100 tracking-tight`} style={{ fontFamily: "'Pretendard', 'Inter', system-ui, sans-serif" }}>{data?.title || "-"}</div>
      <div
        className="mt-1 text-[12px] text-slate-400 leading-snug transition-opacity duration-150"
        style={{ opacity: 1, maxHeight: 80, overflow: "hidden", fontFamily: "'Inter', system-ui, sans-serif" }}
      >
        {data?.subtitle || ""}
      </div>
      {data?.badge && (
        <div className="inline-flex rounded px-1.5 py-0.5 text-[11px] mt-2" style={{ backgroundColor: `${accent}25`, color: accent, fontFamily: "'Inter', system-ui, sans-serif", letterSpacing: "0.01em" }}>
          {data.badge}
        </div>
      )}
      {selected && <div className="pointer-events-none absolute inset-0 rounded-xl ring-2 ring-blue-400/60" />}
    </div>
  );
}

const nodeTypes = { saArtifactNode: SAArtifactNode };

export default function SAArtifactGraph({ graph, emptyText = "그래프 데이터가 없습니다", onNodeClick }) {
  const flowRef = useRef(null);
  const hoverLeaveTimerRef = useRef(null);
  const [selectedId, setSelectedId] = useState(null);
  const [hoveredId, setHoveredId] = useState(null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const nodesInput = graph?.nodes || [];
  const edgesInput = graph?.edges || [];

  const initialNodes = useMemo(
    () => nodesInput.map((node) => ({ ...node, type: "saArtifactNode" })),
    [nodesInput]
  );
  const initialEdges = useMemo(
    () =>
      edgesInput.map((edge) => ({
        markerEnd: { type: MarkerType.ArrowClosed, color: edge?.style?.stroke || "#64748b", width: 14, height: 14 },
        ...edge,
      })),
    [edgesInput]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => setNodes(initialNodes), [initialNodes, setNodes]);
  useEffect(() => setEdges(initialEdges), [initialEdges, setEdges]);

  const adjacency = useMemo(() => {
    const map = {};
    for (const edge of edgesInput) {
      if (!map[edge.source]) map[edge.source] = new Set();
      if (!map[edge.target]) map[edge.target] = new Set();
      map[edge.source].add(edge.target);
      map[edge.target].add(edge.source);
    }
    return map;
  }, [edgesInput]);

  useEffect(() => {
    const activeId = hoveredId || selectedId;
    if (!activeId) {
      setNodes(initialNodes);
      setEdges(initialEdges);
      return;
    }

    const connected = new Set([activeId, ...(adjacency[activeId] ? [...adjacency[activeId]] : [])]);

    setNodes(
      initialNodes.map((node) => ({
        ...node,
        data: {
          ...node.data,
          highlighted: connected.has(node.id),
          dimmed: !connected.has(node.id),
        },
      }))
    );

    setEdges(
      initialEdges.map((edge) => {
        const active = edge.source === activeId || edge.target === activeId;
        const relationType = edge?.data?.relationType || edge?.data?.edge_type || "";
        const hideLowPriorityLabel = zoomLevel < 0.78 && ["execution_order", "internal", "node dispatch"].includes(String(relationType));
        return {
          ...edge,
          label: hideLowPriorityLabel ? "" : edge.label,
          style: {
            ...(edge.style || {}),
            opacity: active ? 1 : 0.18,
          },
          labelStyle: {
            ...(edge.labelStyle || {}),
            fill: hideLowPriorityLabel ? "transparent" : active ? "#e2e8f0" : "#64748b",
          },
          labelBgStyle: hideLowPriorityLabel
            ? { fill: "transparent", stroke: "transparent" }
            : { fill: "#0b0f1a", fillOpacity: 1, stroke: "#172033", strokeWidth: 1 },
          labelBgPadding: hideLowPriorityLabel ? [0, 0] : [8, 4],
          labelShowBg: !hideLowPriorityLabel,
        };
      })
    );
  }, [adjacency, hoveredId, selectedId, initialNodes, initialEdges, setEdges, setNodes, zoomLevel]);

  useEffect(() => {
    if (!flowRef.current || nodes.length === 0) return;
    requestAnimationFrame(() => {
      flowRef.current?.fitView({ ...FIT_VIEW_OPTIONS, duration: 260 });
    });
  }, [nodes.length, edges.length]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") setSelectedId(null);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  if (nodesInput.length === 0) {
    return <div className="h-full flex items-center justify-center text-slate-600 text-sm">{emptyText}</div>;
  }

  const selectedNode = nodes.find((node) => node.id === selectedId);

  return (
    <div className="sa-artifact-graph flex h-full bg-slate-950">
      <div className="relative flex-1">
        <ReactFlow
          onInit={(instance) => {
            flowRef.current = instance;
          }}
          onMove={(_, viewport) => setZoomLevel(viewport.zoom)}
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          onNodeClick={(_, node) => {
            setSelectedId((prev) => (prev === node.id ? null : node.id));
            if (typeof onNodeClick === "function") {
              onNodeClick(node);
            }
          }}
          onNodeMouseEnter={(_, node) => {
            clearTimeout(hoverLeaveTimerRef.current);
            setHoveredId(node.id);
          }}
          onNodeMouseLeave={() => {
            hoverLeaveTimerRef.current = setTimeout(() => setHoveredId(null), 40);
          }}
          fitView
          fitViewOptions={FIT_VIEW_OPTIONS}
          nodesDraggable={false}
          elementsSelectable={true}
          defaultEdgeOptions={{
            labelStyle: { fill: "#cbd5e1", fontSize: 11, fontWeight: 500, fontFamily: "'JetBrains Mono', 'Fira Code', monospace" },
            labelBgStyle: { fill: "#0b0f1a", fillOpacity: 1, stroke: "#172033", strokeWidth: 1 },
            labelBgPadding: [8, 4],
            labelBgBorderRadius: 6,
            labelShowBg: true,
          }}
          minZoom={0.05}
          maxZoom={2.0}
          proOptions={{ hideAttribution: true }}
          style={{ background: "#0b0f1a" }}
        >
          <Background color="#1e293b" gap={26} size={1} />
          {(graph?.legend || []).length > 0 && (
            <div className="absolute left-4 top-4 z-10 flex flex-wrap items-center gap-2 rounded-lg border border-slate-700 bg-slate-900/95 px-3 py-2 text-[12px] shadow-lg backdrop-blur-sm">
              {(graph.legend || []).map((item) => (
                <span key={item.label} className="inline-flex items-center gap-1.5 text-slate-300">
                  <span style={{ width: 10, height: 10, borderRadius: 3, background: item.color, display: "inline-block" }} />
                  {item.label}
                </span>
              ))}
            </div>
          )}
        </ReactFlow>
      </div>

      {selectedNode && (
        <div className="w-96 border-l border-slate-800 bg-slate-900 px-4 py-4 text-slate-300 overflow-y-auto">
          <div className="flex items-center justify-between mb-1">
            <div className="text-[13px] font-mono text-blue-300">
              {selectedNode.data?.detail?.module_id || selectedNode.id}
            </div>
            <button
              onClick={() => setSelectedId(null)}
              className="text-slate-500 hover:text-slate-200 transition-colors p-1 -mr-1 rounded-md text-[15px] leading-none"
              aria-label="닫기"
            >
              ✕
            </button>
          </div>
          <div className="mt-2 text-[14px] text-slate-200 leading-snug">{selectedNode.data?.title || "-"}</div>
          <div className="mt-1 text-[13px] text-slate-400 leading-snug">{selectedNode.data?.subtitle || "-"}</div>
          {Array.isArray(selectedNode.data?.detail?.function_names) && selectedNode.data.detail.function_names.length > 0 && (
            <div className="mt-3">
              <div className="text-[12px] uppercase tracking-wider text-slate-500 mb-1">기능 목록</div>
              <div className="rounded border border-slate-800 bg-slate-950/70 overflow-hidden">
                <div className="grid grid-cols-[40px_1fr_120px] gap-0 border-b border-slate-800 bg-slate-900/70 text-[11px] text-slate-500">
                  <div className="px-2 py-1.5">#</div>
                  <div className="px-2 py-1.5">기능명</div>
                  <div className="px-2 py-1.5">ID</div>
                </div>
                <div className="max-h-56 overflow-y-auto">
                  {selectedNode.data.detail.function_names.map((name, idx) => {
                    const reqId = selectedNode.data?.detail?.req_ids?.[idx] || "-";
                    return (
                      <div
                        key={`${name}-${idx}`}
                        className="grid grid-cols-[40px_1fr_120px] gap-0 border-b border-slate-900 last:border-b-0 text-[12px]"
                      >
                        <div className="px-2 py-1.5 text-slate-500">{idx + 1}</div>
                        <div className="px-2 py-1.5 text-slate-200 break-words leading-snug">{name || "-"}</div>
                        <div className="px-2 py-1.5 text-blue-300 font-mono truncate">{reqId}</div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
          {selectedNode.data?.badge && (
            <div className="mt-2 text-[13px] text-slate-400">{selectedNode.data.badge}</div>
          )}
          {selectedNode.data?.detail?.description && (
            <div className="mt-3 rounded border border-slate-800 bg-slate-950/60 p-3 text-[13px] text-slate-300">
              {selectedNode.data.detail.description}
            </div>
          )}
          {selectedNode.data?.detail?.file_path && selectedNode.data.detail.file_path !== "-" && (
            <div className="mt-3">
              <div className="text-[12px] uppercase tracking-wider text-slate-500 mb-1">파일 루트</div>
              <div className="rounded bg-slate-950/80 p-2 text-[12px] font-mono text-slate-300 break-all">{selectedNode.data.detail.file_path}</div>
            </div>
          )}
          {Array.isArray(selectedNode.data?.detail?.files) && selectedNode.data.detail.files.length > 0 && (
            <div className="mt-3">
              <div className="text-[12px] uppercase tracking-wider text-slate-500 mb-1">파일 목록</div>
              <div className="max-h-48 overflow-y-auto rounded bg-slate-950/80 p-2 space-y-1">
                {selectedNode.data.detail.files.map((file) => (
                  <div key={file} className="text-[12px] font-mono text-slate-300 break-all">{file}</div>
                ))}
              </div>
            </div>
          )}
          {Array.isArray(selectedNode.data?.detail?.mapped_requirements) && selectedNode.data.detail.mapped_requirements.length > 0 && (
            <div className="mt-3">
              <div className="text-[12px] uppercase tracking-wider text-slate-500 mb-1">매핑 요구사항</div>
              <div className="flex flex-wrap gap-1.5">
                {selectedNode.data.detail.mapped_requirements.map((reqId) => (
                  <span key={reqId} className="px-2 py-0.5 rounded bg-blue-600/15 text-blue-300 text-[12px] border border-blue-800/30 font-mono">
                    {reqId}
                  </span>
                ))}
              </div>
            </div>
          )}
          {Array.isArray(selectedNode.data?.detail?.depends_on) && selectedNode.data.detail.depends_on.length > 0 && (
            <div className="mt-3">
              <div className="text-[12px] uppercase tracking-wider text-slate-500 mb-1">의존 모듈</div>
              <div className="flex flex-wrap gap-1.5">
                {selectedNode.data.detail.depends_on.map((reqId) => (
                  <span key={reqId} className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[12px] border border-slate-700 font-mono">
                    {reqId}
                  </span>
                ))}
              </div>
            </div>
          )}
          {selectedNode.data?.detail?.mapping_reason && (
            <div className="mt-3">
              <div className="text-[12px] uppercase tracking-wider text-slate-500 mb-1">매핑 근거</div>
              <div className="rounded bg-slate-950/80 p-2 text-[12px] text-slate-300 whitespace-pre-wrap">{selectedNode.data.detail.mapping_reason}</div>
            </div>
          )}
          {Array.isArray(selectedNode.data?.detail?.layer_evidence) && selectedNode.data.detail.layer_evidence.length > 0 && (
            <div className="mt-3">
              <div className="text-[12px] uppercase tracking-wider text-slate-500 mb-1">증거</div>
              <ul className="space-y-1">
                {selectedNode.data.detail.layer_evidence.map((item, idx) => (
                  <li key={`${item}-${idx}`} className="text-[12px] text-slate-400">- {item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
