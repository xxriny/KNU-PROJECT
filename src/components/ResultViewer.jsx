/**
 * ResultViewer — 파이프라인 산출물 뷰어
 * 탭에 따라 Overview / RTM / Topology / Context 렌더링
 */

import React from "react";
import useAppStore from "../store/useAppStore";
import TopologyGraph from "./TopologyGraph";
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

  switch (tabId) {
    case "overview":
      return <OverviewTab />;
    case "rtm":
      return <RTMTab />;
    case "topology":
      return <TopologyTab />;
    case "context":
      return <ContextTab />;
    case "sa_overview":
      return <SAOverviewTab />;
    case "sa_feasibility":
      return <SAFeasibilityTab />;
    case "sa_architecture":
      return <SAArchitectureTab />;
    case "sa_security":
      return <SASecurityTab />;
    case "sa_topology":
      return <SATopologyTab />;
    default:
      return <OverviewTab />;
  }
}

// ═══════════════════════════════════════════
//  Overview Tab
// ═══════════════════════════════════════════

function OverviewTab() {
  const { metadata, requirements_rtm, context_spec } = useAppStore();

  if (!metadata) {
    return <EmptyState text="분석 결과가 없습니다" />;
  }

  const stats = {
    total: requirements_rtm.length,
    must: requirements_rtm.filter((r) => r.priority === "Must-have").length,
    should: requirements_rtm.filter((r) => r.priority === "Should-have").length,
    could: requirements_rtm.filter((r) => r.priority === "Could-have").length,
  };

  const categories = {};
  requirements_rtm.forEach((r) => {
    const cat = r.category || "기타";
    categories[cat] = (categories[cat] || 0) + 1;
  });

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4 text-[15px]">
      {/* 프로젝트 정보 */}
      <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700/50">
        <h3 className="text-sm font-semibold text-slate-200 mb-2">
          {metadata.project_name || "프로젝트"}
        </h3>
        <div className="flex items-center gap-3 text-[12px]">
          <span className="px-2 py-0.5 rounded bg-blue-600/20 text-blue-300">
            {metadata.action_type}
          </span>
          <span
            className={`px-2 py-0.5 rounded ${
              metadata.status === "Success"
                ? "bg-green-600/20 text-green-300"
                : "bg-yellow-600/20 text-yellow-300"
            }`}
          >
            {metadata.status}
          </span>
        </div>
        {context_spec?.summary && (
          <p className="mt-3 text-[15px] text-slate-300 leading-relaxed">
            {context_spec.summary}
          </p>
        )}
      </div>

      {/* 통계 카드 */}
      <div className="grid grid-cols-4 gap-3">
        <StatCard label="전체" value={stats.total} color="text-slate-200" />
        <StatCard label="Must-have" value={stats.must} color="text-red-400" />
        <StatCard label="Should-have" value={stats.should} color="text-yellow-400" />
        <StatCard label="Could-have" value={stats.could} color="text-green-400" />
      </div>

      {/* 카테고리 분포 */}
      <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700/50">
        <h4 className="text-sm font-medium text-slate-400 mb-3">카테고리 분포</h4>
        <div className="space-y-2">
          {Object.entries(categories).map(([cat, count]) => (
            <div key={cat} className="flex items-center gap-2">
              <Tag size={11} className="text-slate-500" />
              <span className="text-sm text-slate-300 flex-1">{cat}</span>
              <span className="text-sm text-slate-500">{count}</span>
              <div className="w-24 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full"
                  style={{ width: `${(count / stats.total) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
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
  const { context_spec } = useAppStore();

  if (!context_spec) {
    return <EmptyState text="컨텍스트 명세서가 없습니다" />;
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

function SAFeasibilityTab() {
  const { sa_phase3 } = useAppStore();
  if (!sa_phase3) {
    return <EmptyState text="기술 타당성 결과가 없습니다" />;
  }
  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      <Section title="기술 타당성" icon={<Cpu size={12} />}>
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm text-slate-300">판정</span>
          <StatusBadge status={sa_phase3.status || "Needs_Clarification"} />
        </div>
        <div className="text-sm text-slate-400">복잡도 점수: {sa_phase3.complexity_score ?? "-"}</div>
      </Section>

      {(sa_phase3.reasons || []).length > 0 && (
        <Section title="판정 근거" icon={<CheckCircle size={12} />}>
          <ul className="space-y-1">
            {(sa_phase3.reasons || []).map((item, idx) => (
              <li key={idx} className="text-sm text-slate-400">- {item}</li>
            ))}
          </ul>
        </Section>
      )}

      {(sa_phase3.alternatives || []).length > 0 && (
        <Section title="대안" icon={<Lightbulb size={12} />}>
          <ul className="space-y-1">
            {(sa_phase3.alternatives || []).map((item, idx) => (
              <li key={idx} className="text-sm text-slate-400">- {item}</li>
            ))}
          </ul>
        </Section>
      )}

      {(sa_phase3.high_risk_reqs || []).length > 0 && (
        <Section title="고위험 요구사항" icon={<AlertTriangle size={12} />}>
          <div className="flex flex-wrap gap-2">
            {sa_phase3.high_risk_reqs.map((rid) => (
              <span key={rid} className="px-2 py-0.5 rounded bg-red-600/20 text-red-300 text-[12px] font-mono border border-red-800/30">
                {rid}
              </span>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}

function SAArchitectureTab() {
  const { sa_phase5, sa_phase7 } = useAppStore();
  if (!sa_phase5 && !sa_phase7) {
    return <EmptyState text="아키텍처 결과가 없습니다" />;
  }

  const layerColors = {
    presentation: "bg-blue-600/20 text-blue-300",
    application: "bg-purple-600/20 text-purple-300",
    domain: "bg-teal-600/20 text-teal-300",
    infrastructure: "bg-orange-600/20 text-orange-300",
    security: "bg-red-600/20 text-red-300",
  };

  const grouped = {};
  if (sa_phase5?.mapped_requirements) {
    for (const req of sa_phase5.mapped_requirements) {
      const layer = req.layer || "application";
      if (!grouped[layer]) grouped[layer] = [];
      grouped[layer].push(req);
    }
  }

  const layerOrder = sa_phase5?.layer_order || ["presentation", "application", "domain", "infrastructure", "security"];

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      {sa_phase5 && (
        <Section title="아키텍처 매핑" icon={<Layers size={12} />}>
          <div className="flex items-center gap-2 mb-3">
            <span className="text-[12px] text-slate-400">패턴</span>
            <span className="px-2 py-0.5 rounded bg-blue-600/20 text-blue-300 text-[12px]">
              {sa_phase5.pattern || "Clean Architecture"}
            </span>
            <StatusBadge status={sa_phase5.status || "Needs_Clarification"} />
          </div>

          {layerOrder.map((layer) => {
            const reqs = grouped[layer];
            if (!reqs || reqs.length === 0) return null;
            return (
              <div key={layer} className="mb-3">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${layerColors[layer] || "bg-slate-700 text-slate-400"}`}>
                    {layer}
                  </span>
                  <span className="text-[11px] text-slate-600">{reqs.length}개</span>
                </div>
                <div className="space-y-1 pl-3 border-l border-slate-700">
                  {reqs.map((req) => (
                    <div key={req.REQ_ID} className="flex items-center gap-2 text-[12px]">
                      <span className="text-blue-400 font-mono w-20 flex-shrink-0">{req.REQ_ID}</span>
                      <span className="text-slate-400 flex-1 truncate">{req.description}</span>
                      {req.depends_on?.length > 0 && (
                        <span className="text-slate-600 text-[11px]">→ {req.depends_on.join(", ")}</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </Section>
      )}

      {sa_phase7 && (
        <Section title="인터페이스 계약" icon={<GitBranch size={12} />}>
          <div className="mb-2 flex items-center gap-2">
            <StatusBadge status={sa_phase7.status || "Needs_Clarification"} />
            <span className="text-[12px] text-slate-500">
              계약 {(sa_phase7.interface_contracts || []).length}개
            </span>
          </div>
          {(sa_phase7.guardrails || []).length > 0 && (
            <div className="mb-3">
              <div className="text-[11px] text-slate-500 mb-1.5 uppercase tracking-wider">Guardrails</div>
              <ul className="space-y-1">
                {sa_phase7.guardrails.map((g, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-[12px] text-slate-400">
                    <Shield size={10} className="text-red-400 mt-0.5 flex-shrink-0" />
                    {g}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {(sa_phase7.interface_contracts || []).length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="border-b border-slate-700">
                    <th className="text-left py-1 px-1 text-slate-500 font-medium">계약 ID</th>
                    <th className="text-left py-1 px-1 text-slate-500 font-medium">레이어</th>
                    <th className="text-left py-1 px-1 text-slate-500 font-medium">Input</th>
                    <th className="text-left py-1 px-1 text-slate-500 font-medium">Output</th>
                  </tr>
                </thead>
                <tbody>
                  {sa_phase7.interface_contracts.slice(0, 20).map((c, idx) => (
                    <tr key={idx} className="border-b border-slate-800/50">
                      <td className="py-1 px-1 text-blue-300 font-mono">{c.contract_id}</td>
                      <td className="py-1 px-1">
                        <span className={`px-1.5 py-0.5 rounded text-[11px] ${layerColors[c.layer] || "bg-slate-700 text-slate-400"}`}>
                          {c.layer}
                        </span>
                      </td>
                      <td className="py-1 px-1 text-slate-500">{JSON.stringify(c.input)}</td>
                      <td className="py-1 px-1 text-slate-500">{JSON.stringify(c.output)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {sa_phase7.interface_contracts.length > 20 && (
                <p className="text-[11px] text-slate-600 mt-1 text-right">
                  +{sa_phase7.interface_contracts.length - 20}개 더 있음
                </p>
              )}
            </div>
          )}
        </Section>
      )}
    </div>
  );
}

function SASecurityTab() {
  const { sa_phase6 } = useAppStore();
  if (!sa_phase6) {
    return <EmptyState text="보안 경계 결과가 없습니다" />;
  }
  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      <Section title="보안 경계" icon={<Shield size={12} />}>
        <div className="flex items-center gap-2 mb-3">
          <StatusBadge status={sa_phase6.status || "Needs_Clarification"} />
        </div>

        {/* RBAC 역할 */}
        {(sa_phase6.rbac_roles || []).length > 0 && (
          <div className="mb-3">
            <div className="text-[11px] text-slate-500 mb-1.5 uppercase tracking-wider">RBAC 역할</div>
            <div className="flex flex-wrap gap-2">
              {sa_phase6.rbac_roles.map((role) => (
                <span key={role} className="px-2.5 py-1 rounded-full bg-red-600/15 text-red-300 text-[12px] border border-red-800/30">
                  {role}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Trust Boundaries */}
        {(sa_phase6.trust_boundaries || []).length > 0 && (
          <div className="mb-3">
            <div className="text-[11px] text-slate-500 mb-1.5 uppercase tracking-wider">Trust Boundaries</div>
            <div className="space-y-1.5">
              {sa_phase6.trust_boundaries.map((boundary, idx) => {
                const parts = boundary.split(/\s*->\s*/);
                return (
                  <div key={idx} className="flex items-center gap-1 text-[12px]">
                    {parts.map((part, pi) => (
                      <React.Fragment key={pi}>
                        <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">{part.trim()}</span>
                        {pi < parts.length - 1 && (
                          <ArrowRight size={12} className="text-slate-600 flex-shrink-0" />
                        )}
                      </React.Fragment>
                    ))}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* authz_matrix 요약 */}
        {(sa_phase6.authz_matrix || []).length > 0 && (
          <div>
            <div className="text-[11px] text-slate-500 mb-1.5 uppercase tracking-wider">
              권한 매트릭스 ({sa_phase6.authz_matrix.length}개)
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-[12px]">
                <thead>
                  <tr className="border-b border-slate-700">
                    <th className="text-left py-1 px-1 text-slate-500 font-medium">요구사항</th>
                    <th className="text-left py-1 px-1 text-slate-500 font-medium">Role</th>
                    <th className="text-left py-1 px-1 text-slate-500 font-medium">Access</th>
                  </tr>
                </thead>
                <tbody>
                  {sa_phase6.authz_matrix.slice(0, 16).map((row, idx) => (
                    <tr key={idx} className="border-b border-slate-800/50">
                      <td className="py-1 px-1 text-blue-400 font-mono">{row.req_id}</td>
                      <td className="py-1 px-1 text-slate-400">{row.role}</td>
                      <td className="py-1 px-1">
                        <span className={`px-1.5 py-0.5 rounded text-[11px] ${row.access === "write" ? "bg-orange-600/20 text-orange-300" : "bg-slate-700 text-slate-400"}`}>
                          {row.access}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {sa_phase6.authz_matrix.length > 16 && (
                <p className="text-[11px] text-slate-600 mt-1 text-right">
                  +{sa_phase6.authz_matrix.length - 16}개 더 있음
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
  const { sa_phase8 } = useAppStore();
  if (!sa_phase8) {
    return <EmptyState text="위상 정렬 결과가 없습니다" />;
  }
  const queue = sa_phase8.topo_queue || [];
  const cycles = sa_phase8.cyclic_requirements || [];
  const batches = sa_phase8.parallel_batches || [];

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
              <span key={rid} className="px-2 py-0.5 rounded bg-red-600/20 text-red-300 text-[12px] border border-red-800/30">
                {rid}
              </span>
            ))}
          </div>
          <p className="text-[11px] text-slate-600 mt-2">
            순환 의존성이 있는 요구사항은 위상 정렬에서 제외됩니다. 의존성을 재검토하세요.
          </p>
        </Section>
      )}

      {/* 실행 순서 */}
      {queue.length > 0 && (
        <Section title="구현 순서 (Topology Queue)" icon={<GitBranch size={12} />}>
          <div className="space-y-1">
            {queue.map((rid, idx) => (
              <div key={rid} className="flex items-center gap-3">
                <span className="text-[11px] font-mono text-slate-600 w-6 text-right flex-shrink-0">
                  {idx + 1}
                </span>
                <div className="flex-1 flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-blue-500 flex-shrink-0" />
                  <span className="text-[13px] text-blue-300 font-mono">{rid}</span>
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* 병렬 배치 (batches > 1일 때) */}
      {batches.length > 1 && (
        <Section title="병렬 배치" icon={<Layers size={12} />}>
          <div className="space-y-2">
            {batches.map((batch, idx) => (
              <div key={idx} className="flex items-start gap-2">
                <span className="text-[11px] text-slate-600 font-mono mt-0.5 w-14 flex-shrink-0">
                  Batch {idx + 1}
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {batch.map((rid) => (
                    <span key={rid} className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[12px] font-mono">
                      {rid}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}
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

