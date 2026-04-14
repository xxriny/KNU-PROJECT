import React from "react";
import useAppStore from "../../store/useAppStore";
import { Section, EmptyState } from "./SharedComponents";
import { CheckCircle, AlertTriangle, ArrowRight, Tag, Shield, Lightbulb, AlertCircle, Layers, GitBranch } from "lucide-react";

export default function ContextTab() {
  const { pm_bundle, pm_coverage_rate, pm_warnings, thinking_log, isDarkMode } = useAppStore();

  if (!pm_bundle) {
    return <EmptyState text="PM 분석 보고서가 아직 생성되지 않았습니다" />;
  }

  const { metadata, data } = pm_bundle;
  const safePmWarnings = Array.isArray(pm_warnings) ? pm_warnings : (typeof pm_warnings === "string" ? [pm_warnings] : []);
  const safeThinkingLog = Array.isArray(thinking_log) ? thinking_log : [];
  // pm_analysis 노드의 thinking 찾기
  const analysisThinking = safeThinkingLog.find(log => log.node === "pm_analysis")?.thinking || "";

  return (
    <div className="h-full overflow-y-auto p-4 space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { label: "기술 스택 커버리지", value: `${(pm_coverage_rate * 100).toFixed(1)}%`, color: "text-blue-500" },
          { label: "발견된 이슈/위험", value: safePmWarnings.length, color: safePmWarnings.length > 0 ? "text-orange-500" : "text-green-500" },
          { label: "번들 사양 버전", value: metadata?.version || "v1.0", color: isDarkMode ? "text-slate-300" : "text-slate-700" }
        ].map((stat, i) => (
          <div key={i} className={`p-4 rounded-xl border flex flex-col items-center justify-center transition-all ${isDarkMode ? "bg-slate-900/50 border-slate-700/50" : "bg-white border-slate-200 shadow-sm"}`}>
            <div className={`text-3xl font-bold ${stat.color}`}>{stat.value}</div>
            <div className="text-[12px] text-slate-500 mt-1 uppercase tracking-wider font-semibold">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* ── AI PM의 전략적 사고 (Thinking) ── */}
      {analysisThinking && (
        <Section title="AI PM 전략적 분석" icon={<Lightbulb size={12} />}>
          <div className={`border rounded-lg p-4 transition-all ${isDarkMode ? "bg-blue-500/5 border-blue-500/20" : "bg-blue-50 border-blue-100 shadow-sm"}`}>
            <p className={`text-[14px] leading-relaxed whitespace-pre-wrap ${isDarkMode ? "text-slate-300" : "text-slate-600"}`}>
              {analysisThinking}
            </p>
          </div>
        </Section>
      )}

      {/* ── 경고 및 권장 사항 ── */}
      {safePmWarnings.length > 0 && (
        <Section title="검토 필요 사항 (Warnings)" icon={<AlertTriangle size={12} />}>
          <div className="space-y-2">
            {safePmWarnings.map((warning, idx) => (
              <div key={idx} className={`flex items-start gap-3 p-3 border rounded-lg transition-all ${isDarkMode ? "bg-orange-500/5 border-orange-500/20" : "bg-orange-50 border-orange-100 shadow-sm"}`}>
                <AlertCircle size={14} className="text-orange-500 mt-0.5" />
                <p className={`text-sm ${isDarkMode ? "text-orange-200/80" : "text-orange-800"}`}>{warning}</p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* ── 프로젝트 메타데이터 ── */}
      <Section title="분석 메타데이터" icon={<Layers size={12} />}>
        <div className="grid grid-cols-2 gap-4 text-sm text-slate-400">
          <div className="space-y-1">
            <div className="text-[12px] text-slate-600">세션 ID</div>
            <div className="font-mono text-[12px]">{metadata?.session_id}</div>
          </div>
          <div className="space-y-1">
            <div className="text-[12px] text-slate-600">분석 완료 시각</div>
            <div className="text-[12px]">{metadata?.created_at ? new Date(metadata.created_at).toLocaleString() : "-"}</div>
          </div>
        </div>
      </Section>
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
