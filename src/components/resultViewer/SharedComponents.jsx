import React from "react";
import useAppStore from "../../store/useAppStore";

export function AnimatedCounter({ value, decimals = 0 }) {
  return (
    <span>
      {value.toLocaleString(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })}
    </span>
  );
}

export function StatCard({ label, value, color, suffix = "" }) {
  const { isDarkMode } = useAppStore();
  const numericValue = typeof value === "number" ? value : parseFloat(String(value).replace(/[^0-9.]/g, ""));
  const isNumeric = !isNaN(numericValue);

  return (
    <div
      className={`rounded-xl p-4 border transition-all ${isDarkMode
        ? "glass-card border-[var(--border)] shadow-lg"
        : "bg-white/80 backdrop-blur-md border-slate-200 shadow-sm"
        }`}
    >
      <div className={`text-2xl font-bold ${color}`}>
        {isNumeric ? <AnimatedCounter value={numericValue} decimals={String(value).includes(".") ? 1 : 0} /> : value}
        {suffix}
      </div>
      <div className="text-[12px] font-medium text-slate-500 mt-1 uppercase tracking-wider">{label}</div>
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
    <div className={`rounded-lg p-4 border transition-all ${isDarkMode ? "bg-slate-900/50 border-slate-700/50" : "bg-white border-slate-200 shadow-sm"
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

export function ReportHeader({ title, subtitle, metadata }) {
  const { isDarkMode } = useAppStore();
  return (
    <div className="mb-12 text-center max-w-3xl mx-auto pt-4">
      <div className={`inline-block px-3 py-1 rounded-full mb-6 border ${isDarkMode ? "bg-blue-500/10 border-blue-500/20 text-blue-400" : "bg-blue-50 border-blue-100 text-blue-600"
        } text-[10px] font-black tracking-[0.2em] uppercase`}>
        Navigator Analysis Report
      </div>
      <h1 className={`text-5xl font-black mb-6 tracking-tight leading-tight ${isDarkMode ? "text-white" : "text-slate-900"}`}>
        {title}
      </h1>
      {subtitle && (
        <p className={`text-[17px] font-medium mb-10 ${isDarkMode ? "text-slate-400" : "text-slate-500"}`}>
          {subtitle}
        </p>
      )}
      {metadata && (
        <div className={`flex flex-wrap items-center justify-center gap-y-2 gap-x-6 text-[11px] font-bold uppercase tracking-widest border-t border-b border-dashed ${isDarkMode ? "border-white/10" : "border-slate-200"
          } py-4 mt-8`}>
          {Object.entries(metadata).map(([key, value]) => (
            <div key={key} className="flex items-center gap-2">
              <span className="opacity-40">{key}</span>
              <span className={isDarkMode ? "text-slate-300" : "text-slate-700"}>{value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function ReportSection({ number, title, children }) {
  const { isDarkMode } = useAppStore();
  return (
    <div className="mb-16">
      <div className="flex items-baseline gap-3 mb-8 border-b pb-3 border-white/5">
        <span className="text-2xl font-black text-blue-500 font-mono tracking-tighter">
          {number < 10 ? `0${number}` : number}
        </span>
        <h2 className={`text-2xl font-black tracking-tight ${isDarkMode ? "text-white" : "text-slate-900"}`}>
          {title}
        </h2>
      </div>
      <div className={`space-y-8 text-[18px] leading-[1.8] font-normal ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>
        {children}
      </div>
    </div>
  );
}

export function ReportTable({ headers, rows, title }) {
  const { isDarkMode } = useAppStore();
  return (
    <div className="my-8">
      {title && (
        <div className="text-[12px] font-black text-slate-500 mb-3 uppercase tracking-tighter ml-1">
          {title}
        </div>
      )}
      <div className={`overflow-hidden rounded-xl border ${isDarkMode ? "border-white/5 bg-white/5" : "border-slate-200 bg-slate-50/50"}`}>
        <table className="w-full text-left border-collapse table-fixed">
          <thead className={isDarkMode ? "bg-white/5" : "bg-slate-100"}>
            <tr>
              {headers.map((h, i) => (
                <th key={i} className="px-5 py-4 text-[11px] font-black text-slate-500 uppercase tracking-widest border-r last:border-r-0 border-white/5">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className={`border-t ${isDarkMode ? "border-white/5" : "border-slate-200"}`}>
                {row.map((cell, j) => (
                  <td key={j} className={`px-5 py-5 text-[15px] font-medium break-all border-r last:border-r-0 ${isDarkMode ? "border-white/5 text-slate-300" : "border-slate-200 text-slate-700"}`}>
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

