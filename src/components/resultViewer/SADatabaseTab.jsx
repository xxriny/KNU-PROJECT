import React, { useState } from "react";
import { useStore } from "../../store/useStore";
import SADatabaseER from "./SADatabaseER";
import { Database, Table as TableIcon, Key, Network, List } from "lucide-react";
import Card from "../ui/Card";
import Badge from "../ui/Badge";
import ReportLayout from "./layout/ReportLayout";

export default function SADatabaseTab() {
  const { isDarkMode, sa_output, tables: storeTables } = useStore(['isDarkMode', 'sa_output', 'tables']);
  const [viewMode, setViewMode] = useState("grid"); // "grid" | "diagram"
  const tables = storeTables?.length > 0 ? storeTables : (sa_output?.tables || sa_output?.data?.tables || []);

  if (tables.length === 0) return <div className="h-full flex items-center justify-center text-slate-500">DB 데이터 없음</div>;

  return (
    <ReportLayout
      icon={Database}
      title="Schema Design"
      subtitle="데이터 영속성 계층의 구조와 테이블 간 관계 설계 리포트입니다."
      badge={`${tables.length} Entities`}
      rightElement={
        <div className={`flex p-1 rounded-xl border ${isDarkMode ? "bg-black/20 border-white/5" : "bg-slate-100 border-slate-200 shadow-inner"}`}>
          {[
            { id: "grid", icon: List, label: "LIST" },
            { id: "diagram", icon: Network, label: "DIAGRAM" }
          ].map(mode => (
            <button 
              key={mode.id}
              onClick={() => setViewMode(mode.id)}
              className={`flex items-center gap-2 px-5 py-2 rounded-lg text-xs font-black transition-all ${viewMode === mode.id 
                ? (isDarkMode ? "bg-blue-600 text-white shadow-lg" : "bg-white text-blue-600 shadow-sm") 
                : "text-slate-500 hover:text-slate-400"}`}
            >
              <mode.icon size={14} /> {mode.label}
            </button>
          ))}
        </div>
      }
    >
      <div className="min-h-[500px]">
        {viewMode === "diagram" ? (
          <SADatabaseER tables={tables} />
        ) : (
          <div className="report-grid-2">
            {tables.map((table, idx) => <TableCard key={idx} table={table} isDarkMode={isDarkMode} />)}
          </div>
        )}
      </div>
    </ReportLayout>
  );
}

const TableCard = React.memo(({ table, isDarkMode }) => (
  <Card variant="solid" noPadding className="overflow-hidden border-t-4 border-t-amber-500 shadow-2xl shadow-black/10">
    <div className={`px-6 py-4 border-b flex items-center gap-2 ${isDarkMode ? "bg-white/5 border-white/5" : "bg-slate-50 border-slate-100"}`}>
      <TableIcon className="text-amber-500" size={18} />
      <h4 className={`font-mono text-lg font-bold ${isDarkMode ? "text-white" : "text-slate-900"}`}>{table.table_name}</h4>
    </div>
    <div className="overflow-x-auto">
      <table className="w-full text-left border-collapse">
        <thead>
          <tr className="report-label-sm">
            <th className="px-6 py-4 border-b border-white/5">Column</th>
            <th className="px-6 py-4 border-b border-white/5">Type</th>
            <th className="px-6 py-4 border-b border-white/5 text-right">Constraint</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {(table.columns || []).map((col, cidx) => (
            <tr key={cidx} className={`${isDarkMode ? "hover:bg-white/5" : "hover:bg-slate-50"} transition-colors`}>
              <td className="px-6 py-3.5 font-mono text-[14px] flex items-center gap-2">
                {col.constraints?.toLowerCase().includes("pk") && <Key size={14} className="text-amber-500" />}
                <span className={isDarkMode ? "text-slate-200" : "text-slate-800"}>{col.name}</span>
              </td>
              <td className={`px-6 py-3.5 font-mono text-[13px] ${isDarkMode ? "text-blue-400/70" : "text-blue-600"}`}>{col.type}</td>
              <td className="px-6 py-3.5 text-right">
                {col.constraints && <Badge variant="secondary" className="text-[10px] px-2 font-black uppercase">{col.constraints}</Badge>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </Card>
));
