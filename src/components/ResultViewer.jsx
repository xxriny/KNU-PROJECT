/**
 * ResultViewer — 파이프라인 산출물 뷰어
 * 탭에 따라 Overview / RTM / Topology / Context 렌더링
 */

import React, { useMemo, useState } from "react";
import useAppStore from "../store/useAppStore";
import TopologyGraph from "./TopologyGraph";
import SAArtifactGraph from "./SAArtifactGraph";
import {
  normalizeFlowchartForGraph,
  normalizeUMLForGraph,
  normalizeContainerDiagramForGraph,
} from "./saGraphAdapters";
import {
  CheckCircle,
  AlertTriangle,
  ArrowRight,
  Tag,
  Shield,
  Lightbulb,
  AlertCircle,
  Cpu,
  GitBranch,
  Layers,
} from "lucide-react";

export default function ResultViewer({ tabId = "overview" }) {
  let content;
  switch (tabId) {
    case "overview":
      content = <OverviewTab />;
      break;
    case "rtm":
      content = <RTMTab />;
      break;
    case "topology":
      content = <TopologyTab />;
      break;
    case "context":
      content = <ContextTab />;
      break;
    case "sa_overview":
      content = <OverviewTab />;
      break;
    case "sa_feasibility":
      content = <OverviewTab />;
      break;
    case "sa_architecture":
      content = <SAArchitectureTab />;
      break;
    case "sa_security":
      content = <SASecurityTab />;
      break;
    case "sa_topology":
      content = <SATopologyTab />;
      break;
    case "sa_system":
      content = <SASystemDiagramTab />;
      break;
    case "sa_flowchart":
      content = <SAFlowchartTab />;
      break;
    case "sa_uml":
      content = <SAUMLComponentTab />;
      break;
    case "sa_interfaces":
      content = <SAInterfacesTab />;
      break;
    case "sa_decisions":
      content = <SADecisionTableTab />;
      break;
    default:
      content = <OverviewTab />;
      break;
  }

  return <div className="doc-font-up">{content}</div>;
}

// ═══════════════════════════════════════════
//  Overview Tab
// ═══════════════════════════════════════════

function OverviewTab() {
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
      {/* 프로젝트 정보 */}
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

      {/* 의사결정 요약 */}
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
        {/* PM Summary */}
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

        {/* SA Summary */}
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

function StatCard({ label, value, color }) {
  return (
    <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700/50 text-center">
      <div className={`text-xl font-bold ${color}`}>{value}</div>
      <div className="text-[12px] text-slate-500 mt-0.5">{label}</div>
    </div>
  );
}

// ═══════════════════════════════════════════
//  RTM Tab
// ═══════════════════════════════════════════

function RTMTab() {
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

function PriorityBadge({ priority }) {
  const colors = {
    "Must-have": "bg-red-600/20 text-red-300",
    "Should-have": "bg-yellow-600/20 text-yellow-300",
    "Could-have": "bg-green-600/20 text-green-300",
  };
  return (
    <span className={`px-1.5 py-0.5 rounded text-[12px] ${colors[priority] || "bg-slate-700 text-slate-400"}`}>
      {priority}
    </span>
  );
}

// ═══════════════════════════════════════════
//  Topology Tab
// ═══════════════════════════════════════════

function TopologyTab() {
  const { semantic_graph, requirements_rtm } = useAppStore();

  if (!semantic_graph || !semantic_graph.nodes || semantic_graph.nodes.length === 0) {
    return <EmptyState text="시맨틱 그래프 데이터가 없습니다" />;
  }

  return (
    <div className="h-full">
      <TopologyGraph semanticGraph={semantic_graph} requirementsRtm={requirements_rtm} />
    </div>
  );
}

// ═══════════════════════════════════════════
//  Context Tab
// ═══════════════════════════════════════════

function ContextTab() {
  const { context_spec, sa_reverse_context } = useAppStore();

  if (!context_spec && !sa_reverse_context) {
    return <EmptyState text="컨텍스트 명세서가 없습니다" />;
  }

  if (!context_spec && sa_reverse_context) {
    return <ReverseContextTab reverseContext={sa_reverse_context} />;
  }

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      {/* 요약 */}
      {context_spec.summary && (
        <Section title="프로젝트 요약" icon={<Lightbulb size={12} />}>
          <p className="text-[14px] text-slate-300 leading-relaxed">
            {context_spec.summary}
          </p>
        </Section>
      )}

      {/* 핵심 결정 */}
      {context_spec.key_decisions?.length > 0 && (
        <Section title="핵심 결정 사항" icon={<CheckCircle size={12} />}>
          <ul className="space-y-1">
            {context_spec.key_decisions.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-[15px] text-slate-400">
                <CheckCircle size={10} className="text-green-400 mt-0.5 flex-shrink-0" />
                {item}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {/* 미해결 질문 */}
      {context_spec.open_questions?.length > 0 && (
        <Section title="미해결 질문" icon={<AlertCircle size={12} />}>
          <ul className="space-y-1">
            {context_spec.open_questions.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-[15px] text-slate-400">
                <AlertCircle size={10} className="text-yellow-400 mt-0.5 flex-shrink-0" />
                {item}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {/* 기술 스택 제안 */}
      {context_spec.tech_stack_suggestions?.length > 0 && (
        <Section title="기술 스택 제안" icon={<Tag size={12} />}>
          <div className="flex flex-wrap gap-1.5">
            {context_spec.tech_stack_suggestions.map((item, idx) => (
              <span
                key={idx}
                className="px-2 py-0.5 rounded bg-blue-600/10 text-blue-300 text-[12px]"
              >
                {item}
              </span>
            ))}
          </div>
        </Section>
      )}

      {/* 리스크 요인 */}
      {context_spec.risk_factors?.length > 0 && (
        <Section title="리스크 요인" icon={<AlertTriangle size={12} />}>
          <ul className="space-y-1">
            {context_spec.risk_factors.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm text-slate-400">
                <Shield size={10} className="text-red-400 mt-0.5 flex-shrink-0" />
                {item}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {/* 다음 단계 */}
      {context_spec.next_steps?.length > 0 && (
        <Section title="다음 단계" icon={<ArrowRight size={12} />}>
          <ol className="space-y-1">
            {context_spec.next_steps.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm text-slate-400">
                <span className="text-blue-400 font-mono text-[12px] mt-0.5 flex-shrink-0">
                  {idx + 1}.
                </span>
                {item}
              </li>
            ))}
          </ol>
        </Section>
      )}
    </div>
  );
}

function ReverseContextTab({ reverseContext }) {
  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      {reverseContext.summary && (
        <Section title="역분석 요약" icon={<Lightbulb size={12} />}>
          <p className="text-[14px] text-slate-300 leading-relaxed">
            {reverseContext.summary}
          </p>
        </Section>
      )}

      {reverseContext.architecture_highlights?.length > 0 && (
        <Section title="구조 하이라이트" icon={<Layers size={12} />}>
          <ul className="space-y-1">
            {reverseContext.architecture_highlights.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-[15px] text-slate-400">
                <Layers size={10} className="text-blue-400 mt-0.5 flex-shrink-0" />
                {item}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {reverseContext.tech_stack_observations?.length > 0 && (
        <Section title="관측된 기술 스택" icon={<Tag size={12} />}>
          <div className="flex flex-wrap gap-1.5">
            {reverseContext.tech_stack_observations.map((item, idx) => (
              <span
                key={idx}
                className="px-2 py-0.5 rounded bg-blue-600/10 text-blue-300 text-[12px]"
              >
                {item}
              </span>
            ))}
          </div>
        </Section>
      )}

      {reverseContext.dependency_observations?.length > 0 && (
        <Section title="의존성 관찰" icon={<GitBranch size={12} />}>
          <ul className="space-y-1">
            {reverseContext.dependency_observations.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-[15px] text-slate-400">
                <GitBranch size={10} className="text-teal-400 mt-0.5 flex-shrink-0" />
                {item}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {reverseContext.risk_factors?.length > 0 && (
        <Section title="리스크 요인" icon={<AlertTriangle size={12} />}>
          <ul className="space-y-1">
            {reverseContext.risk_factors.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm text-slate-400">
                <Shield size={10} className="text-red-400 mt-0.5 flex-shrink-0" />
                {item}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {reverseContext.next_steps?.length > 0 && (
        <Section title="다음 검증 단계" icon={<ArrowRight size={12} />}>
          <ol className="space-y-1">
            {reverseContext.next_steps.map((item, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm text-slate-400">
                <span className="text-blue-400 font-mono text-[12px] mt-0.5 flex-shrink-0">
                  {idx + 1}.
                </span>
                {item}
              </li>
            ))}
          </ol>
        </Section>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════
//  SA Tabs
// ═══════════════════════════════════════════

function SAOverviewTab() {
  const { metadata, sa_output, sa_phase1, sa_phase2, sa_phase3, sa_phase4, sa_phase5, sa_phase6, sa_phase7, sa_phase8 } = useAppStore();

  if (!sa_output && !sa_phase1 && !sa_phase8) {
    return <EmptyState text="SA 결과가 없습니다" />;
  }

  const phases = [
    { id: "SA-01", label: "코드 구조 분석", phase: sa_phase1 },
    { id: "SA-02", label: "영향도 분석", phase: sa_phase2 },
    { id: "SA-03", label: "기술 타당성", phase: sa_phase3 },
    { id: "SA-04", label: "의존성 샌드박스", phase: sa_phase4 },
    { id: "SA-05", label: "아키텍처 매핑", phase: sa_phase5 },
    { id: "SA-06", label: "보안 경계", phase: sa_phase6 },
    { id: "SA-07", label: "인터페이스 계약", phase: sa_phase7 },
    { id: "SA-08", label: "위상 정렬", phase: sa_phase8 },
  ];

  const passCount = phases.filter((p) => p.phase?.status === "Pass").length;

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      {/* 헤더 */}
      <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700/50">
        <h3 className="text-sm font-semibold text-slate-200 mb-2">
          {metadata?.project_name || "프로젝트"} — SA 통합 결과
        </h3>
        <div className="flex items-center gap-3 text-[12px]">
          <span className="px-2 py-0.5 rounded bg-blue-600/20 text-blue-300">
            {metadata?.action_type || "ANALYSIS"}
          </span>
          <span className="text-slate-500">8단계 구조 분석 파이프라인</span>
          <span className={`px-2 py-0.5 rounded text-[12px] ${passCount === 8 ? "bg-green-600/20 text-green-300" : "bg-yellow-600/20 text-yellow-300"}`}>
            {passCount}/8 Pass
          </span>
        </div>
      </div>

      {/* SA Phase 1 통계 */}
      {sa_phase1 && (
        <div className="grid grid-cols-3 gap-3">
          <StatCard label="스캔 파일" value={sa_phase1.scanned_files ?? 0} color="text-blue-300" />
          <StatCard label="스캔 함수" value={sa_phase1.scanned_functions ?? 0} color="text-purple-300" />
          <StatCard
            label="언어 수"
            value={Object.keys(sa_phase1.languages || {}).length}
            color="text-teal-300"
          />
        </div>
      )}

      {/* 8단계 그리드 */}
      <div className="grid grid-cols-2 gap-2">
        {phases.map(({ id, label, phase }) => (
          <div key={id} className="bg-slate-900/50 rounded-lg p-3 border border-slate-700/50 flex items-center gap-3">
            <span className="text-[11px] font-mono text-slate-500 w-10 flex-shrink-0">{id}</span>
            <span className="text-[13px] text-slate-300 flex-1 truncate">{label}</span>
            <StatusBadge status={phase?.status || "Needs_Clarification"} />
          </div>
        ))}
      </div>

      {/* 언어 분포 (sa_phase1) */}
      {sa_phase1?.languages && Object.keys(sa_phase1.languages).length > 0 && (
        <Section title="언어 분포" icon={<Cpu size={12} />}>
          <div className="flex flex-wrap gap-2">
            {Object.entries(sa_phase1.languages).map(([lang, cnt]) => (
              <span key={lang} className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[12px]">
                {lang} <span className="text-slate-500">{cnt}</span>
              </span>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

function SAArchitectureTab() {
  const { sa_phase5, sa_phase7, activateOutputTab } = useAppStore();
  if (!sa_phase5 && !sa_phase7) {
    return <EmptyState text="아키텍처 결과가 없습니다" />;
  }

  const [selectedLayer, setSelectedLayer] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");

  const layerMeta = {
    presentation: {
      label: "Presentation",
      chip: "bg-blue-600/20 text-blue-300",
      panel: "border-blue-800/40 bg-blue-950/10",
    },
    application: {
      label: "Application",
      chip: "bg-purple-600/20 text-purple-300",
      panel: "border-purple-800/40 bg-purple-950/10",
    },
    domain: {
      label: "Domain",
      chip: "bg-teal-600/20 text-teal-300",
      panel: "border-teal-800/40 bg-teal-950/10",
    },
    infrastructure: {
      label: "Infrastructure",
      chip: "bg-orange-600/20 text-orange-300",
      panel: "border-orange-800/40 bg-orange-950/10",
    },
    security: {
      label: "Security",
      chip: "bg-red-600/20 text-red-300",
      panel: "border-red-800/40 bg-red-950/10",
    },
    unknown: {
      label: "Unclassified",
      chip: "bg-slate-700 text-slate-300",
      panel: "border-slate-700/70 bg-slate-900/40",
    },
  };

  const normalizeLayer = (rawLayer) => {
    const key = String(rawLayer || "").trim().toLowerCase();
    if (!key) return "application";
    if (key.includes("present")) return "presentation";
    if (key.includes("app")) return "application";
    if (key.includes("domain") || key.includes("business")) return "domain";
    if (key.includes("infra") || key.includes("data") || key.includes("storage")) return "infrastructure";
    if (key.includes("security") || key.includes("auth")) return "security";
    if (layerMeta[key]) return key;
    return "unknown";
  };

  const grouped = useMemo(() => {
    const map = {};
    for (const req of sa_phase5?.mapped_requirements || []) {
      const layer = normalizeLayer(req.layer);
      if (!map[layer]) map[layer] = [];
      map[layer].push(req);
    }
    return map;
  }, [sa_phase5?.mapped_requirements]);

  const layerOrder = useMemo(() => {
    const defaults = ["presentation", "application", "domain", "infrastructure", "security"];
    const fromModel = (sa_phase5?.layer_order || []).map((layer) => normalizeLayer(layer));
    const combined = [...fromModel, ...defaults];
    return combined.filter((layer, idx) => combined.indexOf(layer) === idx);
  }, [sa_phase5?.layer_order]);

  const contracts = useMemo(
    () =>
      (sa_phase7?.interface_contracts || []).map((contract) => ({
        ...contract,
        normalizedLayer: normalizeLayer(contract.layer),
      })),
    [sa_phase7?.interface_contracts]
  );

  const filteredContracts = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    return contracts.filter((contract) => {
      if (selectedLayer !== "all" && contract.normalizedLayer !== selectedLayer) return false;
      if (!q) return true;
      const haystack = [
        contract.contract_id,
        contract.layer,
        contract.input_spec,
        contract.output_spec,
        contract.req_id,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [contracts, searchTerm, selectedLayer]);

  const totalMappedRequirements = (sa_phase5?.mapped_requirements || []).length;
  const activeLayerCount = Object.keys(grouped).filter(
    (layer) => (grouped[layer] || []).length > 0
  ).length;
  const guardrailCount = (sa_phase7?.guardrails || []).length;
  const toCompactModuleLabel = (text) => {
    const raw = String(text || "").trim();
    if (!raw) return "설명 없음";
    return raw
      .replace(/^핵심\s*분석\s*모듈\s*:\s*/i, "")
      .replace(/^핵심\s*모듈\s*:\s*/i, "")
      .replace(/^분석\s*모듈\s*:\s*/i, "");
  };
  const reqFunctionNameMap = useMemo(() => {
    const map = {};
    for (const req of sa_phase5?.mapped_requirements || []) {
      const reqId = req?.REQ_ID || req?.req_id;
      if (!reqId) continue;
      const functionName = String(
        req?.functional_name || req?.label || toCompactModuleLabel(req?.description) || req?.name || ""
      ).trim();
      if (functionName) {
        map[reqId] = functionName;
      }
    }
    return map;
  }, [sa_phase5?.mapped_requirements]);
  const toHumanReadableTitle = (contract) => {
    const source = String(contract?.interface_name || contract?.description || "").trim();
    if (source) {
      const normalized = source
        .replace(/^IF[-_]/i, "")
        .replace(/[._-]+/g, " ")
        .replace(/\s+/g, " ")
        .trim();

      const lower = normalized.toLowerCase();

      const phraseRules = [
        { test: /(init|initialize|bootstrap).*(analysis|scan)/, value: "프로젝트 분석 초기화" },
        { test: /(render|display).*(result|output)/, value: "분석 결과 렌더링" },
        { test: /(collect|gather).*(metric|log)/, value: "메트릭 수집" },
        { test: /(update|set).*(state|store|ui)/, value: "상태 업데이트" },
        { test: /(start|create).*(session)/, value: "세션 시작" },
        { test: /(load|fetch|get).*(project|data|result)/, value: "데이터 조회" },
        { test: /(save|persist|write).*(result|state|session)/, value: "결과 저장" },
        { test: /(validate|check).*(input|request|schema)/, value: "입력 검증" },
      ];

      for (const rule of phraseRules) {
        if (rule.test.test(lower)) return rule.value;
      }

      const wordMap = {
        init: "초기화",
        initialize: "초기화",
        analysis: "분석",
        analyze: "분석",
        project: "프로젝트",
        session: "세션",
        result: "결과",
        results: "결과",
        output: "출력",
        input: "입력",
        render: "렌더링",
        update: "업데이트",
        state: "상태",
        fetch: "조회",
        load: "불러오기",
        save: "저장",
        collect: "수집",
        metric: "메트릭",
        metrics: "메트릭",
        log: "로그",
        logs: "로그",
        api: "API",
        event: "이벤트",
        queue: "큐",
        pipeline: "파이프라인",
        context: "컨텍스트",
        contract: "계약",
        module: "모듈",
      };

      const translated = normalized
        .split(" ")
        .map((token) => {
          const key = token.toLowerCase();
          return wordMap[key] || "";
        })
        .filter(Boolean)
        .join(" ")
        .trim();

      if (translated) return translated;
    }
    if (contract?.req_id) return `${contract.req_id} 처리 인터페이스`;
    return "모듈 인터페이스";
  };
  const inferCommType = (contract) => {
    const corpus = [
      contract?.interface_name,
      contract?.input_spec,
      contract?.output_spec,
      contract?.layer,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    if (/(api|rest|http|endpoint|request|response|fetch)/.test(corpus)) {
      return { label: "API", tone: "bg-cyan-600/20 text-cyan-300 border-cyan-800/40" };
    }
    if (/(ui|render|view|component|state|store|screen)/.test(corpus)) {
      return { label: "UI", tone: "bg-fuchsia-600/20 text-fuchsia-300 border-fuchsia-800/40" };
    }
    if (/(event|queue|topic|stream|metric|log|emit|publish|subscribe)/.test(corpus)) {
      return { label: "Event", tone: "bg-amber-600/20 text-amber-300 border-amber-800/40" };
    }
    return { label: "Internal", tone: "bg-slate-700/40 text-slate-300 border-slate-700/60" };
  };
  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      {sa_phase5 && (
        <Section title="아키텍처 매핑" icon={<Layers size={12} />}>
          <div className="flex items-center gap-2 mb-3 flex-wrap">
            <span className="text-[13px] text-slate-400">패턴</span>
            <span className="px-2 py-0.5 rounded bg-blue-600/20 text-blue-300 text-[13px]">{sa_phase5.pattern || "Clean Architecture"}</span>
            <StatusBadge status={sa_phase5.status || "Needs_Clarification"} />
            <button
              type="button"
              onClick={() => activateOutputTab("sa_system")}
              className="ml-auto text-[12px] px-2 py-1 rounded border border-slate-700 text-slate-300 hover:bg-slate-800"
            >
              시스템 다이어그램 보기
            </button>
            <button
              type="button"
              onClick={() => activateOutputTab("sa_uml")}
              className="text-[12px] px-2 py-1 rounded border border-slate-700 text-slate-300 hover:bg-slate-800"
            >
              UML 보기
            </button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
            <StatCard label="매핑 요구사항" value={totalMappedRequirements} color="text-blue-300" />
            <StatCard label="활성 레이어" value={activeLayerCount} color="text-teal-300" />
            <StatCard label="인터페이스 계약" value={contracts.length} color="text-purple-300" />
            <StatCard label="가드레일" value={guardrailCount} color="text-red-300" />
          </div>

          <div className="mb-2 text-[13px] text-slate-500">레이어 보드</div>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
            {layerOrder.map((layer) => {
              const reqs = grouped[layer] || [];
              const meta = layerMeta[layer] || layerMeta.unknown;
              const isSelected = selectedLayer === layer;
              return (
                <button
                  type="button"
                  key={layer}
                  onClick={() => setSelectedLayer(isSelected ? "all" : layer)}
                  className={`flex flex-col justify-start items-stretch text-left rounded-lg border p-3 min-h-[156px] align-top transition ${meta.panel} ${isSelected ? "ring-1 ring-slate-400" : "hover:bg-slate-800/40"}`}
                >
                  <div className="w-full self-start space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className={`px-2 py-0.5 rounded text-[12px] font-medium ${meta.chip}`}>{meta.label}</span>
                      <span className="text-[12px] text-slate-500">{reqs.length}개</span>
                    </div>
                    {reqs.length > 0 ? (
                      <div className="space-y-1">
                        {reqs.slice(0, 3).map((req) => (
                          <div key={req.REQ_ID} className="text-[13px] text-slate-300 leading-snug break-words">
                            <span className="text-slate-300">{reqFunctionNameMap[req.REQ_ID] || toCompactModuleLabel(req.description)}</span>
                            <span className="text-slate-500 font-mono ml-1">({req.REQ_ID})</span>
                          </div>
                        ))}
                        {reqs.length > 3 && (
                          <div className="text-[12px] text-slate-500">+{reqs.length - 3}개 더 있음</div>
                        )}
                      </div>
                    ) : (
                      <div className="text-[13px] text-slate-600">매핑된 요구사항 없음</div>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </Section>
      )}

      {sa_phase7 && (
        <Section title="인터페이스 계약 탐색" icon={<GitBranch size={12} />}>
          <div className="mb-2 flex items-center gap-2 flex-wrap">
            <StatusBadge status={sa_phase7.status || "Needs_Clarification"} />
            <span className="text-[13px] text-slate-500">총 {contracts.length}개 계약</span>
            {selectedLayer !== "all" && (
              <span className="text-[12px] px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                레이어 필터: {(layerMeta[selectedLayer] || layerMeta.unknown).label}
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-3">
            <input
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="계약 ID, 입력/출력, REQ_ID 검색"
              className="md:col-span-2 bg-slate-900 border border-slate-700 rounded px-2 py-1.5 text-[13px] text-slate-200 placeholder:text-slate-500"
            />
            <select
              value={selectedLayer}
              onChange={(e) => setSelectedLayer(e.target.value)}
              className="bg-slate-900 border border-slate-700 rounded px-2 py-1.5 text-[13px] text-slate-200"
            >
              <option value="all">전체 레이어</option>
              {layerOrder.map((layer) => (
                <option key={layer} value={layer}>
                  {(layerMeta[layer] || layerMeta.unknown).label}
                </option>
              ))}
              <option value="unknown">Unclassified</option>
            </select>
          </div>

          {(sa_phase7.guardrails || []).length > 0 && (
            <div className="mb-3">
              <div className="text-[12px] text-slate-500 mb-1.5 uppercase tracking-wider">Guardrails</div>
              <ul className="space-y-1">
                {sa_phase7.guardrails.map((g, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-[13px] text-slate-400">
                    <Shield size={10} className="text-red-400 mt-0.5 flex-shrink-0" />
                    {g}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {filteredContracts.length > 0 ? (
            <div className="space-y-2">
              {filteredContracts.slice(0, 40).map((c, idx) => {
                const commType = inferCommType(c);
                const title = toHumanReadableTitle(c);
                const reqLabel = reqFunctionNameMap[c.req_id] || c.req_id || c.contract_id || `ROW-${idx + 1}`;
                const layerLabel = (layerMeta[c.normalizedLayer] || layerMeta.unknown).label;
                return (
                  <div key={idx} className="rounded-lg border border-slate-700/70 bg-slate-900/40 p-3">
                    <div className="flex items-start gap-2 mb-2 flex-wrap">
                      <span className={`px-2 py-0.5 rounded border text-[12px] font-medium ${commType.tone}`}>
                        {commType.label}
                      </span>
                      <h5 className="text-[15px] font-semibold text-slate-200 leading-tight">
                        {title} <span className="text-slate-400">({reqLabel})</span>
                      </h5>
                      <span className={`ml-auto px-1.5 py-0.5 rounded text-[12px] ${(layerMeta[c.normalizedLayer] || layerMeta.unknown).chip}`}>
                        {layerLabel}
                      </span>
                    </div>

                    <div className="text-[12px] text-slate-500 mb-2">
                      원본 ID: {c.contract_id || "NO-ID"}
                      <span className={`ml-2 ${c.req_id ? "text-slate-500" : "text-slate-700"}`}>REQ: {c.req_id || "-"}</span>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto_1fr] gap-2 items-center">
                      <div className="rounded border border-slate-700 bg-slate-800/60 p-2">
                        <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Input</div>
                        <div className={`font-mono text-[12px] leading-relaxed break-words ${c.input_spec ? "text-slate-200" : "text-slate-600"}`}>
                          {c.input_spec || "-"}
                        </div>
                      </div>

                      <div className="flex justify-center text-slate-500">
                        <ArrowRight size={14} />
                      </div>

                      <div className="rounded border border-slate-700 bg-slate-800/60 p-2">
                        <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Output</div>
                        <div className={`font-mono text-[12px] leading-relaxed break-words ${c.output_spec ? "text-slate-200" : "text-slate-600"}`}>
                          {c.output_spec || "-"}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}

              {filteredContracts.length > 40 && (
                <p className="text-[12px] text-slate-600 text-right">+{filteredContracts.length - 40}개 더 있음</p>
              )}
            </div>
          ) : (
            <div className="text-[13px] text-slate-500 border border-slate-800 rounded p-3">
              현재 필터 조건에 맞는 인터페이스 계약이 없습니다.
            </div>
          )}
        </Section>
      )}
    </div>
  );
}

function SASecurityTab() {
  const { sa_phase5, sa_phase6, sa_phase7 } = useAppStore();
  if (!sa_phase6) {
    return <EmptyState text="보안 경계 결과가 없습니다" />;
  }

  const toCompactModuleLabel = (text) => {
    const raw = String(text || "").trim();
    if (!raw) return "기능명 없음";
    return raw
      .replace(/^핵심\s*분석\s*모듈\s*:\s*/i, "")
      .replace(/^핵심\s*모듈\s*:\s*/i, "")
      .replace(/^분석\s*모듈\s*:\s*/i, "");
  };

  const extractFileRoot = (...texts) => {
    const joined = texts.filter(Boolean).join(" ").replace(/\\/g, "/");
    const match = joined.match(/((?:src|backend|electron|pipeline|components|store)\/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+)/i);
    return match ? match[1] : "-";
  };

  const toKoreanFunctionName = (rawName) => {
    const normalized = String(rawName || "")
      .replace(/^IF[-_]/i, "")
      .replace(/[._-]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    const lower = normalized.toLowerCase();

    const rules = [
      { test: /(init|initialize|bootstrap).*(analysis|scan)/, value: "프로젝트 분석 초기화" },
      { test: /(render|display).*(result|output)/, value: "분석 결과 렌더링" },
      { test: /(collect|gather).*(metric|log)/, value: "메트릭 수집" },
      { test: /(start|create).*(session)/, value: "세션 시작" },
      { test: /(fetch|load|get).*(project|data|result)/, value: "데이터 조회" },
      { test: /(save|persist|write).*(result|state|session)/, value: "결과 저장" },
      { test: /(validate|check).*(input|request|schema)/, value: "입력 검증" },
    ];
    for (const rule of rules) {
      if (rule.test.test(lower)) return rule.value;
    }
    return normalized || "모듈 기능";
  };

  const isLikelyFilePath = (text) => {
    const value = String(text || "").trim();
    if (!value) return false;
    if (/^(src|backend|electron|pipeline|components|store)\//i.test(value.replace(/\\/g, "/"))) return true;
    if (/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+/.test(value) && /[\\/]/.test(value)) return true;
    return false;
  };

  const reqTitleMap = {};
  const reqFileRootMap = {};
  for (const contract of sa_phase7?.interface_contracts || []) {
    const reqId = contract?.req_id || contract?.REQ_ID;
    if (!reqId || reqId === "-") continue;
    const titleCandidate = toKoreanFunctionName(contract?.interface_name || contract?.contract_id);
    if (titleCandidate && titleCandidate !== "모듈 기능") {
      reqTitleMap[reqId] = titleCandidate;
    }
    if (!reqFileRootMap[reqId] || reqFileRootMap[reqId] === "-") {
      reqFileRootMap[reqId] = extractFileRoot(contract?.input_spec, contract?.output_spec);
    }
  }

  for (const req of sa_phase5?.mapped_requirements || []) {
    const reqId = req?.REQ_ID || req?.req_id;
    if (!reqId) continue;
    const compact = String(req?.functional_name || req?.label || toCompactModuleLabel(req?.description) || "").trim();
    if (!reqTitleMap[reqId] && compact && !isLikelyFilePath(compact) && compact !== "기능명 없음") {
      reqTitleMap[reqId] = compact;
    }
    reqFileRootMap[reqId] = extractFileRoot(req?.description, req?.mapping_reason, req?.layer_evidence);
  }

  const getBoundaryVisual = (boundary) => {
    const corpus = [boundary?.boundary_name, boundary?.crossing_data]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    if (/(client|web|electron|browser|ui)/.test(corpus)) {
      return { emoji: "🌐" };
    }
    if (/(llm|openai|gemini|model|ai)/.test(corpus)) {
      return { emoji: "🤖" };
    }
    if (/(chroma|vector|database|db|sqlite)/.test(corpus)) {
      return { emoji: "🗄️" };
    }
    if (/(device|local|desktop|on-device|on device)/.test(corpus)) {
      return { emoji: "💻" };
    }
    return { emoji: "🛡️" };
  };
  const normalizedRoles = ((sa_phase6.defined_roles || sa_phase6.rbac_roles || [])
    .map((role, idx) => {
      if (typeof role === "string") {
        return { role_name: role, description: "" };
      }
      return {
        role_name: role?.role_name || role?.name || `Role-${idx + 1}`,
        description: role?.description || "",
      };
    })
    .filter((role) => role.role_name));

  const normalizedBoundaries = ((sa_phase6.trust_boundaries || [])
    .map((boundary, idx) => {
      if (typeof boundary === "string") {
        return {
          boundary_name: boundary,
          crossing_data: "",
          security_controls: "",
        };
      }
      return {
        boundary_name: boundary?.boundary_name || boundary?.name || `Boundary-${idx + 1}`,
        crossing_data: boundary?.crossing_data || "",
        security_controls: boundary?.security_controls || boundary?.controls || "",
      };
    })
    .filter((boundary) => boundary.boundary_name));

  const normalizedAuthz = ((sa_phase6.authz_matrix || [])
    .map((row) => ({
      req_id: row?.req_id || row?.REQ_ID || "-",
      allowed_roles: Array.isArray(row?.allowed_roles)
        ? row.allowed_roles
        : row?.role
        ? [row.role]
        : [],
      restriction_level: row?.restriction_level || row?.access || "-",
    })));

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      <Section title="보안 경계" icon={<Shield size={12} />}>
        <div className="flex items-center gap-2 mb-3">
          <StatusBadge status={sa_phase6.status || "Needs_Clarification"} />
        </div>

        {/* RBAC 역할 */}
        {normalizedRoles.length > 0 && (
          <div className="mb-3">
            <div className="text-[11px] text-slate-500 mb-1.5 uppercase tracking-wider">RBAC 역할</div>
            <div className="flex flex-wrap gap-2">
              {normalizedRoles.map((role) => (
                <span key={role.role_name} className="px-2.5 py-1 rounded-full bg-red-600/15 text-red-300 text-[12px] border border-red-800/30">
                  {role.role_name}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Trust Boundaries */}
        {normalizedBoundaries.length > 0 && (
          <div className="mb-3">
            <div className="text-[11px] text-slate-500 mb-1.5 uppercase tracking-wider">Trust Boundaries</div>
            <div className="space-y-1.5">
              {normalizedBoundaries.map((boundary, idx) => {
                const visual = getBoundaryVisual(boundary);
                return (
                  <div key={idx} className="rounded border border-slate-800/70 bg-slate-900/30 p-2">
                    <div className="flex items-center gap-1 text-[12px]">
                      <span className="text-[14px]" aria-hidden="true">{visual.emoji}</span>
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">{boundary.boundary_name}</span>
                    </div>
                    {boundary.crossing_data && (
                      <div className="mt-1 text-[12px] text-slate-400">
                        데이터: {boundary.crossing_data}
                      </div>
                    )}
                    {boundary.security_controls && (
                      <div className="mt-1 text-[12px] text-slate-500">
                        통제: {boundary.security_controls}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* authz_matrix 요약 */}
        {normalizedAuthz.length > 0 && (
          <div>
            <div className="text-[11px] text-slate-500 mb-1.5 uppercase tracking-wider">
              권한 매트릭스 ({normalizedAuthz.length}개)
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="border-b border-slate-700">
                    <th className="text-left py-1 px-1 text-slate-500 font-medium">요구사항</th>
                    <th className="text-left py-1 px-1 text-slate-500 font-medium">Roles</th>
                    <th className="text-left py-1 px-1 text-slate-500 font-medium">Restriction</th>
                  </tr>
                </thead>
                <tbody>
                  {normalizedAuthz.slice(0, 16).map((row, idx) => {
                    const fileRoot = reqFileRootMap[row.req_id] || "-";
                    const functionName = reqTitleMap[row.req_id] || "";
                    const primaryLabel = functionName || fileRoot;
                    return (
                    <tr key={idx} className="border-b border-slate-800/50">
                      <td className="py-1 px-1">
                        <div className="text-slate-200 font-medium truncate">
                          {primaryLabel} <span className="text-slate-400">({row.req_id || "-"})</span>
                        </div>
                      </td>
                      <td className="py-1 px-1">
                        {row.allowed_roles.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {row.allowed_roles.map((role, roleIdx) => (
                              <span
                                key={`${role}-${roleIdx}`}
                                className="px-2 py-0.5 rounded-full bg-red-600/15 text-red-300 text-[11px] border border-red-800/30"
                              >
                                {role}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="text-slate-600">-</span>
                        )}
                      </td>
                      <td className="py-1 px-1">
                        <span className={`px-1.5 py-0.5 rounded text-[11px] ${row.restriction_level === "Authorized" || row.restriction_level === "InternalOnly" ? "bg-orange-600/20 text-orange-300" : "bg-slate-700 text-slate-400"}`}>
                          {row.restriction_level}
                        </span>
                      </td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
              {normalizedAuthz.length > 16 && (
                <p className="text-[11px] text-slate-600 mt-1 text-right">
                  +{normalizedAuthz.length - 16}개 더 있음
                </p>
              )}
            </div>
          </div>
        )}
      </Section>
    </div>
  );
}

function SATopologyTab() {
  const { sa_phase5, sa_phase8 } = useAppStore();
  if (!sa_phase8) {
    return <EmptyState text="위상 정렬 결과가 없습니다" />;
  }

  const [selectedCycle, setSelectedCycle] = useState("");
  const queue = sa_phase8.topo_queue || [];
  const cycles = sa_phase8.cyclic_requirements || [];
  const batches = sa_phase8.parallel_batches || [];
  const dependencySources = sa_phase8.dependency_sources || {};

  const reqMeta = useMemo(() => {
    const map = {};
    for (const item of sa_phase5?.mapped_requirements || []) {
      const reqId = item?.REQ_ID || item?.req_id;
      if (!reqId) continue;
      const description = String(item?.description || "")
        .replace(/^핵심\s*분석\s*모듈\s*:\s*/i, "")
        .replace(/^핵심\s*모듈\s*:\s*/i, "")
        .replace(/^분석\s*모듈\s*:\s*/i, "")
        .trim();
      map[reqId] = {
        name: description || "모듈 기능",
        layer: item?.layer || "unknown",
      };
    }
    return map;
  }, [sa_phase5?.mapped_requirements]);

  const orderIndex = useMemo(() => {
    const map = {};
    queue.forEach((rid, idx) => {
      map[rid] = idx + 1;
    });
    return map;
  }, [queue]);

  const layerLabel = (layer) => {
    const key = String(layer || "").toLowerCase();
    if (key.includes("present")) return "Presentation";
    if (key.includes("app")) return "Application";
    if (key.includes("domain") || key.includes("business")) return "Domain";
    if (key.includes("infra") || key.includes("data")) return "Infrastructure";
    if (key.includes("security") || key.includes("auth")) return "Security";
    return "Unknown";
  };

  const layerTone = (layer) => {
    const key = String(layer || "").toLowerCase();
    if (key.includes("present")) return "bg-blue-600/20 text-blue-300";
    if (key.includes("app")) return "bg-purple-600/20 text-purple-300";
    if (key.includes("domain") || key.includes("business")) return "bg-teal-600/20 text-teal-300";
    if (key.includes("infra") || key.includes("data")) return "bg-orange-600/20 text-orange-300";
    if (key.includes("security") || key.includes("auth")) return "bg-red-600/20 text-red-300";
    return "bg-slate-700 text-slate-300";
  };

  const cyclePathMap = useMemo(() => {
    const cyclicSet = new Set(cycles);
    const adjacency = {};
    Object.keys(dependencySources).forEach((target) => {
      const deps = (dependencySources[target] || [])
        .map((src) => src?.from)
        .filter((from) => from && cyclicSet.has(from));
      adjacency[target] = [...new Set(deps)];
    });

    const findPath = (start) => {
      const stack = [[start, [start]]];
      while (stack.length > 0) {
        const [node, path] = stack.pop();
        const nexts = adjacency[node] || [];
        for (const next of nexts) {
          if (next === start && path.length > 1) {
            return [...path, start];
          }
          if (!path.includes(next) && path.length < 8) {
            stack.push([next, [...path, next]]);
          }
        }
      }
      return [];
    };

    const map = {};
    cycles.forEach((rid) => {
      const path = findPath(rid);
      map[rid] = path.length > 0 ? path.join(" ➔ ") : "경로 정보 없음";
    });
    return map;
  }, [cycles, dependencySources]);

  const phaseGroups = useMemo(() => {
    if (batches.length > 0) {
      return batches.map((batch, idx) => ({
        phaseNo: idx + 1,
        title: idx === 0 ? "종속성 없음 (독립 개발 가능)" : `Phase ${idx} 의존`,
        items: batch,
      }));
    }
    if (queue.length === 0) return [];
    return [
      {
        phaseNo: 1,
        title: "순차 실행",
        items: queue,
      },
    ];
  }, [batches, queue]);

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      {/* 상태 요약 */}
      <div className="bg-slate-900/50 rounded-lg p-3 border border-slate-700/50 flex items-center gap-3">
        <StatusBadge status={sa_phase8.status || "Needs_Clarification"} />
        <span className="text-[12px] text-slate-500">
          실행 순서 {queue.length}개
          {cycles.length > 0 && ` · 순환 의존성 ${cycles.length}개`}
        </span>
      </div>

      {/* 순환 의존성 경고 */}
      {cycles.length > 0 && (
        <Section title="순환 의존성 경고" icon={<AlertTriangle size={12} />}>
          <div className="flex flex-wrap gap-2">
            {cycles.map((rid) => (
              <button
                key={rid}
                type="button"
                title={cyclePathMap[rid] || "경로 정보 없음"}
                onClick={() => setSelectedCycle((prev) => (prev === rid ? "" : rid))}
                className="px-2 py-0.5 rounded bg-red-600/20 text-red-300 text-[12px] border border-red-800/30 hover:bg-red-600/30"
              >
                {rid}
              </button>
            ))}
          </div>
          {selectedCycle && (
            <div className="mt-2 rounded border border-red-900/40 bg-red-950/20 p-2 text-[12px] text-red-200">
              {cyclePathMap[selectedCycle] || "경로 정보 없음"}
            </div>
          )}
          <p className="text-[11px] text-slate-600 mt-2">
            순환 의존성이 있는 요구사항은 위상 정렬에서 제외됩니다. 의존성을 재검토하세요.
          </p>
        </Section>
      )}

      {/* 실행 그룹 (Phase) */}
      {phaseGroups.length > 0 && (
        <Section title="실행 그룹 (Topology Queue)" icon={<GitBranch size={12} />}>
          <div className="space-y-3">
            {phaseGroups.map((group) => (
              <div key={group.phaseNo} className="rounded-lg border border-slate-700/70 bg-slate-900/30 p-3">
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <span className="px-2 py-0.5 rounded bg-blue-600/20 text-blue-300 text-[12px]">Phase {group.phaseNo}</span>
                  <span className="text-[12px] text-slate-500">{group.title}</span>
                  <span className="ml-auto text-[11px] text-slate-600">{group.items.length}개 모듈</span>
                </div>

                <div className="space-y-1.5">
                  {group.items.map((rid) => {
                    const meta = reqMeta[rid] || { name: "모듈 기능", layer: "unknown" };
                    const seq = orderIndex[rid] || "-";
                    return (
                      <div key={`${group.phaseNo}-${rid}`} className="flex items-center gap-2">
                        <span className="text-[11px] font-mono text-slate-600 w-8 text-right flex-shrink-0">{seq}</span>
                        <span className="text-[12px] text-blue-300 font-mono flex-shrink-0">{rid}</span>
                        <span className="text-[13px] text-slate-200 truncate">{meta.name}</span>
                        <span className={`ml-auto px-1.5 py-0.5 rounded text-[11px] ${layerTone(meta.layer)}`}>
                          {layerLabel(meta.layer)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

function SASystemDiagramTab() {
  const { sa_artifacts } = useAppStore();
  const containerSpec = sa_artifacts?.container_diagram_spec;

  if (!containerSpec) {
    return <EmptyState text="시스템 다이어그램 산출물이 없습니다" />;
  }
  const ctnSummary = containerSpec?.summary || {};
  const graph = normalizeContainerDiagramForGraph(containerSpec);

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      <Section title="시스템 아키텍처 요약" icon={<Layers size={12} />}>
        <div className="grid grid-cols-3 gap-3">
          <StatCard label="컴포넌트" value={ctnSummary.component_count ?? (containerSpec?.components || []).length} color="text-blue-300" />
          <StatCard label="외부 시스템" value={ctnSummary.external_count ?? (containerSpec?.external_systems || []).length} color="text-amber-300" />
          <StatCard label="연결" value={ctnSummary.connection_count ?? (containerSpec?.connections || []).length} color="text-teal-300" />
        </div>
      </Section>

      <div className="h-[620px] rounded-lg border border-slate-700/50 overflow-hidden">
        <SAArtifactGraph
          graph={graph}
          emptyText="시스템 아키텍처 데이터가 없습니다"
        />
      </div>
    </div>
  );
}
function SAFlowchartTab() {
  const { sa_artifacts, sa_phase5 } = useAppStore();
  const spec = sa_artifacts?.flowchart_spec;

  if (!spec) {
    return <EmptyState text="Flowchart 산출물이 없습니다" />;
  }

  const stages = spec.stages || [];
  const summary = spec.summary || {};
  const quality = spec.data_quality || {};
  const reqFunctionNameMap = useMemo(() => {
    const map = {};
    for (const req of sa_phase5?.mapped_requirements || []) {
      const reqId = req?.REQ_ID || req?.req_id;
      if (!reqId) continue;
      const functionName = String(
        req?.functional_name || req?.label || req?.description || req?.name || ""
      )
        .replace(/^핵심\s*분석\s*모듈\s*:\s*/i, "")
        .replace(/^핵심\s*모듈\s*:\s*/i, "")
        .replace(/^분석\s*모듈\s*:\s*/i, "")
        .trim();
      if (functionName) {
        map[reqId] = functionName;
      }
    }
    return map;
  }, [sa_phase5?.mapped_requirements]);

  const graphSpec = useMemo(
    () => ({
      ...spec,
      stages: stages.map((stage) => ({
        ...stage,
        function_names: (stage.req_ids || []).map((reqId) => reqFunctionNameMap[reqId] || reqId),
      })),
    }),
    [spec, stages, reqFunctionNameMap]
  );

  const graph = normalizeFlowchartForGraph(graphSpec);

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      <Section title="Flowchart 요약" icon={<GitBranch size={12} />}>
        <div className="grid grid-cols-3 gap-3">
          <StatCard label="Stage" value={summary.stage_count || stages.length} color="text-blue-300" />
          <StatCard label="Parallel" value={summary.parallel_stage_count || 0} color="text-purple-300" />
          <StatCard label="완전성" value={`${Math.round((quality.completeness || 0) * 100)}%`} color="text-teal-300" />
        </div>
      </Section>

      <Section title="단계별 흐름" icon={<Layers size={12} />}>
        <div className="h-[560px] rounded-lg border border-slate-700/50 overflow-hidden">
          <SAArtifactGraph graph={graph} emptyText="Flowchart 그래프 데이터가 없습니다" />
        </div>
      </Section>
    </div>
  );
}

function SAUMLComponentTab() {
  const { sa_artifacts } = useAppStore();
  const spec = sa_artifacts?.uml_component_spec;

  if (!spec) {
    return <EmptyState text="UML Component 산출물이 없습니다" />;
  }

  const components = spec.components || [];
  const interfaces = spec.provided_interfaces || [];
  const relations = spec.relations || [];
  const summary = spec.summary || {};
  const denseGraph = relations.length >= 600;
  const [expandedLayer, setExpandedLayer] = useState("");

  const graph = useMemo(
    () =>
      normalizeUMLForGraph(spec, {
        mode: expandedLayer ? "detail" : "cluster",
        layerFilter: expandedLayer || undefined,
        hideExecutionOrder: true,
        minConfidence: 0.25,
        showEdgeLabels: expandedLayer ? relations.length < 180 : true,
      }),
    [spec, expandedLayer, relations.length]
  );

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      <Section title="UML Component 요약" icon={<Cpu size={12} />}>
        <div className="grid grid-cols-3 gap-3">
          <StatCard label="Components" value={summary.component_count || components.length} color="text-blue-300" />
          <StatCard label="Interfaces" value={summary.interface_count || interfaces.length} color="text-purple-300" />
          <StatCard label="Relations" value={summary.relation_count || relations.length} color="text-teal-300" />
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-[12px] text-slate-500">보기 방식</span>
          <span className="text-[12px] px-2 py-1 rounded border border-blue-500 text-blue-300 bg-blue-500/10">
            {expandedLayer ? `${expandedLayer} 레이어 상세` : "클러스터(기본)"}
          </span>
          {expandedLayer && (
            <button
              type="button"
              onClick={() => setExpandedLayer("")}
              className="text-[12px] px-2 py-1 rounded border border-slate-700 text-slate-300 hover:bg-slate-800"
            >
              클러스터로 돌아가기
            </button>
          )}

          {denseGraph && (
            <span className="ml-auto text-[11px] text-slate-500">
              대규모 그래프 감지: 클러스터 우선 + 실행순서/저신뢰 엣지 숨김
            </span>
          )}
        </div>
      </Section>

      <Section title="컴포넌트" icon={<Layers size={12} />}>
        <div className="h-[560px] rounded-lg border border-slate-700/50 overflow-hidden">
          <SAArtifactGraph
            graph={graph}
            emptyText="UML 그래프 데이터가 없습니다"
            onNodeClick={(node) => {
              if (expandedLayer) return;
              const nodeId = String(node?.id || "");
              if (!nodeId.startsWith("cluster-")) return;
              setExpandedLayer(nodeId.replace(/^cluster-/, ""));
            }}
          />
        </div>
      </Section>
    </div>
  );
}

function SAInterfacesTab() {
  const { sa_artifacts, sa_phase5 } = useAppStore();
  const doc = sa_artifacts?.interface_definition_doc;

  if (!doc) {
    return <EmptyState text="인터페이스 정의서 산출물이 없습니다" />;
  }

  const contracts = doc.contracts || [];
  const guardrails = doc.guardrails || [];
  const quality = doc.data_quality || {};
  const [expandedContractId, setExpandedContractId] = useState("");

  const reqFunctionNameMap = useMemo(() => {
    const map = {};
    for (const req of sa_phase5?.mapped_requirements || []) {
      const reqId = req?.REQ_ID || req?.req_id;
      if (!reqId) continue;
      const functionName = String(
        req?.functional_name || req?.label || req?.description || req?.name || ""
      )
        .replace(/^핵심\s*분석\s*모듈\s*:\s*/i, "")
        .replace(/^핵심\s*모듈\s*:\s*/i, "")
        .replace(/^분석\s*모듈\s*:\s*/i, "")
        .trim();
      if (functionName) {
        map[reqId] = functionName;
      }
    }
    return map;
  }, [sa_phase5?.mapped_requirements]);

  const layerBadgeTone = (layer) => {
    const key = String(layer || "").toLowerCase();
    if (key.includes("present")) return "bg-blue-900/30 text-blue-300 border-blue-800/50";
    if (key.includes("app")) return "bg-violet-900/30 text-violet-300 border-violet-800/50";
    if (key.includes("domain")) return "bg-emerald-900/30 text-emerald-300 border-emerald-800/50";
    if (key.includes("infra") || key.includes("data")) return "bg-amber-900/30 text-amber-300 border-amber-800/50";
    if (key.includes("security") || key.includes("auth")) return "bg-rose-900/30 text-rose-300 border-rose-800/50";
    return "bg-slate-800/50 text-slate-300 border-slate-700/60";
  };

  const formatIoPreview = (specText, maxLength = 86) => {
    const raw = String(specText || "").trim();
    if (!raw) return "-";
    const compact = raw.replace(/\s+/g, " ");
    return compact.length > maxLength ? `${compact.slice(0, maxLength)}...` : compact;
  };

  const formatExpandedIo = (specText) => {
    const raw = String(specText || "").trim();
    if (!raw) return "-";
    try {
      return JSON.stringify(JSON.parse(raw), null, 2);
    } catch {
      return raw;
    }
  };

  const renderGuardrailText = (text) => {
    const pattern = /(상호\s*TLS\s*\(mTLS\)\s*암호화|최소\s*권한\s*원칙|익명화\s*및\s*토큰화|토큰\s*회전|비밀\s*관리|감사\s*로그|입력\s*검증|권한\s*검사)/gi;
    const chunks = String(text || "").split(pattern);
    return chunks.map((chunk, idx) => {
      if (!chunk) return null;
      const highlighted = pattern.test(chunk);
      pattern.lastIndex = 0;
      return highlighted ? (
        <span key={`${chunk}-${idx}`} className="font-semibold text-amber-300">{chunk}</span>
      ) : (
        <span key={`${chunk}-${idx}`}>{chunk}</span>
      );
    });
  };

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      <Section title="인터페이스 정의서" icon={<GitBranch size={12} />}>
        <div className="text-[12px] text-slate-500 mb-2">
          계약 {contracts.length}개 · 가드레일 {guardrails.length}개 · 완전성 {Math.round((quality.completeness || 0) * 100)}%
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-[12px] border-separate border-spacing-y-1">
            <thead>
              <tr className="border-b border-slate-700">
                <th className="text-left py-1 px-2 text-slate-500 font-medium">계약 ID</th>
                <th className="text-left py-1 px-2 text-slate-500 font-medium">레이어</th>
                <th className="text-left py-1 px-2 text-slate-500 font-medium">인터페이스</th>
                <th className="text-left py-1 px-2 text-slate-500 font-medium">Input</th>
                <th className="text-left py-1 px-2 text-slate-500 font-medium">Output</th>
                <th className="text-left py-1 px-2 text-slate-500 font-medium">상세</th>
              </tr>
            </thead>
            <tbody>
              {contracts.slice(0, 30).map((c, idx) => {
                const rowId = c.contract_id || `contract-${idx}`;
                const expanded = expandedContractId === rowId;
                const reqId = String(c.contract_id || "").startsWith("IF-")
                  ? String(c.contract_id).slice(3)
                  : String(c.contract_id || "");
                const contractLabel = reqFunctionNameMap[reqId] || c.interface_name || "-";
                return (
                  <React.Fragment key={rowId}>
                    <tr className="bg-slate-900/40 border border-slate-800/60">
                      <td className="py-2 px-2 align-top">
                        <div className="text-[13px] font-semibold text-slate-200 leading-snug">{contractLabel}</div>
                        <div className="mt-0.5 text-[11px] text-slate-500 font-mono">{c.contract_id || "-"}</div>
                      </td>
                      <td className="py-2 px-2 align-top">
                        <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${layerBadgeTone(c.layer)}`}>
                          {c.layer || "Unknown"}
                        </span>
                      </td>
                      <td className="py-2 px-2 align-top">
                        <div className="text-[13px] font-semibold text-slate-200 tracking-tight">{c.interface_name || "-"}</div>
                      </td>
                      <td className="py-2 px-2 align-top">
                        <div className="rounded-md bg-slate-800/30 px-2 py-1.5">
                          <code className="block max-w-[340px] truncate font-mono text-[11px] text-slate-400" title={c.input_spec || "-"}>
                            {formatIoPreview(c.input_spec)}
                          </code>
                        </div>
                      </td>
                      <td className="py-2 px-2 align-top">
                        <div className="rounded-md bg-slate-800/30 px-2 py-1.5">
                          <code className="block max-w-[360px] truncate font-mono text-[11px] text-slate-400" title={c.output_spec || "-"}>
                            {formatIoPreview(c.output_spec)}
                          </code>
                        </div>
                      </td>
                      <td className="py-2 px-2 align-top">
                        <button
                          type="button"
                          onClick={() => setExpandedContractId((prev) => (prev === rowId ? "" : rowId))}
                          className="text-[11px] px-2 py-1 rounded border border-slate-700 text-slate-300 hover:bg-slate-800"
                        >
                          {expanded ? "접기" : "펼치기"}
                        </button>
                      </td>
                    </tr>

                    {expanded && (
                      <tr className="bg-slate-950/40 border border-slate-800/60">
                        <td colSpan={6} className="px-2 pb-3 pt-1">
                          <div className="grid grid-cols-1 xl:grid-cols-2 gap-2">
                            <div className="rounded-md bg-slate-800/25 p-2">
                              <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Input (Full)</div>
                              <pre className="text-[11px] font-mono text-slate-300 whitespace-pre-wrap break-words leading-relaxed">
                                {formatExpandedIo(c.input_spec)}
                              </pre>
                            </div>
                            <div className="rounded-md bg-slate-800/25 p-2">
                              <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Output (Full)</div>
                              <pre className="text-[11px] font-mono text-slate-300 whitespace-pre-wrap break-words leading-relaxed">
                                {formatExpandedIo(c.output_spec)}
                              </pre>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </Section>

      {guardrails.length > 0 && (
        <Section title="Guardrails" icon={<Shield size={12} />}>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
            {guardrails.map((item, idx) => (
              <div key={idx} className="rounded-lg border border-slate-800/70 bg-slate-900/40 p-3">
                <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">Rule {idx + 1}</div>
                <p className="text-[13px] text-slate-300 leading-relaxed">{renderGuardrailText(item)}</p>
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

function SADecisionTableTab() {
  const { sa_artifacts, sa_phase5 } = useAppStore();
  const table = sa_artifacts?.decision_table;

  if (!table) {
    return <EmptyState text="Decision Table 산출물이 없습니다" />;
  }

  const rows = table.rows || [];
  const quality = table.data_quality || {};

  const reqFunctionNameMap = useMemo(() => {
    const map = {};
    for (const req of sa_phase5?.mapped_requirements || []) {
      const reqId = req?.REQ_ID || req?.req_id;
      if (!reqId) continue;
      const functionName = String(
        req?.functional_name || req?.label || req?.description || req?.name || ""
      )
        .replace(/^핵심\s*분석\s*모듈\s*:\s*/i, "")
        .replace(/^핵심\s*모듈\s*:\s*/i, "")
        .replace(/^분석\s*모듈\s*:\s*/i, "")
        .trim();
      if (functionName) {
        map[reqId] = functionName;
      }
    }
    return map;
  }, [sa_phase5?.mapped_requirements]);

  const layerBadgeTone = (layer) => {
    const key = String(layer || "").toLowerCase();
    if (key.includes("present")) return "bg-blue-900/30 text-blue-300 border-blue-800/50";
    if (key.includes("app")) return "bg-violet-900/30 text-violet-300 border-violet-800/50";
    if (key.includes("domain")) return "bg-emerald-900/30 text-emerald-300 border-emerald-800/50";
    if (key.includes("infra") || key.includes("data")) return "bg-amber-900/30 text-amber-300 border-amber-800/50";
    if (key.includes("security") || key.includes("auth")) return "bg-rose-900/30 text-rose-300 border-rose-800/50";
    return "bg-slate-800/50 text-slate-300 border-slate-700/60";
  };

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

function StatusBadge({ status }) {
  const normalized = status || "Needs_Clarification";
  const colors = {
    Pass: "bg-green-600/20 text-green-300",
    Fail: "bg-red-600/20 text-red-300",
    Error: "bg-red-600/20 text-red-300",
    Needs_Clarification: "bg-yellow-600/20 text-yellow-300",
    Skipped: "bg-slate-700 text-slate-300",
    Warning_Hallucination_Detected: "bg-amber-600/20 text-amber-300",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-[12px] ${colors[normalized] || colors.Needs_Clarification}`}>
      {normalized}
    </span>
  );
}

function Section({ title, icon, children }) {
  return (
    <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700/50">
      <h4 className="flex items-center gap-1.5 text-sm font-medium text-slate-400 mb-3">
        {icon}
        {title}
      </h4>
      {children}
    </div>
  );
}

// ═══════════════════════════════════════════
//  Empty State
// ═══════════════════════════════════════════

function EmptyState({ text }) {
  return (
    <div className="h-full flex items-center justify-center text-slate-600 text-sm">
      {text}
    </div>
  );
}

