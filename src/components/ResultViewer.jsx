/**
 * ResultViewer — 파이프라인 산출물 뷰어 (라우터)
 * tabId에 따라 개별 탭 컴포넌트를 렌더링한다.
 */

import React from "react";
import OverviewTab from "./resultViewer/OverviewTab";
import RTMTab from "./resultViewer/RTMTab";
import TopologyTab from "./resultViewer/TopologyTab";
import ContextTab from "./resultViewer/ContextTab";
import SAArchitectureTab from "./resultViewer/SAArchitectureTab";
import SASecurityTab from "./resultViewer/SASecurityTab";
import SATopologyTab from "./resultViewer/SATopologyTab";
import SASystemDiagramTab from "./resultViewer/SASystemDiagramTab";
import SAFlowchartTab from "./resultViewer/SAFlowchartTab";
import SAUMLComponentTab from "./resultViewer/SAUMLComponentTab";
import SAInterfacesTab from "./resultViewer/SAInterfacesTab";
import SADecisionTableTab from "./resultViewer/SADecisionTableTab";

const TAB_COMPONENTS = {
  overview: OverviewTab,
  rtm: RTMTab,
  topology: TopologyTab,
  context: ContextTab,
  sa_architecture: SAArchitectureTab,
  sa_security: SASecurityTab,
  sa_topology: SATopologyTab,
  sa_system: SASystemDiagramTab,
  sa_flowchart: SAFlowchartTab,
  sa_uml: SAUMLComponentTab,
  sa_interfaces: SAInterfacesTab,
  sa_decisions: SADecisionTableTab,
};

export default function ResultViewer({ tabId = "overview" }) {
  const TabComponent = TAB_COMPONENTS[tabId] || OverviewTab;
  return (
    <div className="doc-font-up">
      <TabComponent />
    </div>
  );
}
