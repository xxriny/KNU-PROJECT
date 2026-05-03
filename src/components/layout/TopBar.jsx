import React, { useEffect, useState } from "react";
import { ChevronRight, Library, Settings } from "lucide-react";
import useAppStore from "../../store/useAppStore";

export default function TopBar({
  activeOutputId, activateOutputTab,
  hasProgress, hasSaData, resultData,
  showSessions, setShowSessions,
  showSettings, setShowSettings,
}) {
  const { isDarkMode, currentSessionId, sessions, updateSessionName } = useAppStore();
  const currentSession = sessions.find(s => s.id === currentSessionId);
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState("");

  useEffect(() => {
    if (currentSession) setEditValue(currentSession.name);
  }, [currentSession]);

  const handleRename = () => {
    if (editValue.trim() && currentSession) {
      updateSessionName(currentSessionId, editValue.trim());
    }
    setIsEditing(false);
  };

  return (
    <div className={`h-14 app-drag flex items-center px-6 gap-4 border-b border-[var(--border)] backdrop-blur-xl shrink-0 z-20 relative ${isDarkMode ? "bg-[rgba(19,23,31,0.9)]" : "bg-[rgba(255,255,255,0.9)]"
      }`}>
      {/* 로고 영역 */}
      <div className="flex items-center gap-3 shrink-0 app-no-drag">
        <span className="text-sm font-display font-black text-gradient tracking-[0.25em] select-none ml-2">
          NAVIGATOR
        </span>
      </div>

      <div className="w-px h-6 bg-[var(--border)] shrink-0 mx-2" />

      {/* 세션 이름 (좌측 정렬) */}
      <div className="flex-1 flex items-center app-no-drag overflow-hidden">
        {isEditing ? (
          <input
            autoFocus
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onBlur={handleRename}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleRename();
              if (e.key === "Escape") setIsEditing(false);
            }}
            className={`px-2 py-1 text-xl font-bold bg-transparent border-b-2 border-blue-500 outline-none w-full max-w-[600px] ${isDarkMode ? "text-white" : "text-slate-900"}`}
          />
        ) : (
          <div
            onDoubleClick={() => setIsEditing(true)}
            className={`group flex items-center gap-3 cursor-text px-3 py-1.5 rounded-xl transition-all hover:bg-white/5 truncate max-w-[800px]`}
            title="더블 클릭하여 별칭 수정"
          >
            <span className={`text-xl font-bold tracking-tight truncate ${isDarkMode ? "text-slate-100" : "text-slate-800"}`}>
              {currentSession?.name || "새 프로젝트 세션"}
            </span>
            <div className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center">
              <ChevronRight size={16} className="text-blue-500/50" />
            </div>
          </div>
        )}
      </div>

      {/* 세션 & 설정 버튼 (우측 윈도우 컨트롤러 140px 여백 확보) */}
      <div className="flex items-center gap-2 app-no-drag shrink-0 mr-[140px]">
        <button
          onClick={() => setShowSessions(!showSessions)}
          className={`flex items-center gap-2 px-4 py-2 text-[13px] font-bold rounded-xl border transition-all ${showSessions
            ? "bg-blue-500/10 border-blue-500/30 text-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.1)]"
            : `border-[var(--border)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] ${isDarkMode ? "hover:bg-white/10" : "hover:bg-black/5"}`
            }`}
        >
          <Library size={16} />
          <span>라이브러리</span>
        </button>
        <button
          onClick={() => setShowSettings(!showSettings)}
          className={`flex items-center gap-2 px-4 py-2 text-[13px] font-bold rounded-xl border transition-all ${showSettings
            ? "bg-blue-500/10 border-blue-500/30 text-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.1)]"
            : `border-[var(--border)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] ${isDarkMode ? "hover:bg-white/10" : "hover:bg-black/5"}`
            }`}
        >
          <Settings size={16} />
          <span>설정</span>
        </button>
      </div>
    </div>
  );
}
