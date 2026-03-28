import React, { useMemo } from "react";
import useAppStore from "../../store/useAppStore";
import { StatCard, Section, EmptyState } from "./SharedComponents";
import SAArtifactGraph from "../SAArtifactGraph";
import { normalizeFlowchartForGraph } from "../saGraphAdapters";
import { buildReqFunctionNameMap } from "./resultUtils";
import { GitBranch, Layers } from "lucide-react";

export default function SAFlowchartTab() {
  const { sa_artifacts, sa_phase5 } = useAppStore();
  const spec = sa_artifacts?.flowchart_spec;

  if (!spec) {
    return <EmptyState text="Flowchart 산출물이 없습니다" />;
  }

  const stages = spec.stages || [];
  const summary = spec.summary || {};
  const quality = spec.data_quality || {};
  const reqFunctionNameMap = useMemo(
    () => buildReqFunctionNameMap(sa_phase5?.mapped_requirements),
    [sa_phase5?.mapped_requirements]
  );

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
