import React from "react";
import { Library } from "lucide-react";
import useAppStore from "../../store/useAppStore";

export default function TopBar({
  activeOutputId, activateOutputTab,
  hasProgress, hasSaData, resultData,
  showSessions, setShowSessions,
  showSettings, setShowSettings,
}) {
  const { isDarkMode, currentUser, myTeams } = useAppStore();
  const activeTeam = myTeams.find(t => t.id === currentUser?.team_id);
  const teamName = activeTeam?.name || currentUser?.team_name || "팀 없음";

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

      {/* 팀 이름 */}
      <div className="flex-1 flex items-center app-no-drag overflow-hidden">
        <span className={`text-xl font-bold tracking-tight truncate ${isDarkMode ? "text-slate-100" : "text-slate-800"}`}>
          {teamName}
        </span>
      </div>

      {/* 라이브러리 버튼 */}
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
      </div>
    </div>
  );
}
