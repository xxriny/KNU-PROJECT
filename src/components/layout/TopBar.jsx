import React, { useState } from "react";
import { Library, RotateCcw, X } from "lucide-react";
import useAppStore from "../../store/useAppStore";

export default function TopBar({
  activeOutputId, activateOutputTab,
  hasProgress, hasSaData, resultData,
  showSessions, setShowSessions,
  showSettings, setShowSettings,
}) {
  const { isDarkMode, currentUser, myTeams, startNewProject, chatHistory } = useAppStore();
  const activeTeam = myTeams.find(t => t.id === currentUser?.team_id);
  const teamName = activeTeam?.name || currentUser?.team_name || "팀 없음";

  const [confirmReset, setConfirmReset] = useState(false);
  const hasWork = (chatHistory || []).length > 0;

  const handleNewProject = () => {
    if (!hasWork) {
      // 진행 중 작업이 없으면 확인 없이 즉시 reset (ModeBridge로 돌아감)
      startNewProject();
      return;
    }
    setConfirmReset(true);
  };

  const confirmAndReset = () => {
    setConfirmReset(false);
    startNewProject();
    if (showSessions) setShowSessions(false);
  };

  return (
    <div className={`h-14 app-drag flex items-center px-6 gap-4 border-b border-[var(--border)] backdrop-blur-xl shrink-0 z-20 relative ${isDarkMode ? "bg-[rgba(19,23,31,0.9)]" : "bg-[rgba(255,255,255,0.9)]"
      }`}>
      {/* 로고 영역 */}
      <div className="flex items-center gap-3 shrink-0 app-no-drag">
        <span className="text-sm font-display font-black text-gradient tracking-[0.25em] select-none ml-2">
          NAVIGATOR
        </span>

        {/* 새 프로젝트 시작 — 로고 우측에 배치 */}
        <button
          onClick={handleNewProject}
          title="새 프로젝트 / 새 대화 시작"
          className={`flex items-center gap-1.5 px-2.5 py-1.5 text-[11px] font-bold rounded-lg border transition-all ${
            isDarkMode
              ? "border-white/10 text-slate-400 hover:text-white hover:bg-white/5 hover:border-white/20"
              : "border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-50 hover:border-slate-300"
          }`}
        >
          <RotateCcw size={12} />
          <span>새 프로젝트</span>
        </button>
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

      {/* 확인 모달 — 진행 중 작업이 있을 때만 */}
      {confirmReset && (
        <div
          className="fixed inset-0 z-[9000] flex items-center justify-center animate-fade-in"
          style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(8px)" }}
          onClick={(e) => { if (e.target === e.currentTarget) setConfirmReset(false); }}
        >
          <div
            className={`w-[420px] rounded-2xl shadow-2xl p-6 border ${
              isDarkMode ? "bg-[#161B22] border-white/10 text-slate-200" : "bg-white border-slate-200 text-slate-800"
            }`}
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className="w-9 h-9 rounded-xl bg-amber-500/15 flex items-center justify-center">
                  <RotateCcw size={16} className="text-amber-400" />
                </div>
                <h3 className="text-[15px] font-black">새 프로젝트 시작</h3>
              </div>
              <button onClick={() => setConfirmReset(false)} className="opacity-50 hover:opacity-100 p-1 rounded-lg">
                <X size={14} />
              </button>
            </div>
            <p className="text-[13px] leading-relaxed opacity-80 mb-5">
              현재 대화·메모·디자인 스냅샷이 모두 초기화되고 모드 선택 화면으로 돌아갑니다.
              현재 세션은 <strong>라이브러리</strong>에서 다시 열 수 있습니다. 계속할까요?
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setConfirmReset(false)}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition-colors ${
                  isDarkMode ? "bg-white/5 hover:bg-white/10" : "bg-slate-100 hover:bg-slate-200"
                }`}
              >
                취소
              </button>
              <button
                onClick={confirmAndReset}
                className="px-4 py-2 rounded-lg text-xs font-bold bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/20"
              >
                새로 시작
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
