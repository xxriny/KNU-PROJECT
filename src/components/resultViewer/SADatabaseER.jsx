import React, { useState, useEffect, useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Handle,
  Position,
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
  useReactFlow,
  ReactFlowProvider,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Save, RotateCcw, MessageSquare, History, Edit3 } from 'lucide-react';
import useAppStore from '../../store/useAppStore';

// --- 커스텀 노드 정의 ---

const EntityNode = ({ data, id }) => {
  const isDarkMode = useAppStore((state) => state.isDarkMode);
  const [isEditing, setIsEditing] = useState(false);
  const [label, setLabel] = useState(data.label);

  const onBlur = () => {
    setIsEditing(false);
    if (label !== data.label) data.onRename(id, label);
  };

  return (
    <div className={`
      border-2 transition-all duration-300 group
      min-w-[140px] px-6 py-4 flex items-center justify-center relative
      ${isDarkMode 
        ? "bg-[#0f172a] border-indigo-500 text-white shadow-[0_0_15px_rgba(99,102,241,0.2)]" 
        : "bg-white border-black text-black shadow-[4px_4px_0_rgba(0,0,0,0.1)]"}
    `} onDoubleClick={() => setIsEditing(true)}>
      <Handle type="target" position={Position.Top} className="!opacity-0" />
      <Handle type="source" position={Position.Bottom} className="!opacity-0" />
      <Handle type="source" position={Position.Left} id="left" className="!opacity-0" />
      <Handle type="source" position={Position.Right} id="right" className="!opacity-0" />
      {isEditing ? (
        <input autoFocus className="bg-transparent border-b border-indigo-400 outline-none text-center font-bold text-sm w-full" value={label} onChange={(e) => setLabel(e.target.value)} onBlur={onBlur} onKeyDown={(e) => e.key === 'Enter' && onBlur()} />
      ) : (
        <span className="font-bold text-sm tracking-widest uppercase whitespace-nowrap">{label}</span>
      )}
    </div>
  );
};

const AttributeNode = ({ data, id }) => {
  const isDarkMode = useAppStore((state) => state.isDarkMode);
  const [isEditing, setIsEditing] = useState(false);
  const [label, setLabel] = useState(data.label);

  const onBlur = () => {
    setIsEditing(false);
    if (label !== data.label) data.onRename(id, label);
  };

  return (
    <div className={`
      border-2 rounded-[100%/100%] px-10 py-2.5 transition-all duration-300 group
      min-w-[140px] w-fit flex items-center justify-center relative
      ${isDarkMode 
        ? "bg-[#1e293b] border-slate-500 text-slate-200 hover:border-indigo-400" 
        : "bg-white border-black text-black shadow-[2px_2px_0_rgba(0,0,0,0.05)] hover:bg-slate-50"}
    `} onDoubleClick={() => setIsEditing(true)}>
      <Handle type="target" position={Position.Top} className="!opacity-0" />
      <Handle type="source" position={Position.Bottom} className="!opacity-0" />
      {isEditing ? (
        <input autoFocus className="bg-transparent border-b border-indigo-400 outline-none text-center text-[11px] w-full" value={label} onChange={(e) => setLabel(e.target.value)} onBlur={onBlur} onKeyDown={(e) => e.key === 'Enter' && onBlur()} />
      ) : (
        <span className={`text-[11px] whitespace-nowrap tracking-tight px-1 ${data.isPK ? (isDarkMode ? "underline decoration-2 underline-offset-4 font-extrabold text-slate-100" : "underline decoration-2 underline-offset-4 font-extrabold") : "font-medium"}`}>{label}</span>
      )}
    </div>
  );
};

const RelationshipNode = ({ data, id }) => {
  const isDarkMode = useAppStore((state) => state.isDarkMode);
  const [isEditing, setIsEditing] = useState(false);
  const [label, setLabel] = useState(data.label);

  const onBlur = () => {
    setIsEditing(false);
    if (label !== data.label) data.onRename(id, label);
  };

  return (
    <div className="relative w-28 h-28 flex items-center justify-center group transition-all duration-300" onDoubleClick={() => setIsEditing(true)}>
      <div className={`absolute inset-0 border-2 rotate-45 transition-all ${isDarkMode ? "bg-[#0f172a] border-indigo-400 shadow-[0_0_10px_rgba(99,102,241,0.1)]" : "bg-white border-black shadow-[4px_4px_0_rgba(0,0,0,0.1)]"}`} />
      {isEditing ? (
        <input autoFocus className="relative z-10 bg-transparent border-b border-indigo-400 outline-none text-center font-black text-[10px] w-20" value={label} onChange={(e) => setLabel(e.target.value)} onBlur={onBlur} onKeyDown={(e) => e.key === 'Enter' && onBlur()} />
      ) : (
        <span className={`relative z-10 text-[10px] font-black text-center break-words px-3 uppercase leading-tight ${isDarkMode ? "text-indigo-300" : "text-black"}`}>{label}</span>
      )}
      <Handle type="target" position={Position.Top} className="!opacity-0" />
      <Handle type="source" position={Position.Bottom} className="!opacity-0" />
      <Handle type="source" position={Position.Left} id="left" className="!opacity-0" />
      <Handle type="source" position={Position.Right} id="right" className="!opacity-0" />
    </div>
  );
};

const nodeTypes = { entityNode: EntityNode, attributeNode: AttributeNode, relationshipNode: RelationshipNode };

// --- 메인 캔버스 ---

function ERDCanvas({ tables }) {
  const isDarkMode = useAppStore((state) => state.isDarkMode);
  const { toObject } = useReactFlow();
  
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [history, setHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);

  const addHistory = useCallback((msg) => {
    const time = new Date().toLocaleTimeString();
    setHistory(prev => [{ time, msg }, ...prev].slice(0, 50));
  }, []);

  const onRename = useCallback((nodeId, newLabel) => {
    setNodes((nds) => nds.map((node) => {
      if (node.id === nodeId) {
        const oldLabel = node.data.label;
        addHistory(`[이름 변경] '${oldLabel}' -> '${newLabel}'`);
        return { ...node, data: { ...node.data, label: newLabel } };
      }
      return node;
    }));
  }, [addHistory]);

  useEffect(() => {
    const saved = localStorage.getItem('erd-chen-edit-backup-v2');
    if (saved) {
      const { nodes: sn, edges: se, history: sh } = JSON.parse(saved);
      setNodes(sn.map(n => ({ ...n, data: { ...n.data, onRename }})));
      setEdges(se);
      setHistory(sh || []);
      return;
    }

    const tableArray = Array.isArray(tables) ? tables : Object.values(tables || {});
    if (tableArray.length === 0) return;

    const newNodes = [];
    const newEdges = [];
    const uniqueTables = Array.from(new Map(tableArray.map(t => [(t.table_name || t.name || "").toLowerCase(), t])).values());
    const tableNames = uniqueTables.map(t => (t.table_name || t.name || "").toLowerCase());

    const GRID_X = 1000;
    const GRID_Y = 600;
    const ATTR_DIST = 190;

    uniqueTables.forEach((table, tIdx) => {
      const tableName = table.table_name || table.name || "Unknown";
      const baseX = (tIdx % 2) * GRID_X;
      const baseY = Math.floor(tIdx / 2) * GRID_Y;
      const entityId = `ent-${tableName.toLowerCase()}`;

      newNodes.push({ id: entityId, type: "entityNode", data: { label: tableName, onRename }, position: { x: baseX, y: baseY } });

      const columns = (table.columns || []).filter(col => {
        const name = typeof col === 'string' ? col.split(':')[0] : (col.name || "");
        return name.toLowerCase() !== 'fk';
      });

      columns.forEach((col, cIdx) => {
        const colName = typeof col === 'string' ? col.split(':')[0] : (col.name || "");
        const constraints = (typeof col === 'string' ? col : (col.constraints || "")).toLowerCase();
        
        const angle = (cIdx / columns.length) * Math.PI * 2;
        const attrX = baseX + 25 + Math.cos(angle) * ATTR_DIST;
        const attrY = baseY + 10 + Math.sin(angle) * ATTR_DIST;
        const attrId = `attr-${entityId}-${colName.toLowerCase()}`;

        newNodes.push({ id: attrId, type: "attributeNode", data: { label: colName, isPK: constraints.includes("pk"), onRename }, position: { x: attrX, y: attrY } });
        newEdges.push({ id: `e-${attrId}`, source: entityId, target: attrId, type: "straight", style: { stroke: isDarkMode ? "#475569" : "#94a3b8", strokeWidth: 1.5, opacity: 0.8 } });
      });
    });

    let relCounter = 0;
    const existingRels = new Set();
    uniqueTables.forEach((table) => {
      const sourceTableName = (table.table_name || table.name || "").toLowerCase();
      (table.columns || []).forEach((col) => {
        const colName = (typeof col === 'string' ? col.split(':')[0] : (col.name || "")).toLowerCase();
        const constraints = (typeof col === 'string' ? col : (col.constraints || "")).toLowerCase();

        let targetName = null;
        const fkMatch = constraints.match(/fk\s*\(?([^). \n]+)/);
        if (fkMatch) targetName = fkMatch[1].toLowerCase();
        else if (colName.endsWith("id")) {
          const base = colName.replace(/_?id$/, "");
          targetName = tableNames.find(tn => tn === base || tn === base + "s" || base === tn + "s");
        }

        if (targetName && targetName !== sourceTableName) {
          const relKey = [sourceTableName, targetName].sort().join("-");
          if (!existingRels.has(relKey)) {
            existingRels.add(relKey);
            const relId = `rel-${relCounter++}`;
            const sIdx = uniqueTables.findIndex(t => (t.table_name || t.name || "").toLowerCase() === targetName);
            const tIdx = uniqueTables.findIndex(t => (t.table_name || t.name || "").toLowerCase() === sourceTableName);
            const rX = ((sIdx % 2) * GRID_X + (tIdx % 2) * GRID_X) / 2 + 15;
            const rY = (Math.floor(sIdx / 2) * GRID_Y + Math.floor(tIdx / 2) * GRID_Y) / 2;
            newNodes.push({ id: relId, type: "relationshipNode", data: { label: "관계", onRename }, position: { x: rX, y: rY } });
            const commonEdge = { type: "smoothstep", style: { stroke: isDarkMode ? "#6366f1" : "#000", strokeWidth: 2 } };
            newEdges.push({ id: `e1-${relId}`, source: `ent-${targetName}`, target: relId, label: "1", ...commonEdge });
            newEdges.push({ id: `e2-${relId}`, source: relId, target: `ent-${sourceTableName}`, label: "N", ...commonEdge });
          }
        }
      });
    });

    setNodes(newNodes);
    setEdges(newEdges);
    addHistory("AI가 최적의 ER 다이어그램 초안을 생성했습니다.");
  }, [tables, onRename, isDarkMode, addHistory]);

  const onNodesChange = useCallback((changes) => {
    setNodes((nds) => applyNodeChanges(changes, nds));
    const positionChange = changes.find(c => c.type === 'position' && c.dragging === false);
    if (positionChange) {
      const node = nodes.find(n => n.id === positionChange.id);
      if (node) addHistory(`[위치 이동] '${node.data.label}' 노드 배치 조정`);
    }
  }, [nodes, addHistory]);

  const onEdgesChange = useCallback((changes) => setEdges((eds) => applyEdgeChanges(changes, eds)), []);
  const onConnect = useCallback((params) => {
    setEdges((eds) => addEdge({ ...params, type: 'smoothstep', style: { stroke: isDarkMode ? '#6366f1' : '#000', strokeWidth: 2 } }, eds));
    addHistory(`[관계 추가] 새로운 연결선 생성`);
  }, [isDarkMode, addHistory]);

  return (
    <div className={`h-[850px] w-full rounded-3xl border-2 overflow-hidden relative shadow-2xl transition-all duration-500 ${isDarkMode ? "bg-[#020617] border-slate-800" : "bg-[#fafafa] border-slate-200"}`}>
      <div className="absolute top-6 right-6 z-50 flex gap-2">
        <button onClick={() => setShowHistory(!showHistory)} className={`p-2 rounded-xl border-2 flex items-center gap-2 text-xs font-bold transition-all ${isDarkMode ? "bg-[#0f172a] border-slate-700 text-slate-300 hover:border-indigo-500" : "bg-white border-slate-200 text-slate-600 hover:border-black"}`}><History size={14} /> {showHistory ? "닫기" : "이력"}</button>
        <button onClick={() => { localStorage.setItem('erd-chen-edit-backup-v2', JSON.stringify({ ...toObject(), history })); alert('저장되었습니다.'); }} className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-xl shadow-lg flex items-center gap-2 text-xs font-bold"><Save size={14} /> 저장</button>
        <button onClick={() => { if (window.confirm('초기화할까요?')) { localStorage.removeItem('erd-chen-edit-backup-v2'); window.location.reload(); } }} className={`p-2 rounded-xl border-2 flex items-center gap-2 text-xs font-bold transition-all ${isDarkMode ? "bg-[#0f172a] border-slate-700 text-slate-300" : "bg-white border-slate-200 text-slate-600"}`}><RotateCcw size={14} /> 초기화</button>
      </div>

      {showHistory && (
        <div className={`absolute top-20 right-6 z-50 w-72 max-h-[500px] overflow-y-auto p-5 border-2 rounded-2xl shadow-2xl backdrop-blur-xl ${isDarkMode ? "bg-slate-900/90 border-slate-700 text-slate-300" : "bg-white/90 border-slate-200 text-slate-600"}`}>
          <h4 className="font-bold text-sm mb-4 border-b pb-2 flex items-center gap-2"><MessageSquare size={14} /> 작업 메모</h4>
          <div className="space-y-3">{history.map((item, idx) => (<div key={idx} className="flex flex-col gap-1 border-l-2 border-indigo-500/30 pl-3"><span className="text-[10px] opacity-50">{item.time}</span><p className="text-[11px]">{item.msg}</p></div>))}</div>
        </div>
      )}

      <div className={`absolute top-6 left-6 z-50 p-5 border-2 shadow-[4px_4px_0_rgba(0,0,0,0.1)] transition-all ${isDarkMode ? "bg-[#0f172a] border-indigo-500/50" : "bg-white border-black"}`}>
        <h3 className={`font-bold border-b-2 pb-2 mb-4 text-sm uppercase tracking-widest ${isDarkMode ? "text-indigo-400 border-indigo-500/30" : "text-black border-black"}`}>수정 가능한 ERD</h3>
        <p className="text-[10px] text-slate-500 mb-4">* 더블 클릭하여 이름 수정 가능</p>
        <div className="space-y-4 text-xs font-bold">
          <div className="flex items-center gap-4">
            <div className={`w-8 h-4 border-2 ${isDarkMode ? "bg-[#0f172a] border-indigo-500" : "border-black"}`}></div>
            <span className={isDarkMode ? "text-slate-300" : "text-black"}>개체 (Entity)</span>
          </div>
          <div className="flex items-center gap-4">
            <div className={`w-5 h-5 border-2 rotate-45 ml-1.5 mr-1.5 ${isDarkMode ? "bg-[#0f172a] border-indigo-400" : "border-black"}`}></div>
            <span className={isDarkMode ? "text-slate-300" : "text-black"}>관계 (Relationship)</span>
          </div>
          <div className="flex items-center gap-4">
            <div className={`w-8 h-5 border-2 rounded-[100%/100%] flex items-center justify-center ${isDarkMode ? "bg-[#1e293b] border-slate-500" : "border-black"}`}></div>
            <span className={isDarkMode ? "text-slate-300" : "text-black"}>속성 (Attribute)</span>
          </div>
          <div className="flex items-center gap-4">
            <div className={`w-8 h-5 border-2 rounded-[100%/100%] flex items-center justify-center ${isDarkMode ? "bg-[#1e293b] border-slate-500" : "border-black"}`}>
              <span className={`text-[9px] underline decoration-2 ${isDarkMode ? "text-slate-100" : "text-black"}`}>PK</span>
            </div>
            <span className={isDarkMode ? "text-slate-300" : "text-black"}>기본키 (Primary Key)</span>
          </div>
        </div>
      </div>

      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect} fitView fitViewOptions={{ padding: 0.15 }}>
        <Background color={isDarkMode ? "#1e293b" : "#cbd5e1"} gap={30} variant="dots" size={2} className={isDarkMode ? "opacity-30" : "opacity-100"} />
      </ReactFlow>
    </div>
  );
}

export default function SADatabaseER(props) {
  return <ReactFlowProvider><ERDCanvas {...props} /></ReactFlowProvider>;
}