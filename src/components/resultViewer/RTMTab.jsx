import React from "react";
import useAppStore from "../../store/useAppStore";
import { PriorityBadge, EmptyState } from "./SharedComponents";

export default function RTMTab() {
  const { requirements_rtm } = useAppStore();

  if (!requirements_rtm || requirements_rtm.length === 0) {
    return <EmptyState text="RTM 데이터가 없습니다" />;
  }

  return (
    <div className="h-full overflow-auto p-4">
      <table className="w-full text-[15px]">
        <thead>
          <tr className="border-b border-slate-700">
            <th className="text-left py-2 px-2 text-slate-400 font-medium">ID</th>
            <th className="text-left py-2 px-2 text-slate-400 font-medium">카테고리</th>
            <th className="text-left py-2 px-2 text-slate-400 font-medium">설명</th>
            <th className="text-left py-2 px-2 text-slate-400 font-medium">우선순위</th>
            <th className="text-left py-2 px-2 text-slate-400 font-medium">의존성</th>
            <th className="text-left py-2 px-2 text-slate-400 font-medium">테스트 기준</th>
          </tr>
        </thead>
        <tbody>
          {requirements_rtm.map((req, idx) => (
            <tr
              key={req.REQ_ID || req.id || idx}
              className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors"
            >
              <td className="py-2 px-2 text-blue-300 font-mono">
                {req.REQ_ID || req.id}
              </td>
              <td className="py-2 px-2">
                <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                  {req.category}
                </span>
              </td>
              <td className="py-2 px-2 text-slate-300 max-w-xs">
                {req.description}
              </td>
              <td className="py-2 px-2">
                <PriorityBadge priority={req.priority} />
              </td>
              <td className="py-2 px-2 text-slate-500 font-mono text-[12px]">
                {(req.depends_on || []).join(", ") || "-"}
              </td>
              <td className="py-2 px-2 text-slate-500 max-w-[150px] truncate">
                {req.test_criteria || "-"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
