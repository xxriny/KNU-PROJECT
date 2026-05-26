import React from "react";
import useAppStore from "../../store/useAppStore";

const GROUP_META = {
  pm:     { label: "요구사항",      color: "text-cyan-400",   dot: "bg-cyan-400" },
  sa:     { label: "아키텍처",      color: "text-teal-400",   dot: "bg-teal-400" },
  collab: { label: "Collaboration", color: "text-blue-400",   dot: "bg-blue-400" },
};

export default function StudioSidebar({
  panels, activeIconPanel, isDarkMode,
  hasProgress, pipelineStatus,
  onPanel, onOpenProgress,
}) {
  const groups = Object.keys(GROUP_META);
  const grouped = groups.reduce((acc, g) => {
    acc[g] = panels.filter(p => p.group === g);
    return acc;
  }, {});

  return (
    <div className="flex flex-col gap-0 pt-3 px-3">
      {/* 그룹별 섹션 */}
      {groups.map((g) => {
        const items = grouped[g];
        if (!items?.length) return null;
        const meta = GROUP_META[g];
        return (
          <div key={g} className="mb-4">
            <div className="flex items-center gap-1.5 px-1 mb-2">
              <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
              <p className={`text-[9px] font-black uppercase tracking-[0.2em] ${isDarkMode ? "text-slate-600" : "text-slate-400"}`}>
                {meta.label}
              </p>
            </div>
            <div className="flex flex-col gap-1">
              {items.map((panel) => {
                const isActive = activeIconPanel === panel.id;
                return (
                  <button
                    key={panel.id}
                    onClick={() => onPanel(panel.id)}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl border transition-all text-left ${
                      isActive
                        ? isDarkMode
                          ? "bg-white/10 border-white/10"
                          : "bg-blue-50 border-blue-200"
                        : isDarkMode
                          ? "bg-transparent border-transparent hover:bg-white/[0.04] hover:border-white/5"
                          : "bg-transparent border-transparent hover:bg-slate-50 hover:border-slate-100"
                    }`}
                  >
                    <div className={`w-6 h-6 rounded-lg flex items-center justify-center shrink-0 ${
                      isActive ? panel.bg : isDarkMode ? "bg-white/5" : "bg-slate-100"
                    }`}>
                      <panel.Icon size={12} className={isActive ? panel.color : isDarkMode ? "text-slate-500" : "text-slate-400"} />
                    </div>
                    <span className={`text-[11px] font-semibold truncate ${
                      isActive
                        ? isDarkMode ? "text-white" : "text-slate-900"
                        : isDarkMode ? "text-slate-400" : "text-slate-500"
                    }`}>
                      {panel.label}
                    </span>
                    {isActive && (
                      <span className={`ml-auto w-1 h-4 rounded-full shrink-0 ${panel.color.replace("text-", "bg-")}`} />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
