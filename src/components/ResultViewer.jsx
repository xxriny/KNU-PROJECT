import React from "react";
import useAppStore from "../store/useAppStore";
import OverviewTab from "./resultViewer/OverviewTab";
import RTMTab from "./resultViewer/RTMTab";
import StackTab from "./resultViewer/StackTab";
import SAAnalysisTab from "./resultViewer/SAAnalysisTab";
import SAComponentsTab from "./resultViewer/SAComponentsTab";
import SAApiTab from "./resultViewer/SAApiTab";
import SADatabaseTab from "./resultViewer/SADatabaseTab";
import SATestStrategyTab from "./resultViewer/SATestStrategyTab";
import ProjectStructureTab from "./resultViewer/ProjectStructureTab";
import AgileVerifierTab from "./resultViewer/AgileVerifierTab";
import AgileImpactTab from "./resultViewer/AgileImpactTab";
import GitHubDashboard from "./github/GitHubDashboard";
import TaskApprovalPanel from "./resultViewer/TaskApprovalPanel";
import Skeleton from "./ui/Skeleton";

const TAB_COMPONENTS = {
  overview: OverviewTab,
  rtm: RTMTab,
  stack: StackTab,
  sa_overview: SAAnalysisTab,
  sa_components: SAComponentsTab,
  sa_api: SAApiTab,
  sa_db: SADatabaseTab,
  sa_test_strategy: SATestStrategyTab,
  project_structure: ProjectStructureTab,
  agile_verify: AgileVerifierTab,
  agile_impact: AgileImpactTab,
  github_dashboard: GitHubDashboard,
  task_approval: TaskApprovalPanel,
  memo: AgileImpactTab,  // 메모 탭은 통합된 변경분석 탭으로 리디렉션
};

export default function ResultViewer({ tabId = "overview" }) {
  const pipelineStatus = useAppStore((state) => state.pipelineStatus);
  const resultData = useAppStore((state) => state.resultData);

  const TabComponent = TAB_COMPONENTS[tabId] || OverviewTab;

  const isLoading = pipelineStatus === "running" && !resultData;

  return (
    <div className="relative h-full overflow-hidden">
      {/* Main Content Area */}
      <div className="h-full overflow-hidden flex flex-col">
        {isLoading ? (
          <div className="flex-1 p-8 space-y-8 animate-fade-in">
            <Skeleton className="h-12 w-3/4" />
            <div className="grid grid-cols-2 gap-4">
              <Skeleton className="h-32" />
              <Skeleton className="h-32" />
            </div>
            <Skeleton className="h-64" />
          </div>
        ) : (
          <div className="flex-1 h-full overflow-y-auto custom-scrollbar doc-font-up selectable">
            <TabComponent />
          </div>
        )}
      </div>
    </div>
  );
}
