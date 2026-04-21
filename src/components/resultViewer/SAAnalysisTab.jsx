import React from "react";
import useAppStore from "../../store/useAppStore";
import { Section, StatusBadge, EmptyState } from "./SharedComponents";
import { AlertTriangle, CheckCircle, Info, FileText } from "lucide-react";

function SAAnalysisTab() {
  const { sa_output } = useAppStore();

  if (!sa_output) {
    return <EmptyState text="SA 분석 데이터가 없습니다." />;
  }

  const { status, gaps, thinking, metadata } = sa_output;

  return (
    <div className="p-4 space-y-6">
      <div className="flex items-center justify-between bg-slate-800/40 p-4 rounded-xl border border-slate-700/50">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <FileText className="text-blue-400" size={20} />
            Architecture QA Analysis
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Bundle ID: <span className="font-mono text-blue-300/80">{metadata?.bundle_id || "N/A"}</span>
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <span className="text-xs uppercase tracking-widest text-slate-500 font-semibold">Integrity Status</span>
          <StatusBadge status={status || "WARNING"} />
        </div>
      </div>

      <Section title="사고 과정 (Thinking Process)" icon={<Info size={14} />}>
        <div className="bg-slate-900/50 border border-slate-800 p-4 rounded-lg">
          <p className="text-[14px] leading-relaxed text-slate-300 whitespace-pre-wrap italic">
            "{thinking || "분석 내용이 없습니다."}"
          </p>
        </div>
      </Section>

      <Section title="결함 리포트 (Gap Analysis)" icon={<AlertTriangle size={14} />}>
        {gaps && gaps.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {gaps.map((gap, idx) => (
              <div key={idx} className="flex items-start gap-3 p-3 bg-red-900/10 border border-red-900/30 rounded-lg">
                <AlertTriangle className="text-red-400 mt-0.5 shrink-0" size={16} />
                <span className="text-[14px] text-red-200/90">{gap}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex items-center gap-3 p-4 bg-emerald-900/10 border border-emerald-900/30 rounded-lg text-emerald-200/80">
            <CheckCircle size={18} />
            <span className="text-[14px]">발견된 설계 결함이 없습니다. 아키텍처가 정합성을 유지하고 있습니다.</span>
          </div>
        )}
      </Section>
    </div>
  );
}

export default SAAnalysisTab;
