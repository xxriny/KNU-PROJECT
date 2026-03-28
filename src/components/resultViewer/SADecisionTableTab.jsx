import React, { useMemo } from "react";
import useAppStore from "../../store/useAppStore";
import { Section, EmptyState } from "./SharedComponents";
import { buildReqFunctionNameMap, layerBadgeTone } from "./resultUtils";
import { CheckCircle } from "lucide-react";

export default function SADecisionTableTab() {
  const { sa_artifacts, sa_phase5 } = useAppStore();
  const table = sa_artifacts?.decision_table;

  if (!table) {
    return <EmptyState text="Decision Table 산출물이 없습니다" />;
  }

  const rows = table.rows || [];
  const quality = table.data_quality || {};

  const reqFunctionNameMap = useMemo(
    () => buildReqFunctionNameMap(sa_phase5?.mapped_requirements),
    [sa_phase5?.mapped_requirements]
  );


  const restrictionTone = (restriction) => {
    const key = String(restriction || "").toLowerCase();
    if (key.includes("internal") || key.includes("authorized")) return "bg-amber-900/30 text-amber-300 border-amber-800/50";
    if (key.includes("public") || key.includes("open")) return "bg-blue-900/30 text-blue-300 border-blue-800/50";
    return "bg-slate-800/50 text-slate-300 border-slate-700/60";
  };

  const actionTone = (action) => {
    if (action === "ALLOW") return "bg-emerald-900/30 text-emerald-300 border-emerald-800/50";
    if (action === "REVIEW") return "bg-amber-900/30 text-amber-300 border-amber-800/50";
    return "bg-slate-800/50 text-slate-300 border-slate-700/60";
  };

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      <Section title="Decision Table" icon={<CheckCircle size={12} />}>
        <div className="text-[12px] text-slate-500 mb-2">
          규칙 {rows.length}개 · 완전성 {Math.round((quality.completeness || 0) * 100)}%
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-[12px] border-separate border-spacing-y-1">
            <thead>
              <tr className="border-b border-slate-700">
                <th className="text-left py-1 px-2 text-slate-500 font-medium">요구사항</th>
                <th className="text-left py-1 px-2 text-slate-500 font-medium">Layer</th>
                <th className="text-left py-1 px-2 text-slate-500 font-medium">Restriction</th>
                <th className="text-left py-1 px-2 text-slate-500 font-medium">Roles</th>
                <th className="text-left py-1 px-2 text-slate-500 font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 40).map((row, idx) => {
                const reqId = row.req_id || "-";
                const reqLabel = reqFunctionNameMap[reqId] || reqId;
                return (
                  <tr key={idx} className="bg-slate-900/35 border border-slate-800/60">
                    <td className="py-2 px-2 align-top">
                      <div className="text-[13px] font-semibold text-slate-200 leading-snug">{reqLabel}</div>
                      <div className="mt-0.5 text-[11px] text-slate-500 font-mono">{reqId}</div>
                    </td>
                    <td className="py-2 px-2 align-top">
                      <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${layerBadgeTone(row.layer)}`}>
                        {row.layer || "Unknown"}
                      </span>
                    </td>
                    <td className="py-2 px-2 align-top">
                      <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${restrictionTone(row.restriction_level)}`}>
                        {row.restriction_level || "-"}
                      </span>
                    </td>
                    <td className="py-2 px-2 align-top">
                      {Array.isArray(row.allowed_roles) && row.allowed_roles.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {row.allowed_roles.map((role, roleIdx) => (
                            <span
                              key={`${role}-${roleIdx}`}
                              className="inline-flex rounded-full border border-slate-700/60 bg-slate-800/45 px-2 py-0.5 text-[11px] text-slate-300"
                            >
                              {role}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-[12px] text-slate-500">-</span>
                      )}
                    </td>
                    <td className="py-2 px-2 align-top">
                      <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${actionTone(row.action || "REVIEW")}`}>
                        {row.action || "REVIEW"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}
