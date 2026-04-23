import React, { memo, useEffect, useMemo, useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Handle,
  Position,
  useReactFlow,
  ReactFlowProvider,
  BaseEdge,
} from '@xyflow/react';
import { useShallow } from 'zustand/react/shallow';
import '@xyflow/react/dist/style.css';
import ELK from 'elkjs/lib/elk.bundled.js';
import { SmartStepEdge, getSmartEdge } from '@tisoap/react-flow-smart-edge';

// 스토어 및 외부 액션 임포트
import {
  useERDStore,
  onNodesChange,
  onEdgesChange,
  onConnect,
  setElements
} from '../../store/useERDStore';

// 1. Elk.js 레이아웃 엔진 설정
const elk = new ELK();

const elkOptions = {
  'elk.algorithm': 'layered',
  'elk.direction': 'RIGHT',
  'elk.layered.spacing.nodeNodeBetweenLayers': '200',
  'elk.spacing.nodeNode': '80',
  'elk.layered.nodePlacement.strategy': 'NETWORK_SIMPLEX',
  'elk.edgeRouting': 'ORTHOGONAL',
  'elk.layered.crossingMinimization.strategy': 'LAYER_SWEEP',
};

const getLayoutedElements = async (nodes, edges) => {
  const graph = {
    id: 'root',
    layoutOptions: elkOptions,
    children: nodes.map((node) => {
      const columnCount = node.data.columns?.length || 1;
      const estimatedHeight = 50 + (columnCount * 40); // 헤더 + 컬럼 높이 추산
      return {
        id: node.id,
        width: 320, // TableNode fixed width
        height: estimatedHeight,
      };
    }),
    edges: edges.map((edge) => ({
      id: edge.id,
      sources: [edge.source],
      targets: [edge.target],
    })),
  };

  try {
    const layoutedGraph = await elk.layout(graph);
    const layoutedNodes = nodes.map((node) => {
      const elkNode = layoutedGraph.children?.find((n) => n.id === node.id);
      return {
        ...node,
        position: {
          x: elkNode?.x || 0,
          y: elkNode?.y || 0,
        },
      };
    });
    return { nodes: layoutedNodes, edges };
  } catch (error) {
    console.error("ELK Layout Error:", error);
    return { nodes, edges };
  }
};

// 2. Crow's Foot 카디널리티 SVG 마커 정의
const CrowsFootMarkers = () => (
  <svg style={{ position: 'absolute', width: 0, height: 0 }} aria-hidden="true">
    <defs>
      <marker
        id="crow-zero-many"
        viewBox="0 0 40 40"
        refX="38"
        refY="20"
        markerWidth="16"
        markerHeight="16"
        orient="auto-start-reverse"
      >
        <path d="M 5,10 L 35,20 L 5,30" fill="none" stroke="#94a3b8" strokeWidth="3" strokeLinejoin="round" />
        <circle cx="15" cy="20" r="6" fill="#0f172a" stroke="#94a3b8" strokeWidth="2" />
        <line x1="35" y1="20" x2="22" y2="20" stroke="#94a3b8" strokeWidth="3" />
      </marker>

      <marker
        id="crow-one-only"
        viewBox="0 0 40 40"
        refX="38"
        refY="20"
        markerWidth="16"
        markerHeight="16"
        orient="auto-start-reverse"
      >
        <line x1="15" y1="5" x2="15" y2="35" stroke="#94a3b8" strokeWidth="4" />
        <line x1="25" y1="5" x2="25" y2="35" stroke="#94a3b8" strokeWidth="4" />
        <line x1="0" y1="20" x2="40" y2="20" stroke="#94a3b8" strokeWidth="2" />
      </marker>

      <marker
        id="crow-one-many"
        viewBox="0 0 40 40"
        refX="38"
        refY="20"
        markerWidth="16"
        markerHeight="16"
        orient="auto-start-reverse"
      >
        <path d="M 5,10 L 35,20 L 5,30" fill="none" stroke="#94a3b8" strokeWidth="3" strokeLinejoin="round" />
        <line x1="18" y1="5" x2="18" y2="35" stroke="#94a3b8" strokeWidth="4" />
        <line x1="35" y1="20" x2="25" y2="20" stroke="#94a3b8" strokeWidth="3" />
      </marker>
    </defs>
  </svg>
);

// 3. 커스텀 테이블 노드
const TableNode = memo(({ data, id }) => {
  return (
    <div className="bg-[#0f172a] border-2 border-slate-700 rounded-lg shadow-2xl w-[320px] overflow-visible font-sans border-t-indigo-500">
      <div className="bg-slate-800/80 px-4 py-3 flex items-center justify-between border-b border-slate-700 rounded-t-lg">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-indigo-500 rounded-sm rotate-45 shadow-[0_0_8px_rgba(99,102,241,0.5)]" />
          <span className="text-slate-100 font-black text-sm uppercase tracking-tighter">{data.label}</span>
        </div>
        <span className="text-slate-500 text-[10px] font-mono opacity-50">#TABLE</span>
      </div>

      <div className="flex flex-col">
        {(data.columns || []).map((col, index) => {
          const colLow = col.name.toLowerCase();
          const isPK = (col.constraints || "").toLowerCase().includes("pk") || !!col.isPK;
          const isFK = (col.constraints || "").toLowerCase().includes("fk") || !!col.isFK || colLow.endsWith("_id");

          return (
            <div
              key={`${id}-${colLow}-${index}`}
              className="relative flex justify-between items-center px-4 py-2.5 border-b border-slate-800/50 last:border-b-0 hover:bg-slate-800/30 transition-all group text-xs"
            >
              <Handle
                type="target"
                position={Position.Left}
                id={`target-${colLow}`}
                className={`!w-2 !h-2 !bg-blue-500 !-left-1 !border-none transition-all ${isFK ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}
                style={{ top: '50%', transform: 'translateY(-50%)' }}
              />

              <div className="flex items-center gap-3">
                <span className={`text-[9px] font-black w-5 text-center rounded px-1 py-0.5 ${isPK ? "bg-amber-500/10 text-amber-500 border border-amber-500/20" : isFK ? "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20" : "text-slate-600"}`}>
                  {isPK ? "PK" : isFK ? "FK" : "  "}
                </span>
                <span className="text-slate-300 font-semibold tracking-tight">{col.name}</span>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-slate-500 font-mono text-[10px] opacity-70 italic">{col.type || 'varchar'}</span>
                {isPK && <span className="text-amber-500/50 text-[10px]">🔑</span>}
              </div>

              <Handle
                type="source"
                position={Position.Right}
                id={`source-${colLow}`}
                className={`!w-2 !h-2 !bg-amber-500 !-right-1 !border-none transition-all ${isPK ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}
                style={{ top: '50%', transform: 'translateY(-50%)' }}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
});

// 4. 지능형 스마트 엣지
const CustomSmartEdge = (props) => {
  const { sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, nodes } = props;

  const smartEdgeResponse = getSmartEdge({
    sourcePosition,
    targetPosition,
    sourceX,
    sourceY,
    targetX,
    targetY,
    nodes,
    options: {
      nodePadding: 20,
      gridRatio: 10,
    },
  });

  if (!smartEdgeResponse) {
    return <BaseEdge {...props} />;
  }

  const { svgPathString } = smartEdgeResponse;

  return (
    <BaseEdge
      id={props.id}
      path={svgPathString}
      markerStart={props.markerStart}
      markerEnd={props.markerEnd}
      style={{ stroke: '#64748b', strokeWidth: 2 }}
    />
  );
};

const nodeTypes = {
  tableNode: TableNode,
};

const edgeTypes = {
  smart: CustomSmartEdge,
};

function ERDFlow({ tables }) {
  const { nodes, edges } = useERDStore(
    useShallow((state) => ({ nodes: state.nodes, edges: state.edges }))
  );

  const { fitView } = useReactFlow();

  const initializeDiagram = useCallback(async () => {
    if (!tables || tables.length === 0) return;

    const initialNodes = [];
    const initialEdges = [];
    const tableNames = tables.map(t => t.table_name.toLowerCase());

    // 1. 노드 생성
    tables.forEach((table) => {
      initialNodes.push({
        id: table.table_name.toLowerCase(),
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          label: table.table_name,
          columns: table.columns,
        },
      });
    });

    // 2. 엣지 생성
    tables.forEach((table) => {
      const sourceTableLow = table.table_name.toLowerCase();
      (table.columns || []).forEach((col) => {
        const colLow = col.name.toLowerCase();
        const constLow = (col.constraints || "").toLowerCase();
        let targetTable = null;
        let targetField = "id";

        const fkMatch = constLow.match(/fk\s*\(?([^). \n]+)(?:\.([^)]+))?\)?/) ||
          constLow.match(/references\s+([^(\s]+)(?:\(([^)]+)\))?/);

        if (fkMatch) {
          targetTable = fkMatch[1].toLowerCase();
          targetField = (fkMatch[2] || "id").toLowerCase();
        } else if (colLow.endsWith("id") || colLow.endsWith("_id")) {
          const base = colLow.replace(/_?id$/, "");
          targetTable = tableNames.find(tn => tn === base || tn === base + "s" || base === tn + "s");
        }

        if (targetTable && targetTable !== sourceTableLow) {
          const actualTargetTable = tables.find(t => t.table_name.toLowerCase() === targetTable);
          if (actualTargetTable) {
            const hasTargetField = actualTargetTable.columns.some(c => c.name.toLowerCase() === targetField);
            const finalTargetField = hasTargetField ? targetField : (actualTargetTable.columns[0]?.name.toLowerCase() || "id");

            const isJunctionTable = sourceTableLow.includes('member') || sourceTableLow.includes('mapping');

            initialEdges.push({
              id: `edge-${targetTable}-${sourceTableLow}-${colLow}`,
              source: targetTable,
              target: sourceTableLow,
              sourceHandle: `source-${finalTargetField}`,
              targetHandle: `target-${colLow}`,
              type: 'smart',
              markerStart: 'crow-one-only',
              markerEnd: isJunctionTable ? 'crow-zero-many' : 'crow-one-many',
            });
          }
        }
      });
    });

    // 3. ELK 레이아웃 적용
    const { nodes: layoutedNodes, edges: layoutedEdges } = await getLayoutedElements(initialNodes, initialEdges);

    setElements(layoutedNodes, layoutedEdges);

    setTimeout(() => fitView({ padding: 0.2, duration: 1000 }), 100);
  }, [tables, fitView]);

  useEffect(() => {
    initializeDiagram();
  }, [initializeDiagram]);

  return (
    <div className="w-full h-full relative bg-[#020617]">
      <CrowsFootMarkers />
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        fitView
      >
        <Background color="#1e293b" gap={30} variant="dots" className="opacity-20" />
      </ReactFlow>

      {/* HUD Info */}
      <div className="absolute top-8 left-8 z-10 space-y-2 pointer-events-none">
        <div className="flex items-center gap-3">
          <div className="w-1.5 h-6 bg-indigo-500 rounded-full" />
          <h3 className="text-white text-2xl font-black tracking-tighter uppercase leading-none">Architectural ERD Engine</h3>
        </div>
        <p className="text-slate-500 text-[11px] font-mono tracking-[0.3em] uppercase pl-4">ELK Hierarchical / Crow's Foot / Smart Routing</p>
      </div>

      {/* Legend */}
      <div className="absolute bottom-8 right-8 z-10 bg-slate-900/80 border border-slate-800 p-4 rounded-xl backdrop-blur-xl shadow-2xl flex flex-col gap-3">
        <div className="flex items-center gap-3 text-[10px] font-mono text-slate-400">
          <div className="w-4 h-3 bg-amber-500/20 border border-amber-500/40 rounded-sm" /> <span>PK / IDENTIFIER</span>
        </div>
        <div className="flex items-center gap-3 text-[10px] font-mono text-slate-400">
          <div className="w-4 h-3 bg-indigo-500/20 border border-indigo-500/40 rounded-sm" /> <span>FK / RELATIONSHIP</span>
        </div>
        <div className="border-t border-slate-800 my-1" />
        <div className="flex items-center gap-3 text-[10px] font-mono text-slate-400">
          <div className="w-6 h-0.5 bg-slate-500" /> <span>SMART A* ROUTING</span>
        </div>
      </div>
    </div>
  );
}

export default function SADatabaseER({ tables }) {
  return (
    <div className="h-[900px] w-full bg-[#020617] rounded-3xl border border-slate-800/50 overflow-hidden shadow-2xl relative">
      <ReactFlowProvider>
        <ERDFlow tables={tables} />
      </ReactFlowProvider>
    </div>
  );
}