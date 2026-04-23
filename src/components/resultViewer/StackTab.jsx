/**
 * StackTab — PM 기술 스택 매핑 테이블 뷰어
 * PM 파이프라인에서 매핑된 기술 스택 정보를 테이블 형태로 시각화합니다.
 */

import React from "react";
import useAppStore from "../../store/useAppStore";
import { Section, EmptyState } from "./SharedComponents";
import { Layers, Package, CheckCircle2, AlertTriangle, ExternalLink } from "lucide-react";

export default function StackTab() {
  const { tech_stacks, requirements_rtm, isDarkMode } = useAppStore();

  const stacks = Array.isArray(tech_stacks) ? tech_stacks : [];

  if (stacks.length === 0) {
    return <EmptyState text="매핑된 기술 스택이 없습니다." />;
  }

  return (
    <div className="p-6 space-y-6">
      <Section
        title="Technology Stack Mapping"
        icon={<Layers size={14} className="text-indigo-400" />}
      >
        <p className={`text-sm mb-6 ${isDarkMode ? "text-slate-400" : "text-slate-600"}`}>
          각 요구사항(RTM)에 매핑된 기술 스택과 승인 상태를 보여줍니다.
        </p>

        <div className={`rounded-xl border overflow-hidden ${isDarkMode ? "border-slate-700/50" : "border-slate-200"}`}>
          <table className="w-full text-sm text-left">
            <thead>
              <tr className={`text-[10px] uppercase tracking-wider ${isDarkMode ? "bg-slate-800/80 text-slate-400" : "bg-slate-100 text-slate-500"}`}>
                <th className="px-4 py-3 font-semibold">Feature ID</th>
                <th className="px-4 py-3 font-semibold">Package / Library</th>
                <th className="px-4 py-3 font-semibold">Version</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Source</th>
              </tr>
            </thead>
            <tbody className={`divide-y ${isDarkMode ? "divide-slate-800/50" : "divide-slate-100"}`}>
              {stacks.map((stack, idx) => {
                const status = stack.status || stack.st || "APPROVED";
                const isApproved = status === "APPROVED" || status === "A";
                const featureId = stack.feature_id || stack.fid || `FEAT_${String(idx + 1).padStart(3, "0")}`;
                const pkg = stack.pkg || stack.package || stack.name || "N/A";
                const version = stack.version || stack.ver || "-";
                const source = stack.source || stack.src || "RAG";

                return (
                  <tr
                    key={idx}
                    className={`transition-colors ${isDarkMode ? "hover:bg-slate-800/40" : "hover:bg-slate-50"}`}
                  >
                    <td className={`px-4 py-3 font-mono text-xs ${isDarkMode ? "text-cyan-400" : "text-cyan-600"}`}>
                      {featureId}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Package size={14} className={isDarkMode ? "text-indigo-400" : "text-indigo-500"} />
                        <span className={`font-medium ${isDarkMode ? "text-slate-200" : "text-slate-800"}`}>
                          {pkg}
                        </span>
                      </div>
                    </td>
                    <td className={`px-4 py-3 font-mono text-xs ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>
                      {version}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                        isApproved
                          ? (isDarkMode ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30" : "bg-emerald-50 text-emerald-600 border border-emerald-200")
                          : (isDarkMode ? "bg-amber-500/15 text-amber-400 border border-amber-500/30" : "bg-amber-50 text-amber-600 border border-amber-200")
                      }`}>
                        {isApproved ? <CheckCircle2 size={10} /> : <AlertTriangle size={10} />}
                        {isApproved ? "Approved" : status}
                      </span>
                    </td>
                    <td className={`px-4 py-3 text-xs ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>
                      <span className="flex items-center gap-1">
                        <ExternalLink size={10} />
                        {source}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Summary */}
        <div className={`mt-4 flex items-center gap-4 text-xs ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>
          <span>Total: <strong className={isDarkMode ? "text-slate-300" : "text-slate-700"}>{stacks.length}</strong> stacks</span>
          <span>Approved: <strong className="text-emerald-400">{stacks.filter(s => (s.status || s.st || "APPROVED") === "APPROVED" || (s.status || s.st || "A") === "A").length}</strong></span>
        </div>
      </Section>
    </div>
  );
}
