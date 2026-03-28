import React from "react";

export function StatCard({ label, value, color }) {
  return (
    <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700/50 text-center">
      <div className={`text-xl font-bold ${color}`}>{value}</div>
      <div className="text-[12px] text-slate-500 mt-0.5">{label}</div>
    </div>
  );
}

export function PriorityBadge({ priority }) {
  const colors = {
    "Must-have": "bg-red-600/20 text-red-300",
    "Should-have": "bg-yellow-600/20 text-yellow-300",
    "Could-have": "bg-green-600/20 text-green-300",
  };
  return (
    <span className={`px-1.5 py-0.5 rounded text-[12px] ${colors[priority] || "bg-slate-700 text-slate-400"}`}>
      {priority}
    </span>
  );
}

export function StatusBadge({ status }) {
  const normalized = status || "Needs_Clarification";
  const colors = {
    Pass: "bg-green-600/20 text-green-300",
    Fail: "bg-red-600/20 text-red-300",
    Error: "bg-red-600/20 text-red-300",
    Needs_Clarification: "bg-yellow-600/20 text-yellow-300",
    Skipped: "bg-slate-700 text-slate-300",
    Warning_Hallucination_Detected: "bg-amber-600/20 text-amber-300",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-[12px] ${colors[normalized] || colors.Needs_Clarification}`}>
      {normalized}
    </span>
  );
}

export function Section({ title, icon, children }) {
  return (
    <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700/50">
      <h4 className="flex items-center gap-1.5 text-sm font-medium text-slate-400 mb-3">
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
