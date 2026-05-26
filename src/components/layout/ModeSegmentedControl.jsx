import React from "react";
import { Sparkles, Layers, ScanSearch } from "lucide-react";

const MODES = [
  { key: "create",  label: "신규",   Icon: Sparkles,   color: "text-blue-400"    },
  { key: "update",  label: "확장",   Icon: Layers,     color: "text-emerald-400" },
  { key: "reverse", label: "재분석", Icon: ScanSearch, color: "text-purple-400"  },
];

export default function ModeSegmentedControl({ value, onChange, isDarkMode, disabled = false }) {
  return (
    <div className="mb-4">
      <p className={`text-[9px] font-black uppercase tracking-[0.2em] mb-2 px-1 ${isDarkMode ? "text-slate-600" : "text-slate-400"}`}>
        모드
      </p>
      <div
        role="tablist"
        aria-label="분석 모드 선택"
        className={`relative grid grid-cols-3 gap-1 p-1 rounded-2xl border ${
          isDarkMode
            ? "bg-white/[0.03] border-white/5"
            : "bg-slate-50 border-slate-100"
        } ${disabled ? "opacity-50 pointer-events-none" : ""}`}
      >
        {MODES.map((mode) => {
          const isActive = value === mode.key;
          return (
            <button
              key={mode.key}
              role="tab"
              aria-selected={isActive}
              disabled={disabled}
              onClick={() => onChange?.(mode.key)}
              className={`relative flex flex-col items-center justify-center gap-1 py-2 rounded-xl text-[10px] font-bold tracking-tight transition-all ${
                isActive
                  ? isDarkMode
                    ? "bg-[var(--accent)]/15 text-white shadow-[0_2px_8px_rgba(59,130,246,0.15)]"
                    : "bg-white text-slate-900 shadow-sm border border-slate-200"
                  : isDarkMode
                    ? "text-slate-500 hover:text-slate-300 hover:bg-white/[0.04]"
                    : "text-slate-500 hover:text-slate-700 hover:bg-white/60"
              }`}
            >
              <mode.Icon size={14} className={isActive ? mode.color : ""} />
              <span>{mode.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
