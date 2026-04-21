/**
 * ResultViewer — 파이프라인 산출물 뷰어 (라우터)
 * tabId에 따라 개별 탭 컴포넌트를 렌더링한다.
 */

import React from "react";
import OverviewTab from "./resultViewer/OverviewTab";
import RTMTab from "./resultViewer/RTMTab";
import TopologyTab from "./resultViewer/TopologyTab";
import ContextTab from "./resultViewer/ContextTab";
import SAAnalysisTab from "./resultViewer/SAAnalysisTab";
import SAComponentsTab from "./resultViewer/SAComponentsTab";
import SAApiTab from "./resultViewer/SAApiTab";
import SADatabaseTab from "./resultViewer/SADatabaseTab";

const TAB_COMPONENTS = {
  overview: OverviewTab,
  rtm: RTMTab,
  topology: TopologyTab,
  context: ContextTab,
  sa_overview: SAAnalysisTab,
  sa_components: SAComponentsTab,
  sa_api: SAApiTab,
  sa_db: SADatabaseTab,
};

export default function ResultViewer({ tabId = "overview" }) {
  const TabComponent = TAB_COMPONENTS[tabId] || OverviewTab;
  return (
    <div className="doc-font-up">
      <TabComponent />
    </div>
  );
}
