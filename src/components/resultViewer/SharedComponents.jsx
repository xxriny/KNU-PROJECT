import React from "react";
import useAppStore from "../../store/useAppStore";

export function StatCard({ label, value, color }) {
  const { isDarkMode } = useAppStore();
  return (
    <div className={`rounded-lg p-3 border text-center transition-all ${
      isDarkMode ? "glass-card border-[var(--border)]" : "bg-white/70 border-slate-200 shadow-sm"
    }`}>
      <div className={`text-xl font-bold ${color}`}>{value}</div>
      <div className="text-[12px] text-slate-500 mt-0.5">{label}</div>
    </div>
  );
}

export function PriorityBadge({ priority }) {
  const { isDarkMode } = useAppStore();
  const colors = isDarkMode ? {
    "Must-have": "bg-red-600/20 text-red-300",
    "Should-have": "bg-yellow-600/20 text-yellow-300",
    "Could-have": "bg-green-600/20 text-green-300",
  } : {
    "Must-have": "bg-red-50 text-red-600 border border-red-100",
    "Should-have": "bg-yellow-50 text-yellow-600 border border-yellow-200",
    "Could-have": "bg-green-50 text-green-600 border border-green-200",
  };
  return (
    <span className={`px-1.5 py-0.5 rounded text-[12px] ${colors[priority] || (isDarkMode ? "bg-slate-700 text-slate-400" : "bg-slate-100 text-slate-500")}`}>
      {priority}
    </span>
  );
}

export function StatusBadge({ status }) {
  const { isDarkMode } = useAppStore();
  const normalized = status || "Needs_Clarification";
  const colors = isDarkMode ? {
    Pass: "bg-green-600/20 text-green-300",
    Fail: "bg-red-600/20 text-red-300",
    Error: "bg-red-600/20 text-red-300",
    Needs_Clarification: "bg-yellow-600/20 text-yellow-300",
    Skipped: "bg-slate-700 text-slate-300",
    Warning_Hallucination_Detected: "bg-amber-600/20 text-amber-300",
  } : {
    Pass: "bg-green-50 text-green-600 border border-green-100",
    Fail: "bg-red-50 text-red-600 border border-red-100",
    Error: "bg-red-50 text-red-600 border border-red-100",
    Needs_Clarification: "bg-yellow-50 text-yellow-600 border border-yellow-200",
    Skipped: "bg-slate-100 text-slate-500 border border-slate-200",
    Warning_Hallucination_Detected: "bg-amber-50 text-amber-600 border border-amber-200",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-[12px] ${colors[normalized] || colors.Needs_Clarification}`}>
      {normalized}
    </span>
  );
}

export function Section({ title, icon, children }) {
  const { isDarkMode } = useAppStore();
  return (
    <div className={`rounded-lg p-4 border transition-all ${
      isDarkMode ? "bg-slate-900/50 border-slate-700/50" : "bg-white border-slate-200 shadow-sm"
    }`}>
      <h4 className={`flex items-center gap-1.5 text-sm font-medium mb-3 ${isDarkMode ? "text-slate-400" : "text-slate-700"}`}>
        {icon}
        {title}
      </h4>
      {children}
    </div>
  );
}

export function EmptyState({ text }) {
  return (
    <div className="h-full flex items-center justify-center text-slate-600 text-sm">
      {text}
    </div>
  );
}
