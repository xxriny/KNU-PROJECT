import React from "react";
import useAppStore from "../../store/useAppStore";
import { PriorityBadge, EmptyState } from "./SharedComponents";

export default function RTMTab() {
  const { requirements_rtm, tech_stacks, isDarkMode } = useAppStore();

  const safeRequirementsRtm = Array.isArray(requirements_rtm) ? requirements_rtm : [];
  if (safeRequirementsRtm.length === 0) {
    return <EmptyState text="RTM 데이터가 없습니다" />;
  }

  // feature_id 별로 기술 스택 그룹화
  const safeTechStacks = Array.isArray(tech_stacks) ? tech_stacks : [];
  const stackMap = safeTechStacks.reduce((acc, stack) => {
    const fid = stack.feature_id;
    if (!acc[fid]) acc[fid] = [];
    acc[fid].push(stack);
    return acc;
  }, {});

  return (
    <div className={`h-full overflow-auto p-4 transition-colors duration-200 ${isDarkMode ? "bg-[var(--bg-primary)]" : "bg-[var(--bg-secondary)]"}`}>
      <table className="w-full text-[15px]">
        <thead>
          <tr className={`border-b ${isDarkMode ? "border-slate-700" : "border-slate-200"}`}>
            <th className={`text-left py-2 px-2 font-medium ${isDarkMode ? "text-slate-400" : "text-slate-500"}`}>ID</th>
            <th className={`text-left py-2 px-2 font-medium ${isDarkMode ? "text-slate-400" : "text-slate-500"}`}>설명</th>
            <th className={`text-left py-2 px-2 font-medium whitespace-nowrap ${isDarkMode ? "text-slate-400" : "text-slate-500"}`}>기술 스택</th>
            <th className={`text-left py-2 px-2 font-medium ${isDarkMode ? "text-slate-400" : "text-slate-500"}`}>상태</th>
            <th className={`text-left py-2 px-2 font-medium ${isDarkMode ? "text-slate-400" : "text-slate-500"}`}>우선순위</th>
            <th className={`text-left py-2 px-2 font-medium ${isDarkMode ? "text-slate-400" : "text-slate-500"}`}>카테고리</th>
          </tr>
        </thead>
        <tbody>
          {safeRequirementsRtm.map((req, idx) => {
            const fid = req.feature_id || req.REQ_ID || req.id;
            const assignedStacks = stackMap[fid] || [];
            
            return (
              <tr
                key={fid || idx}
                className={`border-b transition-colors ${
                  isDarkMode 
                    ? "border-slate-800/50 hover:bg-slate-800/30" 
                    : "border-slate-100 hover:bg-white"
                }`}
              >
                <td className={`py-2 px-2 font-mono text-[13px] font-bold ${isDarkMode ? "text-blue-400" : "text-blue-700"}`}>
                  {fid}
                </td>
                <td className={`py-2 px-2 max-w-xs leading-relaxed ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>
                  {req.description}
                </td>
                <td className="py-2 px-2">
                  <div className="flex flex-wrap gap-1">
                    {assignedStacks.length > 0 ? (
                      assignedStacks.map((s, sIdx) => (
                        <span key={sIdx} className={`px-1.5 py-0.5 rounded text-[12px] border ${
                          isDarkMode 
                            ? "bg-slate-800 text-blue-300 border-slate-700" 
                            : "bg-blue-50 text-blue-700 border-blue-200"
                        }`}>
                          {s.package}
                        </span>
                      ))
                    ) : (
                      <span className={`${isDarkMode ? "text-slate-600" : "text-slate-400"} text-[12px]`}>-</span>
                    )}
                  </div>
                </td>
                <td className="py-2 px-2">
                  {assignedStacks.length > 0 ? (
                    <StatusBadge status={assignedStacks[0].status} isDarkMode={isDarkMode} />
                  ) : (
                    <span className={`${isDarkMode ? "text-slate-600" : "text-slate-400"} text-[12px]`}>-</span>
                  )}
                </td>
                <td className="py-2 px-2">
                  <PriorityBadge priority={req.priority} />
                </td>
                <td className="py-2 px-2">
                  <span className={`px-1.5 py-0.5 rounded text-[12px] font-medium ${
                    isDarkMode 
                      ? "bg-slate-800 text-slate-400" 
                      : "bg-slate-100 text-slate-600 border border-slate-200"
                  }`}>
                    {req.category}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function StatusBadge({ status, isDarkMode }) {
  const darkStyles = {
    APPROVED: "bg-green-600/20 text-green-400 border-green-500/30",
    PENDING_CRAWL: "bg-yellow-600/20 text-yellow-400 border-yellow-500/30",
    REJECTED: "bg-red-600/20 text-red-400 border-red-500/30",
  };
  const lightStyles = {
    APPROVED: "bg-green-50 text-green-700 border-green-200",
    PENDING_CRAWL: "bg-yellow-50 text-yellow-700 border-yellow-200",
    REJECTED: "bg-red-50 text-red-700 border-red-200",
  };

  const currentStyles = isDarkMode ? darkStyles : lightStyles;
  
  return (
    <span className={`px-1.5 py-0.5 rounded text-[11px] font-bold border ${currentStyles[status] || (isDarkMode ? "bg-slate-800 text-slate-500 border-slate-700" : "bg-slate-100 text-slate-500 border-slate-200")}`}>
      {status}
    </span>
  );
}
