import React from "react";
import useAppStore from "../../store/useAppStore";
import { Section, EmptyState } from "./SharedComponents";
import { Database, Table as TableIcon, Key } from "lucide-react";

function SADatabaseTab() {
  const { sa_output, tables: storeTables } = useAppStore();
  const tables = storeTables?.length > 0 ? storeTables : (sa_output?.tables || sa_output?.data?.tables || []);

  if (tables.length === 0) {
    return <EmptyState text="설계된 DB 테이블이 없습니다." />;
  }

  return (
    <div className="p-4 space-y-6">
      <Section title="Database Schema Design" icon={<Database size={14} />}>
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
      </Section>
    </div>
  );
}

export default SADatabaseTab;
