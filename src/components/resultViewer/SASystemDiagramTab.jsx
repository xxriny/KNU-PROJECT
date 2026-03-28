import React from "react";
import useAppStore from "../../store/useAppStore";
import { StatCard, Section, EmptyState } from "./SharedComponents";
import SAArtifactGraph from "../SAArtifactGraph";
import { normalizeContainerDiagramForGraph } from "../saGraphAdapters";
import { Layers } from "lucide-react";

export default function SASystemDiagramTab() {
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
