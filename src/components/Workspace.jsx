import React, { useEffect, useRef, useState } from "react";
import useAppStore from "../store/useAppStore";
import CodeViewer from "./CodeViewer";
import ResultViewer from "./ResultViewer";
import HomeScreen from "./HomeScreen";
import PipelineProgress from "./PipelineProgress";
import WorkspaceTabs from "./workspace/WorkspaceTabs";

const PM_TABS = ["rtm", "context"];
const PM_LABELS = { rtm: "RTM & Stack", context: "PM Report" };
const SA_TABS = ["sa_overview", "sa_components", "sa_api", "sa_db"];
const SA_LABELS = {
  sa_overview: "QA Analysis",
  sa_components: "Components",
  sa_api: "API Spec",
  sa_db: "Database",
};

export default function Workspace() {
  const openFiles = useAppStore((state) => state.openFiles);
  const activeViewportTab = useAppStore((state) => state.activeViewportTab);
  const activateCodeTab = useAppStore((state) => state.activateCodeTab);
  const activateOutputTab = useAppStore((state) => state.activateOutputTab);
  const closeFile = useAppStore((state) => state.closeFile);
  const pipelineStatus = useAppStore((state) => state.pipelineStatus);
  const pipelineType = useAppStore((state) => state.pipelineType);
  const thinkingLog = useAppStore((state) => state.thinkingLog);
  const resultData = useAppStore((state) => state.resultData);
  const sa_artifacts = useAppStore((state) => state.sa_artifacts);
  const isDarkMode = useAppStore((state) => state.isDarkMode);

  const [pmOpen, setPmOpen] = useState(false);
  const [saOpen, setSaOpen] = useState(false);
  const pmRef = useRef(null);
  const saRef = useRef(null);

  const activeOutputId = activeViewportTab?.kind === "output" ? activeViewportTab.id : null;
  const isPmActive = PM_TABS.includes(activeOutputId);
  const isSaActive = SA_TABS.includes(activeOutputId);
  const hasProgress = pipelineStatus === "running" || pipelineStatus === "error" || thinkingLog.length > 0;
  
  const SA_PIPELINE_TYPES = ["analysis_create", "analysis_reverse", "analysis_update"];
  const hasSaData = Boolean(sa_artifacts || resultData?.sa_output) ||
    (SA_PIPELINE_TYPES.includes(pipelineType) && pipelineStatus !== "idle");

  useEffect(() => {
    const handler = (e) => {
      if (pmRef.current && !pmRef.current.contains(e.target)) setPmOpen(false);
      if (saRef.current && !saRef.current.contains(e.target)) setSaOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const renderViewport = () => {
    if (activeViewportTab?.kind === "code") return <CodeViewer />;
    
    switch (activeOutputId) {
      case "home": return <HomeScreen />;
      case "progress": return <PipelineProgress />;
      case "overview":
      case "memo":
      case "rtm":
      case "context":
      case "sa_overview":
      case "sa_components":
      case "sa_api":
      case "sa_db":
        return <ResultViewer tabId={activeOutputId} />;
      default: return <HomeScreen />;
    }
  };

  return (
    <div className={`h-full flex flex-col bg-transparent text-[15px] transition-colors duration-300 ${isDarkMode ? "dark" : "light"}`}>
      <WorkspaceTabs
        openFiles={openFiles}
        activeViewportTab={activeViewportTab}
        activateCodeTab={activateCodeTab}
        closeFile={closeFile}
        activeOutputId={activeOutputId}
        activateOutputTab={activateOutputTab}
        hasProgress={hasProgress}
        hasSaData={hasSaData}
        pmOpen={pmOpen}
        setPmOpen={setPmOpen}
        pmRef={pmRef}
        PM_TABS={PM_TABS}
        PM_LABELS={PM_LABELS}
        isPmActive={isPmActive}
        saOpen={saOpen}
        setSaOpen={setSaOpen}
        saRef={saRef}
        SA_TABS={SA_TABS}
        SA_LABELS={SA_LABELS}
        isSaActive={isSaActive}
      />

      <div className="flex-1 overflow-hidden">
        {renderViewport()}
      </div>
    </div>
  );
}
