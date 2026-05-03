import React from "react";
import { useStore } from "../../store/useStore";
import { AlertTriangle, CheckCircle, Info, FileText } from "lucide-react";
import Card from "../ui/Card";
import Badge from "../ui/Badge";
import ReportLayout, { ReportSection } from "./layout/ReportLayout";

const SA_ANALYSIS_KEYS = ['isDarkMode', 'sa_output'];

export default function SAAnalysisTab() {
  const { isDarkMode, sa_output } = useStore(SA_ANALYSIS_KEYS);

  if (!sa_output) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-slate-500 animate-fade-in space-y-4">
        <p className="font-bold text-lg">아키텍처 분석 데이터가 없습니다.</p>
      </div>
    );
  }

  const { status, gaps, thinking, metadata } = sa_output;

  return (
    <ReportLayout
      icon={FileText}
      title="Architecture QA Analysis"
      subtitle="시스템 설계의 정합성과 무결성을 RAG 기반으로 검증한 분석 리포트입니다."
      badge={metadata?.bundle_id}
      rightElement={
        <div className="flex flex-col items-end gap-1">
          <span className="report-label-sm">Integrity Status</span>
          <Badge variant={status === "FAIL" ? "error" : (status === "WARNING" ? "warning" : "success")} className="px-4 py-1.5 text-sm font-black">
            {status || "UNKNOWN"}
          </Badge>
        </div>
      }
    >
      <ReportSection title="Thinking Process" icon={<Info size={18} />}>
        <Card variant="solid" className="p-8 border-l-4 border-l-blue-500/30">
          <p className={`text-[16px] leading-relaxed italic whitespace-pre-wrap ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>
            "{thinking || "분석 내용이 없습니다."}"
          </p>
        </Card>
      </ReportSection>

      <ReportSection title="Gap Analysis" icon={<AlertTriangle size={18} />}>
        {gaps?.length > 0 ? (
          <div className="report-grid-2">
            {gaps.map((gap, idx) => (
              <Card key={idx} variant="glass" className="p-5 border-l-4 border-l-red-500/50 hover:border-l-red-500 transition-all">
                <div className="flex items-start gap-4">
                  <AlertTriangle className="text-red-500 shrink-0 mt-1" size={18} />
                  <p className={`text-[15px] font-medium leading-relaxed ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>{gap}</p>
                </div>
              </Card>
            ))}
          </div>
        ) : (
          <Card variant="glass" className="p-8 flex items-center gap-4 border-l-4 border-l-emerald-500/50">
            <CheckCircle className="text-emerald-500" size={32} />
            <p className="text-lg font-bold text-emerald-500/90">아키텍처 정합성이 완벽하게 유지되고 있습니다.</p>
          </Card>
        )}
      </ReportSection>
    </ReportLayout>
  );
}
