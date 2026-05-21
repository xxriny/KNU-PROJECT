import React, { useState } from "react";
import { useStore } from "../../store/useStore";
import {
  ShieldCheck, AlertTriangle, TestTube2, Cpu, Globe, Server, CheckSquare, ChevronDown, ChevronRight
} from "lucide-react";
import Card from "../ui/Card";
import Badge from "../ui/Badge";
import ReportLayout, { ReportSection } from "./layout/ReportLayout";

const RISK_COLORS = {
  critical: "bg-red-500/10 text-red-400 border-red-500/30",
  high: "bg-orange-500/10 text-orange-400 border-orange-500/30",
  medium: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
  low: "bg-green-500/10 text-green-400 border-green-500/30",
};

const SUB_TABS = [
  { id: "unit", label: "Unit", icon: Cpu },
  { id: "integration", label: "Integration", icon: Globe },
  { id: "system", label: "System", icon: Server },
  { id: "acceptance", label: "Acceptance", icon: CheckSquare },
];

export default function SATestStrategyTab() {
  const { isDarkMode, resultData, sa_output } = useStore(["isDarkMode", "resultData", "sa_output"]);
  const [activeSubTab, setActiveSubTab] = useState("unit");

  const testStrategy =
    resultData?.sa_test_strategy ||
    sa_output?.data?.test_strategy ||
    sa_output?.test_strategy ||
    null;

  if (!testStrategy) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-slate-500 gap-3">
        <ShieldCheck size={40} className="opacity-20" />
        <p className="font-bold">테스트 전략 데이터가 없습니다.</p>
        <p className="text-sm">SA 분석(UPDATE 또는 CREATE 모드)을 실행하면 생성됩니다.</p>
      </div>
    );
  }

  const {
    test_philosophy = "",
    risk_zones = [],
    unit_specs = [],
    integration_specs = [],
    system_specs = [],
    acceptance_specs = [],
    test_data_strategy = "",
    automation_priority = [],
  } = testStrategy;

  const subContent = {
    unit: <UnitTab specs={unit_specs} isDarkMode={isDarkMode} />,
    integration: <IntegrationTab specs={integration_specs} isDarkMode={isDarkMode} />,
    system: <SystemTab specs={system_specs} isDarkMode={isDarkMode} />,
    acceptance: <AcceptanceTab specs={acceptance_specs} isDarkMode={isDarkMode} />,
  };

  return (
    <ReportLayout
      icon={ShieldCheck}
      title="Test Strategy"
      subtitle="소프트웨어 공학 관점의 테스트 전략 — 아키텍처 위험 평가, 단계별 테스트 명세, 자동화 우선순위."
      badge={`${risk_zones.length} Risk Zones`}
    >
      {/* 철학 */}
      {test_philosophy && (
        <ReportSection title="Test Philosophy" icon={<ShieldCheck size={20} className="text-blue-400" />}>
          <Card variant="solid" className="p-6 border-l-4 border-l-blue-500/40">
            <p className={`text-base leading-relaxed font-medium ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>
              {test_philosophy}
            </p>
          </Card>
        </ReportSection>
      )}

      {/* 위험 영역 */}
      {risk_zones.length > 0 && (
        <ReportSection
          title="Risk Zones"
          icon={<AlertTriangle size={20} className="text-orange-400" />}
          badge={risk_zones.length}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {risk_zones.map((zone, i) => (
              <RiskZoneCard key={i} zone={zone} isDarkMode={isDarkMode} />
            ))}
          </div>
        </ReportSection>
      )}

      {/* 서브탭 */}
      <ReportSection title="Test Specifications" icon={<TestTube2 size={20} className="text-teal-400" />}>
        {/* 탭 헤더 */}
        <div className={`flex gap-1 p-1 rounded-xl mb-6 w-fit ${isDarkMode ? "bg-white/5" : "bg-slate-100"}`}>
          {SUB_TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setActiveSubTab(id)}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
                activeSubTab === id
                  ? isDarkMode
                    ? "bg-blue-600 text-white shadow"
                    : "bg-white text-blue-600 shadow"
                  : isDarkMode
                  ? "text-slate-400 hover:text-white"
                  : "text-slate-500 hover:text-slate-800"
              }`}
            >
              <Icon size={14} />
              {label}
            </button>
          ))}
        </div>
        {subContent[activeSubTab]}
      </ReportSection>

      {/* 메타 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {test_data_strategy && (
          <ReportSection title="Test Data Strategy" icon={<Server size={20} className="text-purple-400" />}>
            <Card variant="glass" className="p-5">
              <p className={`text-sm leading-relaxed ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>
                {test_data_strategy}
              </p>
            </Card>
          </ReportSection>
        )}
        {automation_priority.length > 0 && (
          <ReportSection title="Automation Priority" icon={<CheckSquare size={20} className="text-emerald-400" />}>
            <div className="space-y-2">
              {automation_priority.map((item, i) => (
                <div key={i} className={`flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium ${isDarkMode ? "bg-white/5 text-slate-300" : "bg-slate-50 text-slate-700"}`}>
                  <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-black shrink-0 ${i === 0 ? "bg-blue-500 text-white" : "bg-slate-500/20 text-slate-500"}`}>
                    {i + 1}
                  </span>
                  {item}
                </div>
              ))}
            </div>
          </ReportSection>
        )}
      </div>
    </ReportLayout>
  );
}

// ── 서브탭 컴포넌트 ─────────────────────────────────────────

function UnitTab({ specs, isDarkMode }) {
  if (!specs.length) return <EmptySpec label="Unit Test" />;
  return (
    <div className="space-y-4">
      {specs.map((spec, i) => (
        <Card key={i} variant="glass" className="p-6">
          <h4 className={`font-bold text-base mb-4 ${isDarkMode ? "text-white" : "text-slate-900"}`}>
            {spec.component_name}
          </h4>
          <div className="space-y-4">
            <SpecList label="Key Invariants" items={spec.key_invariants} color="blue" isDarkMode={isDarkMode} />
            <SpecList label="Mock Targets" items={spec.mock_targets} color="purple" isDarkMode={isDarkMode} />
            <SpecList label="Edge Cases" items={spec.edge_cases} color="amber" isDarkMode={isDarkMode} />
          </div>
        </Card>
      ))}
    </div>
  );
}

function IntegrationTab({ specs, isDarkMode }) {
  if (!specs.length) return <EmptySpec label="Integration Test" />;
  return (
    <div className="space-y-4">
      {specs.map((spec, i) => (
        <Card key={i} variant="glass" className="p-6">
          <div className="flex items-center gap-2 mb-4">
            <Badge variant="blue" className="font-mono text-xs">{spec.endpoint}</Badge>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <InfoRow label="DB Approach" value={spec.db_approach} isDarkMode={isDarkMode} />
            <InfoRow label="Transaction Scenario" value={spec.transaction_scenario} isDarkMode={isDarkMode} />
            {spec.contract_pair && <InfoRow label="Contract Pair" value={spec.contract_pair} isDarkMode={isDarkMode} />}
          </div>
        </Card>
      ))}
    </div>
  );
}

function SystemTab({ specs, isDarkMode }) {
  if (!specs.length) return <EmptySpec label="System Test" />;
  return (
    <div className="space-y-4">
      {specs.map((spec, i) => (
        <Card key={i} variant="glass" className="p-6">
          <div className="mb-4">
            <span className={`text-xs font-bold uppercase tracking-widest ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>Critical Path</span>
            <p className={`mt-1 font-mono text-sm ${isDarkMode ? "text-cyan-300" : "text-cyan-700"}`}>{spec.critical_path}</p>
          </div>
          <Badge variant="secondary" className="mb-4">SLA: {spec.sla_target}</Badge>
          <SpecList label="Chaos Scenarios" items={spec.chaos_scenarios} color="red" isDarkMode={isDarkMode} />
        </Card>
      ))}
    </div>
  );
}

function AcceptanceTab({ specs, isDarkMode }) {
  if (!specs.length) return <EmptySpec label="Acceptance Test" />;
  return (
    <div className="space-y-4">
      {specs.map((spec, i) => (
        <Card key={i} variant="glass" className="p-6">
          <Badge variant="blue" className="mb-4">{spec.feat_id}</Badge>
          <div className="space-y-3">
            <BddRow label="Given" value={spec.given} color="green" isDarkMode={isDarkMode} />
            <BddRow label="When" value={spec.when} color="blue" isDarkMode={isDarkMode} />
            <BddRow label="Then" value={spec.then_ ?? spec.then} color="purple" isDarkMode={isDarkMode} />
            {spec.edge_case && <BddRow label="Edge" value={spec.edge_case} color="amber" isDarkMode={isDarkMode} />}
          </div>
        </Card>
      ))}
    </div>
  );
}

// ── 공통 UI ──────────────────────────────────────────────────

function RiskZoneCard({ zone, isDarkMode }) {
  const level = (zone.risk_level || "medium").toLowerCase();
  const colorClass = RISK_COLORS[level] || RISK_COLORS.medium;
  return (
    <Card variant="glass" className={`p-5 border ${colorClass}`}>
      <div className="flex items-center justify-between mb-3">
        <h4 className={`font-bold ${isDarkMode ? "text-white" : "text-slate-900"}`}>{zone.component_name}</h4>
        <Badge className={`uppercase text-[10px] font-black ${colorClass}`}>{level}</Badge>
      </div>
      <p className={`text-sm mb-3 ${isDarkMode ? "text-slate-400" : "text-slate-600"}`}>{zone.reason}</p>
      {zone.mitigation && (
        <div className={`text-xs font-medium p-2 rounded-lg ${isDarkMode ? "bg-white/5 text-slate-400" : "bg-slate-50 text-slate-500"}`}>
          💡 {zone.mitigation}
        </div>
      )}
    </Card>
  );
}

function SpecList({ label, items = [], color, isDarkMode }) {
  if (!items.length) return null;
  const colorMap = {
    blue: "bg-blue-500/10 text-blue-400",
    purple: "bg-purple-500/10 text-purple-400",
    amber: "bg-amber-500/10 text-amber-400",
    red: "bg-red-500/10 text-red-400",
    green: "bg-green-500/10 text-green-400",
  };
  return (
    <div>
      <span className={`text-xs font-bold uppercase tracking-wider px-2 py-1 rounded-md ${colorMap[color] || colorMap.blue}`}>{label}</span>
      <ul className="mt-2 space-y-1.5">
        {items.map((item, i) => (
          <li key={i} className={`flex items-start gap-2 text-sm ${isDarkMode ? "text-slate-400" : "text-slate-600"}`}>
            <span className="text-slate-600 mt-0.5 shrink-0">•</span>
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

function InfoRow({ label, value, isDarkMode }) {
  return (
    <div>
      <span className={`text-xs font-bold uppercase tracking-wide ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>{label}</span>
      <p className={`mt-1 text-sm ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>{value}</p>
    </div>
  );
}

function BddRow({ label, value, color, isDarkMode }) {
  const colorMap = {
    green: "text-green-400",
    blue: "text-blue-400",
    purple: "text-purple-400",
    amber: "text-amber-400",
  };
  return (
    <div className="flex gap-3">
      <span className={`text-xs font-black w-12 shrink-0 mt-0.5 uppercase ${colorMap[color] || "text-slate-400"}`}>{label}</span>
      <p className={`text-sm ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>{value}</p>
    </div>
  );
}

function EmptySpec({ label }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-slate-500">
      <TestTube2 size={32} className="opacity-20 mb-2" />
      <p className="text-sm">{label} 명세 없음</p>
    </div>
  );
}
