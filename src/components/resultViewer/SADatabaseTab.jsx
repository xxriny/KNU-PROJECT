import React from "react";
import useAppStore from "../../store/useAppStore";
import { Section, EmptyState } from "./SharedComponents";
import SADatabaseER from "./SADatabaseER";
import { Database, Table as TableIcon, Key, Network, List } from "lucide-react";

function SADatabaseTab() {
  const { sa_output, tables: storeTables, isDarkMode } = useAppStore();
  const [viewMode, setViewMode] = React.useState("grid"); // "grid" | "diagram"
  const tables = storeTables?.length > 0 ? storeTables : (sa_output?.tables || sa_output?.data?.tables || []);

  if (tables.length === 0) {
    return <EmptyState text="설계된 DB 테이블이 없습니다." />;
  }

  return (
    <div className="p-4 space-y-6">
      <Section 
        title="Database Schema Design" 
        icon={<Database size={14} />}
        rightElement={
          <div className={`flex items-center p-1 rounded-xl border ${isDarkMode ? "bg-slate-900 border-slate-700" : "bg-slate-50 border-slate-200"}`}>
            <button 
              onClick={() => setViewMode("grid")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${viewMode === "grid" 
                ? (isDarkMode ? "bg-blue-500 text-white" : "bg-blue-600 text-white shadow-sm") 
                : "text-slate-500 hover:text-slate-300"}`}
            >
              <List size={14} /> 리스트 뷰
            </button>
            <button 
              onClick={() => setViewMode("diagram")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${viewMode === "diagram" 
                ? (isDarkMode ? "bg-blue-500 text-white" : "bg-blue-600 text-white shadow-sm") 
                : "text-slate-500 hover:text-slate-300"}`}
            >
              <Network size={14} /> ER 다이어그램
            </button>
          </div>
        }
      >
        {viewMode === "diagram" ? (
          <SADatabaseER tables={tables} />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {tables.map((table, idx) => (
              <div key={idx} className="bg-slate-900/60 border border-slate-700/80 rounded-xl overflow-hidden shadow-lg shadow-black/20">
                <div className="bg-slate-800/80 px-4 py-3 border-b border-slate-700 flex items-center gap-2">
                  <TableIcon className="text-amber-400" size={16} />
                  <h4 className="font-mono text-[15px] font-bold text-slate-100">{table.table_name}</h4>
                </div>
                <div className="p-0">
                  <table className="w-full text-[13px] text-left border-collapse">
                    <thead>
                      <tr className="bg-slate-900/40 text-slate-500 uppercase text-[10px] tracking-wider">
                        <th className="px-4 py-2 font-medium border-b border-slate-800">Column</th>
                        <th className="px-4 py-2 font-medium border-b border-slate-800">Type</th>
                        <th className="px-4 py-2 font-medium border-b border-slate-800">Constraints</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/50">
                      {(table.columns || []).map((col, cidx) => (
                        <tr key={cidx} className="hover:bg-slate-800/30 transition-colors">
                          <td className="px-4 py-2.5 font-mono text-slate-300 flex items-center gap-2">
                            {col.constraints?.toLowerCase().includes("pk") && <Key size={10} className="text-amber-500" />}
                            {col.name}
                          </td>
                          <td className="px-4 py-2.5 text-blue-400/80 font-mono text-[12px]">{col.type}</td>
                          <td className="px-4 py-2.5 text-slate-500 italic text-[12px]">{col.constraints}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}

export default SADatabaseTab;
