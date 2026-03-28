import React from "react";
import useAppStore from "../../store/useAppStore";
import { StatCard, EmptyState } from "./SharedComponents";
import { Tag } from "lucide-react";

export default function OverviewTab() {
  const {
    metadata,
    requirements_rtm,
    context_spec,
    sa_reverse_context,
    sa_phase2,
    sa_phase3,
    sa_phase5,
    sa_artifacts,
    resultData,
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

  const fallbackStats = {
    total: requirements_rtm.length,
    must: requirements_rtm.filter((r) => r.priority === "Must-have").length,
    should: requirements_rtm.filter((r) => r.priority === "Should-have").length,
    could: requirements_rtm.filter((r) => r.priority === "Could-have").length,
  };
  const stats = {
    total: projectOverview?.requirement_count ?? fallbackStats.total,
    must: projectOverview?.priority_counts?.must ?? fallbackStats.must,
    should: projectOverview?.priority_counts?.should ?? fallbackStats.should,
    could: projectOverview?.priority_counts?.could ?? fallbackStats.could,
  };

  const categories = {};
  requirements_rtm.forEach((r) => {
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

  const pmStatus = pmOverview?.status || metadata?.status || "-";
  const pmSummary = pmOverview?.summary || context_spec?.summary || "";
  const pmRequirementCount = Number(pmOverview?.requirement_count ?? stats.total ?? 0);
  const pmRiskList = Array.isArray(pmOverview?.risks) ? pmOverview.risks : risks;

  const feasibility = saOverview?.feasibility || sa_phase3 || {};
  const saStatus = feasibility?.status || "Needs_Clarification";
  const saComplexity = feasibility?.complexity_score;
  const saReasons = Array.isArray(feasibility?.reasons) ? feasibility.reasons : [];
  const saAlternatives = Array.isArray(feasibility?.alternatives) ? feasibility.alternatives : [];
  const saHighRiskReqs = Array.isArray(feasibility?.high_risk_reqs) ? feasibility.high_risk_reqs : [];
  const saCriticalGaps = Array.isArray(saOverview?.critical_gaps)
    ? saOverview.critical_gaps
    : (Array.isArray(sa_phase2?.gap_report) ? sa_phase2.gap_report : []);
  const saSkippedPhases = Array.isArray(saOverview?.skipped_phases) ? saOverview.skipped_phases : [];
  const architecturePattern = sa_phase5?.pattern || projectOverview?.architecture_pattern || "Clean Architecture";
  const hasCategoryData = Object.keys(categories).length > 0;

  const mode = String(actionType || "").toUpperCase();
  const isReverseMode = mode === "REVERSE_ENGINEER";
  const decisionReasons = [
    ...new Set(
      [
        ...(saCriticalGaps || []).slice(0, 1).map((gap) => `막힌 항목: ${gap}`),
        ...(saHighRiskReqs || []).slice(0, 1).map((req) => `고위험 요구사항: ${req}`),
        ...(saReasons || []).slice(0, 1),
        ...(pmRiskList || []).slice(0, 1).map((risk) => `리스크: ${risk}`),
      ].filter(Boolean)
    ),
  ].slice(0, 2);
  const nextAction =
    (projectOverview?.next_actions || [])[0] ||
    (isReverseMode
      ? "핵심 모듈 기준으로 통합 테스트와 관측성(로그/메트릭) 검증을 먼저 진행하세요."
      : "요구사항 우선순위 기준으로 MVP 범위를 확정하고 구현 순서를 고정하세요.");
  const nextActionsList = (projectOverview?.next_actions || []).length > 0
    ? projectOverview.next_actions
    : [nextAction];

  let decisionLabel = "진행 가능";
  let decisionTone = "bg-green-600/20 text-green-300";
  if (saStatus === "Needs_Clarification") {
    decisionLabel = "정보 보강 필요";
    decisionTone = "bg-yellow-600/20 text-yellow-300";
  } else if (saStatus === "Fail" || saCriticalGaps.length >= 3 || saHighRiskReqs.length > 0) {
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
    <div className="h-full overflow-y-auto p-4 space-y-4 text-[15px]">
      <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700/50">
        <h3 className="text-sm font-semibold text-slate-200 mb-2">
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
            <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">
              Unified Overview
            </span>
          )}
        </div>
        {summaryText && (
          <p className="mt-3 text-[15px] text-slate-300 leading-relaxed">
            {summaryText}
          </p>
        )}
      </div>

      {(hasProjectOverview || hasSaFallbackSummary) && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700/50 text-center">
            <div className={`text-3xl font-bold ${criticalGapCount > 0 ? "text-orange-300" : "text-slate-500"}`}>{criticalGapCount}</div>
            <div className="text-[12px] text-slate-500 mt-1">막힌 항목</div>
          </div>
          <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700/50 text-center">
            <div className="text-3xl font-bold text-blue-300">{componentCount}</div>
            <div className="text-[12px] text-slate-500 mt-1">주요 컴포넌트</div>
          </div>
          <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700/50 text-center">
            <div className={`text-3xl font-bold ${externalCount > 0 ? "text-amber-300" : "text-slate-500"}`}>{externalCount}</div>
            <div className="text-[12px] text-slate-500 mt-1">외부 의존 경계</div>
          </div>
        </div>
      )}

      <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700/50 space-y-3">
        <div className="flex items-center gap-2">
          <h4 className="text-sm font-medium text-slate-300">의사결정 요약</h4>
          <span className={`px-2 py-0.5 rounded text-[12px] ${decisionTone}`}>{decisionLabel}</span>
          {isReverseMode && (
            <span className="px-2 py-0.5 rounded text-[12px] bg-slate-800 text-slate-300">역공학 모드</span>
          )}
        </div>
        {decisionReasons.length > 0 ? (
          <ul className="space-y-1">
            {decisionReasons.map((reason, idx) => (
              <li key={idx} className="text-sm text-slate-300">- {reason}</li>
            ))}
          </ul>
        ) : (
          <div className="text-sm text-slate-500">핵심 근거 데이터가 부족합니다.</div>
        )}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700/50 space-y-3">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-medium text-slate-300">PM 요약</h4>
            <span className={`px-2 py-0.5 rounded text-[12px] ${pmStatus === "Success" || pmStatus === "Pass" ? "bg-green-600/20 text-green-300" : "bg-yellow-600/20 text-yellow-300"}`}>
              {pmStatus}
            </span>
          </div>

          {hasPmContent ? (
            <>
              {pmSummary ? (
                <p className="text-[14px] text-slate-300 leading-relaxed">{pmSummary}</p>
              ) : (
                <div className="min-h-16 rounded border border-slate-800/80 bg-slate-900/30 flex items-center justify-center text-center text-[13px] text-slate-500 px-3">
                  요약 텍스트는 없지만 요구사항/리스크 구조는 확인 가능합니다.
                </div>
              )}

              {visibleTopStats.length > 0 && (
                <div className={`grid gap-3 ${visibleTopStats.length >= 4 ? "grid-cols-4" : visibleTopStats.length === 3 ? "grid-cols-3" : "grid-cols-2"}`}>
                  {visibleTopStats.map((item) => (
                    <StatCard key={item.label} label={item.label} value={item.value} color={item.color} />
                  ))}
                </div>
              )}

              {visiblePmStats.length > 0 && (
                <div className={`grid gap-3 ${visiblePmStats.length >= 2 ? "grid-cols-2" : "grid-cols-1"}`}>
                  {visiblePmStats.map((item) => (
                    <StatCard key={item.label} label={item.label} value={item.value} color={item.color} />
                  ))}
                </div>
              )}

              <div>
                <h5 className="text-sm font-medium text-slate-400 mb-2">카테고리 분포</h5>
                {hasCategoryData ? (
                  <div className="space-y-2">
                    {Object.entries(categories).map(([cat, count]) => (
                      <div key={cat} className="flex items-center gap-2">
                        <Tag size={11} className="text-slate-500" />
                        <span className="text-sm text-slate-300 flex-1">{cat}</span>
                        <span className="text-sm text-slate-500">{count}</span>
                        <div className="w-24 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-blue-500 rounded-full"
                            style={{ width: `${stats.total > 0 ? (count / stats.total) * 100 : 0}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="min-h-16 rounded border border-dashed border-slate-700/80 bg-slate-900/20 flex items-center justify-center text-center text-[13px] text-slate-500 px-3">
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
                      <li key={idx} className="text-sm text-slate-300">- {risk}</li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          ) : (
            <div className="min-h-20 rounded border border-dashed border-slate-700/80 bg-slate-900/20 flex items-center justify-center text-center text-[13px] text-slate-500 px-3">
              {isReverseMode
                ? "RTM 데이터가 입력되지 않아 PM 분석이 생략되었습니다."
                : "PM 요약 데이터가 아직 생성되지 않았습니다."}
            </div>
          )}
        </div>

        <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700/50 space-y-3">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-medium text-slate-300">SA 요약</h4>
            <span className={`px-2 py-0.5 rounded text-[12px] ${saStatus === "Pass" ? "bg-green-600/20 text-green-300" : "bg-yellow-600/20 text-yellow-300"}`}>
              {saStatus}
            </span>
            <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[12px]">{architecturePattern}</span>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <StatCard label="기술 타당성" value={saStatus} color={saStatus === "Pass" ? "text-green-300" : "text-yellow-300"} />
            <StatCard label="구현 난이도" value={saComplexity ?? "-"} color="text-purple-300" />
          </div>

          <div>
            <div className="text-[12px] text-slate-500 mb-1.5">판정 근거</div>
            {saReasons.length > 0 ? (
              <ul className="space-y-1">
                {saReasons.slice(0, 8).map((reason, idx) => (
                  <li key={idx} className="text-sm text-slate-300">- {reason}</li>
                ))}
              </ul>
            ) : (
              <div className="text-sm text-slate-500">판정 근거 정보가 없습니다.</div>
            )}
          </div>

          <div>
            <div className="text-[12px] text-slate-500 mb-1.5">대안</div>
            {saAlternatives.length > 0 ? (
              <ul className="space-y-1">
                {saAlternatives.slice(0, 5).map((alt, idx) => (
                  <li key={idx} className="text-sm text-slate-300">- {alt}</li>
                ))}
              </ul>
            ) : (
              <div className="text-sm text-slate-500">대안 정보가 없습니다.</div>
            )}
          </div>

          {saSkippedPhases.length > 0 && (
            <div className="text-[12px] text-slate-500">건너뛴 단계: {saSkippedPhases.join(", ")}</div>
          )}
        </div>
      </div>

      {nextActionsList.length > 0 && (
        <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700/50">
          <h4 className="text-sm font-medium text-slate-400 mb-3">권장 다음 단계</h4>
          <ol className="space-y-1">
            {nextActionsList.map((action, idx) => (
              <li key={idx} className="text-sm text-slate-300">{idx + 1}. {action}</li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
