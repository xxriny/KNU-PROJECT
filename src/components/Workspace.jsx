/**
 * Workspace — 중앙 패널
 *
 * Two-Tier 탭 구조:
 * - Tier 1: 코드 파일 탭
 * - Tier 2: Output 탭 (Home, Progress, Overview, PM)
 * - Shared Viewport: 단 하나의 렌더링 영역
 */

import React, { useEffect, useRef, useState } from "react";
import useAppStore from "../store/useAppStore";
import CodeViewer from "./CodeViewer";
import ResultViewer from "./ResultViewer";
import HomeScreen from "./HomeScreen";
import PipelineProgress from "./PipelineProgress";
import { X, Code2, LayoutDashboard, ChevronDown, House, Activity } from "lucide-react";

const PM_TABS = ["rtm", "context"];
const PM_LABELS = { rtm: "RTM", context: "Context" };
const SA_TABS = ["sa_architecture", "sa_security", "sa_topology", "sa_system", "sa_flowchart", "sa_uml", "sa_interfaces", "sa_decisions"];
const SA_LABELS = {
  sa_architecture: "Architecture",
  sa_security: "Security",
  sa_topology: "Topology Queue",
  sa_system: "System Diagram",
  sa_flowchart: "Flowchart",
  sa_uml: "UML Components",
  sa_interfaces: "Interfaces",
  sa_decisions: "Decision Table",
};

export default function Workspace() {
  const {
    openFiles,
    activeViewportTab,
    activateCodeTab,
    activateOutputTab,
    closeFile,
    pipelineStatus,
    pipelineType,
    thinkingLog,
    resultData,
    sa_artifacts,
  } = useAppStore();

  const [pmOpen, setPmOpen] = useState(false);
  const [saOpen, setSaOpen] = useState(false);
  const pmRef = useRef(null);
  const saRef = useRef(null);
  const activeOutputId = activeViewportTab?.kind === "output" ? activeViewportTab.id : null;
  const isPmActive = PM_TABS.includes(activeOutputId);
  const isSaActive = SA_TABS.includes(activeOutputId);
  const hasProgress = pipelineStatus === "running" || pipelineStatus === "error" || thinkingLog.length > 0;
  const SA_PIPELINE_TYPES = ["analysis_create", "analysis_reverse", "analysis_update"];
  const hasSaData = Boolean(
    sa_artifacts ||
    resultData?.system_scan ||
    resultData?.sa_phase3 ||
    resultData?.sa_phase8
  ) || (SA_PIPELINE_TYPES.includes(pipelineType) && pipelineStatus !== "idle");

  useEffect(() => {
    const handler = (e) => {
      if (pmRef.current && !pmRef.current.contains(e.target)) {
        setPmOpen(false);
      }
      if (saRef.current && !saRef.current.contains(e.target)) {
        setSaOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const renderViewport = () => {
    if (activeViewportTab?.kind === "code") {
      return <CodeViewer />;
    }

    switch (activeOutputId) {
      case "home":
        return <HomeScreen />;
      case "progress":
        return <PipelineProgress />;
      case "overview":
      case "sa_overview":
      case "sa_feasibility":
        return <ResultViewer tabId="overview" />;
      case "rtm":
      case "context":
      case "sa_architecture":
      case "sa_security":
      case "sa_topology":
      case "sa_system":
      case "sa_flowchart":
      case "sa_uml":
      case "sa_interfaces":
      case "sa_decisions":
        return <ResultViewer tabId={activeOutputId} />;
      default:
        return <HomeScreen />;
    }
  };

  const isCodeViewport = activeViewportTab?.kind === "code";

  return (
    <div className="h-full flex flex-col bg-slate-950 text-[15px]">
      <div className="flex items-center border-b border-slate-700/50 bg-slate-900/50 min-h-9">
        <div className="flex items-center gap-0.5 px-1 py-0.5 overflow-x-auto w-full">
          {openFiles.length === 0 ? (
            <div className="px-3 py-1.5 text-[15px] text-slate-600">열린 코드 탭이 없습니다</div>
          ) : (
            openFiles.map((file) => {
              const isActive = activeViewportTab?.kind === "code" && activeViewportTab.id === file.id;
              return (
                <div
                  key={file.id}
                  className={`group flex items-center gap-1.5 px-3 py-1.5 text-[15px] rounded-t cursor-pointer transition-colors ${
                    isActive
                      ? "bg-slate-800 text-blue-300 border-t-2 border-blue-500"
                      : "text-slate-500 hover:text-slate-300 hover:bg-slate-800/50"
                  }`}
                  onClick={() => activateCodeTab(file.id)}
                >
                  <Code2 size={11} />
                  <span className="truncate max-w-[160px]">{file.name}</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); closeFile(file.id); }}
                    className="opacity-0 group-hover:opacity-100 hover:text-red-400 transition-opacity"
                  >
                    <X size={11} />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>

      <div className="flex items-center border-b border-slate-700/50 bg-slate-900/60 px-1 min-h-9">
        <button
          onClick={() => activateOutputTab("home")}
          className={`flex items-center gap-1 px-3 py-1.5 text-[15px] transition-colors ${
            activeOutputId === "home"
              ? "text-blue-300 border-b-2 border-blue-500"
              : "text-slate-500 hover:text-slate-300"
          }`}
        >
          <House size={12} />
          <span>Home</span>
        </button>

        {hasProgress && (
          <button
            onClick={() => activateOutputTab("progress")}
            className={`flex items-center gap-1 px-3 py-1.5 text-[15px] transition-colors ${
              activeOutputId === "progress"
                ? "text-blue-300 border-b-2 border-blue-500"
                : "text-slate-500 hover:text-slate-300"
            }`}
          >
            <Activity size={12} />
            <span>Progress</span>
          </button>
        )}

        <button
          onClick={() => activateOutputTab("overview")}
          className={`flex items-center gap-1 px-3 py-1.5 text-[15px] transition-colors ${
            activeOutputId === "overview"
              ? "text-blue-300 border-b-2 border-blue-500"
              : "text-slate-500 hover:text-slate-300"
          }`}
        >
          <LayoutDashboard size={12} />
          <span>Overview</span>
        </button>

        <div className="relative" ref={pmRef}>
          <button
            onClick={() => setPmOpen((open) => !open)}
            className={`flex items-center gap-1 px-3 py-1.5 text-[15px] transition-colors ${
              isPmActive
                ? "text-blue-300 border-b-2 border-blue-500"
                : "text-slate-500 hover:text-slate-300"
            }`}
          >
            <span>PM</span>
            {isPmActive && (
              <span className="text-[12px] text-slate-400">› {PM_LABELS[activeOutputId]}</span>
            )}
            <ChevronDown size={11} className={`transition-transform ${pmOpen ? "rotate-180" : ""}`} />
          </button>

          {pmOpen && (
            <div className="absolute top-full left-0 z-50 mt-0.5 bg-slate-800 border border-slate-700 rounded-md shadow-xl overflow-hidden">
              {PM_TABS.map((id) => (
                <button
                  key={id}
                  onClick={() => { activateOutputTab(id); setPmOpen(false); }}
                  className={`block w-full text-left px-4 py-2 text-[15px] transition-colors ${
                    activeOutputId === id
                      ? "bg-slate-700 text-blue-300"
                      : "text-slate-300 hover:bg-slate-700/60"
                  }`}
                >
                  {PM_LABELS[id]}
                </button>
              ))}
            </div>
          )}
        </div>

        {hasSaData && (
          <div className="relative" ref={saRef}>
            <button
              onClick={() => setSaOpen((open) => !open)}
              className={`flex items-center gap-1 px-3 py-1.5 text-[15px] transition-colors ${
                isSaActive
                  ? "text-blue-300 border-b-2 border-blue-500"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              <span>SA</span>
              {isSaActive && (
                <span className="text-[12px] text-slate-400">› {SA_LABELS[activeOutputId]}</span>
              )}
              <ChevronDown size={11} className={`transition-transform ${saOpen ? "rotate-180" : ""}`} />
            </button>

            {saOpen && (
              <div className="absolute top-full left-0 z-50 mt-0.5 bg-slate-800 border border-slate-700 rounded-md shadow-xl overflow-hidden min-w-[168px]">
                {SA_TABS.map((id) => (
                  <button
                    key={id}
                    onClick={() => { activateOutputTab(id); setSaOpen(false); }}
                    className={`block w-full text-left px-4 py-2 text-[15px] transition-colors ${
                      activeOutputId === id
                        ? "bg-slate-700 text-blue-300"
                        : "text-slate-300 hover:bg-slate-700/60"
                    }`}
                  >
                    {SA_LABELS[id]}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex-1 overflow-hidden">
        {isCodeViewport ? (
          renderViewport()
        ) : (
          <div className="h-full overflow-auto">
            <div className="min-w-[1080px] h-full">
              {renderViewport()}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
