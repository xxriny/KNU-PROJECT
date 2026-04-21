import React from "react";
import useAppStore from "../../store/useAppStore";
import {
  ReportHeader,
  ReportSection,
  ReportTable,
  EmptyState,
  StatusBadge,
  AnimatedCounter
} from "./SharedComponents";
import { Tag, CheckCircle2, AlertTriangle, Info } from "lucide-react";

export default function OverviewTab() {
  const {
    requirements_rtm,
    pm_bundle,
    pm_coverage_rate,
    pm_warnings,
    sa_artifacts,
    resultData,
    thinking_log,
    context_spec,
    sa_reverse_context,
    isDarkMode,
    metadata,
    sa_output,
    currentSessionId,
    sessions
  } = useAppStore();

  const currentSession = sessions.find(s => s.id === currentSessionId);
  const projectOverview = resultData?.project_overview || null;
  const pmOverview = resultData?.pm_overview || null;

  const hasRenderableData = Boolean(
    projectOverview ||
    pmOverview ||
    metadata ||
    (requirements_rtm || []).length > 0 ||
    context_spec?.summary ||
    sa_reverse_context?.summary ||
    sa_artifacts
  );

  if (!hasRenderableData) {
    return <EmptyState text="분석 결과가 없습니다" />;
  }

  const summaryText =
    projectOverview?.summary ||
    context_spec?.summary ||
    sa_reverse_context?.summary ||
    "시스템 기반 분석 결과를 종합하여 보고서를 작성하였습니다.";

  const inferredProjectName =
    (resultData?.source_dir || "").replace(/\\/g, "/").split("/").filter(Boolean).pop() || "미지정 프로젝트";

  // 세션 별칭(Alias)이 최우선이고, 없으면 기존 메타데이터나 폴더명 사용
  const projectName = currentSession?.name || projectOverview?.project_name || metadata?.project_name || inferredProjectName;
  const actionType = projectOverview?.action_type || metadata?.action_type || resultData?.action_type || "ANALYSIS";

  const safeThinkingLog = Array.isArray(thinking_log) ? thinking_log : [];
  const pmSummary = safeThinkingLog.find((l) => l.node === "pm_analysis")?.thinking || pmOverview?.insights || "";
  const pmRiskList = Array.isArray(pm_warnings) ? pm_warnings : (typeof pm_warnings === "string" ? [pm_warnings] : []);

  const saStatus = sa_output?.status || "PENDING";
  const saCriticalGaps = Array.isArray(sa_output?.gaps) ? sa_output.gaps : [];

  const nextActionsUnsafe = projectOverview?.next_actions;
  const nextActionsList = Array.isArray(nextActionsUnsafe) ? nextActionsUnsafe : (typeof nextActionsUnsafe === "string" ? [nextActionsUnsafe] : []);

  // 리소스 지표 표 데이터
  const usage = projectOverview?.usage_summary || {};
  const usageRows = [
    ["Total Tokens", usage.total_tokens?.toLocaleString() || "0", "전체 사용량"],
    ["Input Tokens", usage.input_tokens?.toLocaleString() || "0", "입력/컨텍스트"],
    ["Output Tokens", usage.output_tokens?.toLocaleString() || "0", "생성/추론"],
    ["Estimated Cost", `$${Number(usage.total_cost || 0).toFixed(4)}`, "예상 비용 (USD)"]
  ];

  return (
    <div className={`h-full overflow-y-auto transition-colors duration-300 ${isDarkMode ? "bg-transparent text-slate-300" : "bg-white text-slate-800"}`}>
      <div className="max-w-4xl mx-auto px-8 py-16 pb-32">

        {/* 헤더 */}
        <ReportHeader
          title={`${projectName} 종합 분석 보고서`}
          subtitle={`소스 분석 및 ${actionType} 파이프라인 기반의 정밀 진단 결과`}
          metadata={{
            "Project ID": metadata?.project_id || "N/A",
            "Action Mode": actionType,
            "Date": new Date().toLocaleDateString(),
            "Integrity Status": saStatus
          }}
        />

        {/* 1. 전략적 개요 */}
        <ReportSection number={1} title="전략적 개요 (Strategic Overview)">
          <p className="indent-4 mb-6">
            본 보고서는 {projectName} 시스템의 소스 코드와 요구사항 명세(RTM)를 바탕으로 수행된 자동화 분석 결과를 담고 있습니다.
            분석 프로세스는 PM 분석 레이어에서 비즈니스 로직의 완결성을 검증하고, QA/SA 레이어에서 아키텍처 정합성과 설계 결함을 식별하는 단계로 진행되었습니다.
          </p>
          <div className={`p-6 rounded-2xl border ${isDarkMode ? "bg-white/5 border-white/10" : "bg-slate-50 border-slate-200"}`}>
            <h4 className="flex items-center gap-2 font-black text-sm mb-3 uppercase tracking-tighter text-blue-500">
              <CheckCircle2 size={16} /> Analysis Executive Summary
            </h4>
            <p className="leading-relaxed">
              {summaryText}
            </p>
          </div>
        </ReportSection>

        {/* 2. 비즈니스 분석 인사이트 */}
        <ReportSection number={2} title="비즈니스 및 요구사항 분석 (PM Insights)">
          <p className="indent-4 mb-4">
            PM(Product Management) 분석 모듈은 시스템이 비즈니스 요구사항을 얼마나 충실히 반영하고 있는지, 그리고 구현된 기능들이 논리적으로 타당한지를 검증합니다.
          </p>

          {pmSummary && (
            <div className={`my-6 pl-4 border-l-4 border-blue-500/30 py-1`}>
              <p className="italic text-[15px] opacity-90">{pmSummary}</p>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 my-8">
            <div className="space-y-4">
              <h5 className="text-[13px] font-black uppercase text-slate-500 tracking-wider">구현 정합성 지표</h5>
              <div className="flex items-end gap-3 px-1">
                <span className="text-4xl font-black text-blue-500">
                  <AnimatedCounter value={pm_coverage_rate * 100} />%
                </span>
                <span className="text-xs font-bold text-slate-500 mb-1.5 underline decoration-blue-500/30 underline-offset-4 uppercase">Technical Coverage</span>
              </div>
            </div>

            <div className="space-y-3">
              <h5 className="text-[13px] font-black uppercase text-slate-500 tracking-wider">식별된 비즈니스 리스크</h5>
              {pmRiskList.length > 0 ? (
                <ul className="space-y-2">
                  {pmRiskList.slice(0, 3).map((risk, i) => (
                    <li key={i} className="flex gap-2 text-sm items-start">
                      <AlertTriangle size={14} className="text-orange-400 shrink-0 mt-0.5" />
                      <span>{risk}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm italic opacity-50">특별한 비즈니스 리스크가 발견되지 않았습니다.</p>
              )}
            </div>
          </div>
        </ReportSection>

        {/* 3. QA 및 아키텍처 정합성 검증 */}
        <ReportSection number={3} title="품질 보증 및 아키텍처 정합성 (QA/SA)">
          <p className="indent-4 mb-6">
            SA(Software Architecture) 분석 모듈은 소스 코드로부터 추출된 실제 구조와 설계 의도 간의 정합성을 검증합니다.
            엔터티 관계, API 명세, 데이터베이스 스키마 변화를 추적하여 아키텍처 부패 여부를 진단합니다.
          </p>

          <div className="grid grid-cols-3 gap-4 mb-8">
            {[
              { label: "Components", count: (sa_output?.data?.components || []).length, unit: "EA" },
              { label: "Internal APIs", count: (sa_output?.data?.apis || []).length, unit: "EA" },
              { label: "DB Tables", count: (sa_output?.data?.tables || []).length, unit: "EA" }
            ].map((item, i) => (
              <div key={i} className={`p-4 rounded-xl border ${isDarkMode ? "bg-white/5 border-white/5" : "bg-slate-50 border-slate-100"}`}>
                <div className="text-[10px] font-black text-slate-500 uppercase mb-1 tracking-widest">{item.label}</div>
                <div className="flex items-baseline gap-1">
                  <span className="text-xl font-black">{item.count}</span>
                  <span className="text-[10px] font-bold opacity-30">{item.unit}</span>
                </div>
              </div>
            ))}
          </div>

          <div className={`p-8 rounded-2xl border-2 ${isDarkMode ? "bg-red-500/5 border-red-500/20 shadow-[0_0_30px_rgba(239,68,68,0.05)]" : "bg-red-50 border-red-200"}`}>
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <AlertTriangle size={24} className="text-red-500" />
                <h4 className={`text-xl font-black tracking-tight ${isDarkMode ? "text-white" : "text-slate-900"}`}>
                  Architecture Consistency Status
                </h4>
              </div>
              <StatusBadge status={saStatus} />
            </div>

            <div className="flex items-center justify-between mb-8 px-1">
              <span className={`text-[15px] font-medium ${isDarkMode ? "text-slate-400" : "text-slate-600"}`}>검증 결과 상태</span>
              <div className={`px-3 py-1 rounded-md text-[11px] font-black uppercase tracking-widest ${saStatus === "FAIL" ? "bg-red-500 text-white" : "bg-orange-500 text-white"}`}>
                Critical Findings Detected
              </div>
            </div>

            {saCriticalGaps.length > 0 && (
              <div className={`pt-6 border-t ${isDarkMode ? "border-red-500/10" : "border-red-200"}`}>
                <div className="text-[14px] font-black text-red-500 uppercase mb-5 tracking-tighter flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                  중요 설계 결함 상세 발췌
                </div>
                <ul className="space-y-4">
                  {saCriticalGaps.map((gap, i) => (
                    <li key={i} className={`flex gap-4 p-4 rounded-xl ${isDarkMode ? "bg-white/5" : "bg-white border border-red-100 shadow-sm"}`}>
                      <span className="text-red-500 font-black text-lg select-none">!</span>
                      <span className={`text-[17px] font-medium leading-relaxed ${isDarkMode ? "text-slate-200" : "text-slate-700"}`}>{gap}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </ReportSection>

        {/* 4. 권장 조치 사항 */}
        {nextActionsList.length > 0 && (
          <ReportSection number={4} title="향후 권장 조치 사항 (Recommendations)">
            <p className="mb-6">
              분석 결과를 바탕으로 최적의 시스템 품질을 유지하기 위해 다음의 조치 사항을 권고합니다.
            </p>
            <div className="space-y-3 px-2">
              {nextActionsList.map((action, idx) => (
                <div key={idx} className={`group flex gap-4 p-4 rounded-2xl transition-all ${isDarkMode ? "hover:bg-white/5" : "hover:bg-slate-50 border border-transparent hover:border-slate-200"}`}>
                  <div className="flex items-center justify-center w-8 h-8 rounded-full bg-blue-500/10 text-blue-500 font-mono font-black text-xs shrink-0">
                    {idx + 1}
                  </div>
                  <div className="flex-1 text-[15px] self-center">
                    {typeof action === "string" ? action : String(action)}
                  </div>
                </div>
              ))}
            </div>
          </ReportSection>
        )}

        {/* 5. 비고: 리소스 최적화 지표 (표 형식) */}
        <div className="mt-24 pt-12 border-t-2 border-dashed border-white/10">
          <ReportSection number={5} title="비고: 리소스 최적화 및 비용 산출 지표">
            <p className="text-sm opacity-60 mb-6">
              본 분석 파이프라인 수행 과정에서 소모된 계산 자원 및 AI 모델 비용 산출 내역입니다. 이는 리소스 최적화 및 예산 관리의 근거 자료로 활용될 수 있습니다.
            </p>
            <ReportTable
              title="Pipeline Execution Usage & Cost Detail"
              headers={["Category", "Value", "Notes"]}
              rows={usageRows}
            />
          </ReportSection>
        </div>

        {/* 꼬리말 */}
        <div className="mt-32 text-center">
          <div className="inline-block w-12 h-1 bg-blue-500/30 rounded-full mb-8" />
          <p className="text-[11px] font-black text-slate-500 uppercase tracking-[0.5em] select-none opacity-50">
            End of Analysis Report
          </p>
        </div>

      </div>
    </div>
  );
}
