import React, { useMemo, useState } from "react";
import useAppStore from "../../store/useAppStore";
import { StatCard, Section, EmptyState } from "./SharedComponents";
import SAArtifactGraph from "../SAArtifactGraph";
import { normalizeUMLForGraph } from "../saGraphAdapters";
import { Cpu, Layers } from "lucide-react";

export default function SAUMLComponentTab() {
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
