import React from "react";
import useAppStore from "../../store/useAppStore";
import { StatCard, EmptyState, StatusBadge } from "./SharedComponents";
import { Tag } from "lucide-react";

export default function OverviewTab() {
  const {
    metadata,
    requirements_rtm,
    pm_bundle,
    pm_coverage_rate,
    pm_warnings,
    sa_phase2,
    sa_phase3,
    sa_phase5,
    sa_artifacts,
    resultData,
    thinking_log,
    context_spec,
    sa_reverse_context,
    isDarkMode,
  } = useAppStore();
  const projectOverview = resultData?.project_overview || null;
  const pmOverview = resultData?.pm_overview || null;
  const saOverview = resultData?.sa_overview || null;

  const hasRenderableData = Boolean(
    projectOverview ||
      pmOverview ||
      saOverview ||
      metadata ||
      (requirements_rtm || []).length > 0 ||
      context_spec?.summary ||
      sa_reverse_context?.summary ||
      sa_phase2 ||
      sa_phase3 ||
      sa_artifacts
  );

  if (!hasRenderableData) {
    return <EmptyState text="분석 결과가 없습니다" />;
  }

  const safeRtm = Array.isArray(requirements_rtm) ? requirements_rtm : [];
  const fallbackStats = {
    total: safeRtm.length,
    must: safeRtm.filter((r) => r.priority === "Must-have").length,
    should: safeRtm.filter((r) => r.priority === "Should-have").length,
    could: safeRtm.filter((r) => r.priority === "Could-have").length,
  };
  const stats = {
    total: projectOverview?.requirement_count ?? fallbackStats.total,
    must: projectOverview?.priority_counts?.must ?? fallbackStats.must,
    should: projectOverview?.priority_counts?.should ?? fallbackStats.should,
    could: projectOverview?.priority_counts?.could ?? fallbackStats.could,
  };

  const categories = {};
  safeRtm.forEach((r) => {
    const cat = r.category || "기타";
    categories[cat] = (categories[cat] || 0) + 1;
  });
  const summaryText =
    projectOverview?.summary ||
    context_spec?.summary ||
    sa_reverse_context?.summary ||
    (sa_phase3?.reasons || [])[0] ||
    "SA 기반 분석 결과를 요약했습니다.";

  const inferredProjectName =
    (resultData?.source_dir || "").replace(/\\/g, "/").split("/").filter(Boolean).pop() || "프로젝트";
  const projectName = projectOverview?.project_name || metadata?.project_name || inferredProjectName;
  const actionType = projectOverview?.action_type || metadata?.action_type || resultData?.action_type || "ANALYSIS";
  const status = projectOverview?.status || metadata?.status || sa_phase3?.status || "Pass";
  const risks =
    projectOverview?.risks ||
    pmOverview?.risks ||
    context_spec?.risk_factors ||
    sa_reverse_context?.risk_factors ||
    [];
  const hasProjectOverview = Boolean(projectOverview);
  const fallbackContainerSummary = sa_artifacts?.container_diagram_spec?.summary || {};
  const hasSaFallbackSummary = Boolean(sa_phase2 || sa_phase3 || sa_artifacts);

  const criticalGapCount = projectOverview?.critical_gap_count ?? (sa_phase2?.gap_report || []).length;
  const componentCount =
    projectOverview?.container_summary?.component_count ??
    (fallbackContainerSummary.component_count || 0);
  const externalCount =
    projectOverview?.container_summary?.external_count ??
    (fallbackContainerSummary.external_count || 0);

  const pmStatus = pm_bundle ? (pm_coverage_rate >= 0.9 ? "Perfect" : "Pass") : "-";
  const safeThinkingLog = Array.isArray(thinking_log) ? thinking_log : [];
  const pmSummary = safeThinkingLog.find((l) => l.node === "pm_analysis")?.thinking || "";
  const pmRequirementCount = safeRtm.length;
  const pmRiskList = Array.isArray(pm_warnings) ? pm_warnings : (typeof pm_warnings === "string" ? [pm_warnings] : []);

  const sa_output = useAppStore(s => s.sa_output);
  const saStatus = sa_output?.status || "PENDING";
  const saCriticalGaps = Array.isArray(sa_output?.gaps) ? sa_output.gaps : [];
  const architecturePattern = metadata?.architecture_pattern || "Clean Architecture";
  const hasCategoryData = Object.keys(categories).length > 0;

  const mode = String(actionType || "").toUpperCase();
  const isReverseMode = mode === "REVERSE_ENGINEER";
  const decisionReasons = [
    ...new Set(
      [
        ...(saCriticalGaps || []).slice(0, 2).map((gap) => `설계 결함: ${gap}`),
        ...(pmRiskList || []).slice(0, 1).map((risk) => `비즈니스 리스크: ${risk}`),
      ].filter(Boolean)
    ),
  ].slice(0, 2);
  const nextAction =
    (projectOverview?.next_actions || [])[0] ||
    (isReverseMode
      ? "핵심 모듈 기준으로 통합 테스트와 관측성(로그/메트릭) 검증을 먼저 진행하세요."
      : "요구사항 우선순위 기준으로 MVP 범위를 확정하고 구현 순서를 고정하세요.");
  const nextActionsUnsafe = projectOverview?.next_actions;
  const nextActionsSafe = Array.isArray(nextActionsUnsafe) ? nextActionsUnsafe : (typeof nextActionsUnsafe === "string" ? [nextActionsUnsafe] : []);
  const nextActionsList = nextActionsSafe.length > 0 ? nextActionsSafe : [nextAction];

  let decisionLabel = "진행 가능";
  let decisionTone = "bg-green-600/20 text-green-300";
  if (saStatus === "FAIL") {
    decisionLabel = "설계 재검토 필요";
    decisionTone = "bg-red-600/20 text-red-300";
  } else if (saStatus === "WARNING" || saCriticalGaps.length > 0) {
    decisionLabel = "주의 필요";
    decisionTone = "bg-orange-600/20 text-orange-300";
  }

  const visibleTopStats = [
    { label: "전체", value: stats.total, color: "text-slate-200" },
    { label: "Must-have", value: stats.must, color: "text-red-400" },
    { label: "Should-have", value: stats.should, color: "text-yellow-400" },
    { label: "Could-have", value: stats.could, color: "text-green-400" },
  ].filter((item) => Number(item.value || 0) > 0);

  const visiblePmStats = [
    { label: "요구사항 수", value: pmRequirementCount, color: "text-blue-300" },
    { label: "리스크 수", value: pmRiskList.length, color: "text-orange-300" },
  ].filter((item) => Number(item.value || 0) > 0);
  const hasPmContent = Boolean(pmSummary || visibleTopStats.length > 0 || hasCategoryData || pmRiskList.length > 0);

  return (
    <div className={`h-full overflow-y-auto p-4 space-y-4 text-[15px] transition-colors duration-200 ${isDarkMode ? "bg-[var(--bg-primary)]" : "bg-[var(--bg-secondary)]"}`}>
      <div className={`rounded-lg p-4 border transition-all ${isDarkMode ? "bg-slate-900/50 border-slate-700/50" : "bg-white border-slate-200 shadow-sm"}`}>
        <h3 className={`text-sm font-semibold mb-2 ${isDarkMode ? "text-slate-200" : "text-slate-800"}`}>
          {projectName}
        </h3>
        <div className="flex items-center gap-3 text-[12px]">
          <span className="px-2 py-0.5 rounded bg-blue-600/20 text-blue-300">
            {actionType}
          </span>
          <span
            className={`px-2 py-0.5 rounded ${
              status === "Success" || status === "Pass"
                ? "bg-green-600/20 text-green-300"
                : "bg-yellow-600/20 text-yellow-300"
            }`}
          >
            {status}
          </span>
          {hasProjectOverview && (
            <span className={`px-2 py-0.5 rounded ${isDarkMode ? "bg-slate-800 text-slate-300" : "bg-slate-100 text-slate-600 border border-slate-200"}`}>
              Unified Overview
            </span>
          )}
        </div>
        {summaryText && (
          <p className={`mt-3 text-[15px] leading-relaxed ${isDarkMode ? "text-slate-300" : "text-slate-600"}`}>
            {summaryText}
          </p>
        )}
      </div>

      {(hasProjectOverview || hasSaFallbackSummary) && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {[
              { label: "막힌 항목", value: criticalGapCount, color: criticalGapCount > 0 ? "text-orange-400" : (isDarkMode ? "text-slate-500" : "text-slate-300") },
              { label: "주요 컴포넌트", value: componentCount, color: "text-blue-500" },
              { label: "외부 의존 경계", value: externalCount, color: externalCount > 0 ? "text-amber-500" : (isDarkMode ? "text-slate-500" : "text-slate-300") }
            ].map((stat, i) => (
              <div key={i} className={`rounded-lg p-4 border text-center transition-all ${isDarkMode ? "bg-slate-900/50 border-slate-700/50" : "bg-white border-slate-200 shadow-sm"}`}>
                <div className={`text-3xl font-bold ${stat.color}`}>{stat.value}</div>
                <div className="text-[12px] text-slate-500 mt-1">{stat.label}</div>
              </div>
            ))}
          </div>

          {projectOverview?.usage_summary && (
            <div className={`rounded-lg p-4 border transition-all ${isDarkMode ? "bg-slate-900/50 border-slate-700/50" : "bg-white border-slate-200 shadow-sm"}`}>
              <div className="flex items-center justify-between mb-3">
                <h4 className={`text-sm font-medium ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>Resource Usage (Cost Optimization)</h4>
                <span className="text-[12px] text-green-400 font-mono">
                  ${Number(projectOverview.usage_summary.total_cost || 0).toFixed(4)}
                </span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <div className="text-[11px] text-slate-500 uppercase tracking-wider">Total Tokens</div>
                  <div className={`text-lg font-semibold ${isDarkMode ? "text-slate-200" : "text-slate-800"}`}>
                    {Number(projectOverview.usage_summary.total_tokens || 0).toLocaleString()}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] text-slate-500 uppercase tracking-wider">Input</div>
                  <div className="text-lg font-semibold text-blue-400">
                    {Number(projectOverview.usage_summary.input_tokens || 0).toLocaleString()}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] text-slate-500 uppercase tracking-wider">Output</div>
                  <div className="text-lg font-semibold text-purple-400">
                    {Number(projectOverview.usage_summary.output_tokens || 0).toLocaleString()}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] text-slate-500 uppercase tracking-wider">Estimated Cost</div>
                  <div className="text-lg font-semibold text-green-400">
                    ${Number(projectOverview.usage_summary.total_cost || 0).toFixed(5)}
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      <div className={`rounded-lg p-4 border space-y-3 transition-all ${isDarkMode ? "bg-slate-900/50 border-slate-700/50" : "bg-white border-slate-200 shadow-sm"}`}>
        <div className="flex items-center gap-2">
          <h4 className={`text-sm font-medium ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>의사결정 요약</h4>
          <span className={`px-2 py-0.5 rounded text-[12px] ${decisionTone}`}>{decisionLabel}</span>
          {isReverseMode && (
            <span className={`px-2 py-0.5 rounded text-[12px] ${isDarkMode ? "bg-slate-800 text-slate-300" : "bg-slate-100 text-slate-600 border border-slate-200"}`}>역공학 모드</span>
          )}
        </div>
        {decisionReasons.length > 0 ? (
          <ul className="space-y-1">
            {decisionReasons.map((reason, idx) => (
              <li key={idx} className={`text-sm ${isDarkMode ? "text-slate-300" : "text-slate-600"}`}>- {reason}</li>
            ))}
          </ul>
        ) : (
          <div className="text-sm text-slate-500">핵심 근거 데이터가 부족합니다.</div>
        )}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className={`rounded-lg p-4 border space-y-3 transition-all ${isDarkMode ? "bg-slate-900/50 border-slate-700/50" : "bg-white border-slate-200 shadow-sm"}`}>
          <div className="flex items-center gap-2">
            <h4 className={`text-sm font-medium ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>PM 요약</h4>
            <span className={`px-2 py-0.5 rounded text-[12px] ${pmStatus === "Success" || pmStatus === "Pass" ? "bg-green-600/20 text-green-300" : "bg-green-100 text-green-700 border border-green-200"}`}>
              {pmStatus}
            </span>
          </div>

          {hasPmContent ? (
            <>
              {pmSummary ? (
                <p className={`text-[14px] leading-relaxed ${isDarkMode ? "text-slate-300" : "text-slate-600"}`}>{pmSummary}</p>
              ) : (
                <div className={`min-h-16 rounded border flex items-center justify-center text-center text-[13px] px-3 ${isDarkMode ? "border-slate-800/80 bg-slate-900/30 text-slate-500" : "border-slate-100 bg-slate-50 text-slate-400"}`}>
                  요약 텍스트는 없지만 요구사항/리스크 구조는 확인 가능합니다.
                </div>
              )}

              {(pm_bundle || visibleTopStats.length > 0) && (
                <div className="grid grid-cols-2 gap-3">
                  <StatCard label="기술 커버리지" value={`${(pm_coverage_rate * 100).toFixed(0)}%`} color="text-blue-400" />
                  <StatCard label="발견된 리스크" value={pmRiskList.length} color="text-orange-400" />
                </div>
              )}

              <div>
                <h5 className={`text-sm font-medium mb-2 ${isDarkMode ? "text-slate-400" : "text-slate-700"}`}>카테고리 분포</h5>
                {hasCategoryData ? (
                  <div className="space-y-2">
                    {Object.entries(categories).map(([cat, count]) => (
                      <div key={cat} className="flex items-center gap-2">
                        <Tag size={11} className="text-slate-500" />
                        <span className={`text-sm flex-1 ${isDarkMode ? "text-slate-300" : "text-slate-600"}`}>{cat}</span>
                        <span className="text-sm text-slate-500">{count}</span>
                        <div className={`w-24 h-1.5 rounded-full overflow-hidden ${isDarkMode ? "bg-slate-800" : "bg-slate-100"}`}>
                          <div
                            className="h-full bg-blue-500 rounded-full"
                            style={{ width: `${stats.total > 0 ? (count / stats.total) * 100 : 0}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className={`min-h-16 rounded border border-dashed flex items-center justify-center text-center text-[13px] px-3 ${isDarkMode ? "border-slate-700/80 bg-slate-900/20 text-slate-500" : "border-slate-200 bg-slate-50/50 text-slate-400"}`}>
                    {isReverseMode
                      ? "RTM 데이터가 입력되지 않아 분석이 생략되었습니다."
                      : "카테고리 데이터가 없어 분포를 계산할 수 없습니다."}
                  </div>
                )}
              </div>

              {pmRiskList.length > 0 && (
                <div>
                  <div className="text-[12px] text-slate-500 mb-1.5">리스크</div>
                  <ul className="space-y-1">
                    {pmRiskList.slice(0, 8).map((risk, idx) => (
                      <li key={idx} className={`text-sm ${isDarkMode ? "text-slate-300" : "text-slate-600"}`}>- {risk}</li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          ) : (
            <div className={`min-h-20 rounded border border-dashed flex items-center justify-center text-center text-[13px] px-3 ${isDarkMode ? "border-slate-700/80 bg-slate-900/20 text-slate-500" : "border-slate-200 bg-slate-50/50 text-slate-400"}`}>
              {isReverseMode
                ? "RTM 데이터가 입력되지 않아 PM 분석이 생략되었습니다."
                : "PM 요약 데이터가 아직 생성되지 않았습니다."}
            </div>
          )}
        </div>

        <div className={`rounded-lg p-4 border space-y-3 transition-all ${isDarkMode ? "bg-slate-900/50 border-slate-700/50" : "bg-white border-slate-200 shadow-sm"}`}>
          <div className="flex items-center gap-2">
            <h4 className={`text-sm font-medium ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>SA 요약</h4>
            <StatusBadge status={saStatus} />
            <span className={`px-2 py-0.5 rounded text-[12px] ${isDarkMode ? "bg-slate-800 text-slate-300" : "bg-slate-100 text-slate-600 border border-slate-200"}`}>{architecturePattern}</span>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="text-center p-2 rounded bg-slate-800/30 border border-slate-700/50">
              <div className="text-lg font-bold text-blue-400">{(sa_output?.data?.components || []).length}</div>
              <div className="text-[10px] text-slate-500 uppercase">Components</div>
            </div>
            <div className="text-center p-2 rounded bg-slate-800/30 border border-slate-700/50">
              <div className="text-lg font-bold text-cyan-400">{(sa_output?.data?.apis || []).length}</div>
              <div className="text-[10px] text-slate-500 uppercase">APIs</div>
            </div>
            <div className="text-center p-2 rounded bg-slate-800/30 border border-slate-700/50">
              <div className="text-lg font-bold text-amber-400">{(sa_output?.data?.tables || []).length}</div>
              <div className="text-[10px] text-slate-500 uppercase">Tables</div>
            </div>
          </div>

          <div>
            <div className="text-[12px] text-slate-500 mb-1.5">품질 진단 요약</div>
            <p className={`text-[14px] leading-relaxed ${isDarkMode ? "text-slate-300" : "text-slate-600"}`}>
              {sa_output?.thinking?.split("\n")[0] || "아키텍처 설계가 완료되었습니다."}
            </p>
          </div>
        </div>
      </div>

      {nextActionsList.length > 0 && (
        <div className={`rounded-lg p-4 border transition-all ${isDarkMode ? "bg-slate-900/50 border-slate-700/50" : "bg-white border-slate-200 shadow-sm"}`}>
          <h4 className={`text-sm font-medium mb-3 ${isDarkMode ? "text-slate-400" : "text-slate-700"}`}>권장 다음 단계</h4>
          <ol className="space-y-1">
            {nextActionsList.map((action, idx) => (
              <li key={idx} className={`text-sm ${isDarkMode ? "text-slate-300" : "text-slate-600"}`}>
                {idx + 1}. {typeof action === "string" ? action : String(action)}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
