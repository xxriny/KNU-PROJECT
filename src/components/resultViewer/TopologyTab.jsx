import React from "react";
import useAppStore from "../../store/useAppStore";
import TopologyGraph from "../TopologyGraph";
import { EmptyState } from "./SharedComponents";

export default function TopologyTab() {
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
