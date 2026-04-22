import React, { useState, useEffect } from "react";
import useAppStore from "../../store/useAppStore";
import { StickyNote, Trash2, Edit3, Search, Filter, MessageSquarePlus } from "lucide-react";

export default function MemoManager() {
  const { isDarkMode, userComments, removeComment, syncMemos } = useAppStore();
  const [searchTerm, setSearchTerm] = useState("");
  const [filterSection, setFilterSection] = useState("All");

  useEffect(() => {
    syncMemos();
  }, []);

  const sections = ["All", ...new Set(userComments.map(c => c.section))];
  
  const filteredMemos = userComments.filter(memo => {
    const matchesSearch = memo.text.toLowerCase().includes(searchTerm.toLowerCase()) || 
                          memo.selectedText?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesFilter = filterSection === "All" || memo.section === filterSection;
    return matchesSearch && matchesFilter;
  });

  return (
    <div className={`h-full flex flex-col p-6 space-y-6 ${isDarkMode ? "text-slate-300" : "text-slate-800"}`}>
      <div className="flex flex-col gap-4">
        <h2 className={`text-2xl font-black tracking-tight ${isDarkMode ? "text-white" : "text-slate-900"}`}>전체 메모 관리</h2>
        <p className="text-sm opacity-60">프로젝트 수행 중 기록된 모든 지적사항과 메모를 중앙에서 관리합니다.</p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className={`flex-1 min-w-[200px] flex items-center gap-2 px-3 py-2 rounded-xl border ${isDarkMode ? "bg-white/5 border-white/10" : "bg-slate-50 border-slate-200"}`}>
          <Search size={16} className="text-slate-500" />
          <input 
            type="text" 
            placeholder="메모 검색..." 
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="bg-transparent border-none outline-none text-sm w-full"
          />
        </div>
        <div className={`flex items-center gap-2 px-3 py-2 rounded-xl border ${isDarkMode ? "bg-white/5 border-white/10" : "bg-slate-50 border-slate-200"}`}>
          <Filter size={16} className="text-slate-500" />
          <select 
            value={filterSection}
            onChange={(e) => setFilterSection(e.target.value)}
            className="bg-transparent border-none outline-none text-sm cursor-pointer"
          >
            {sections.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-3 pr-2 custom-scrollbar">
        {filteredMemos.length === 0 ? (
          <div className="h-64 flex flex-col items-center justify-center opacity-20 border-2 border-dashed border-white/10 rounded-3xl">
            <StickyNote size={48} className="mb-4" />
            <p>검색 결과가 없거나 작성된 메모가 없습니다.</p>
          </div>
        ) : (
          filteredMemos.map((memo) => (
            <div key={memo.id} className={`group p-5 rounded-2xl border transition-all hover:scale-[1.01] ${
              isDarkMode ? "bg-white/5 border-white/5 hover:border-white/20" : "bg-white border-slate-200 shadow-sm hover:shadow-md"
            }`}>
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                      isDarkMode ? "bg-blue-500/20 text-blue-300" : "bg-blue-50 text-blue-600"
                    }`}>
                      {memo.section}
                    </span>
                  </div>
                  <h3 className={`text-base font-bold mb-2 ${isDarkMode ? "text-slate-100" : "text-slate-800"}`}>
                    {memo.text}
                  </h3>
                  {memo.selectedText && (
                    <div className={`p-3 rounded-xl text-sm italic mb-1 border-l-4 ${
                      isDarkMode ? "bg-black/20 border-blue-500/40 text-slate-400" : "bg-slate-50 border-blue-200 text-slate-500"
                    }`}>
                      "{memo.selectedText}"
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button 
                    onClick={() => removeComment(memo.id)}
                    className="p-2 rounded-lg hover:bg-red-500/10 text-slate-500 hover:text-red-500 transition-colors"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
