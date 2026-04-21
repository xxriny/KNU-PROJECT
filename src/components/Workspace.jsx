import React, { useEffect, useRef, useState } from "react";
import useAppStore from "../store/useAppStore";
import CodeViewer from "./CodeViewer";
import ResultViewer from "./ResultViewer";
import HomeScreen from "./HomeScreen";
import PipelineProgress from "./PipelineProgress";
import { X, Code2, LayoutDashboard, ChevronDown, House, Activity } from "lucide-react";

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
    isDarkMode,
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
      return (
        <div
          key="code-viewer"
          className="h-full w-full"
        >
          <CodeViewer />
        </div>
      );
    }

    const content = (() => {
      switch (activeOutputId) {
        case "home":
          return <HomeScreen />;
        case "progress":
          return <PipelineProgress />;
        case "overview":
        case "sa_overview":
        case "sa_components":
        case "sa_api":
        case "sa_db":
          return <ResultViewer tabId={activeOutputId} />;
        default:
          return <HomeScreen />;
      }
    })();

    return (
      <div
        key={activeOutputId || "fallback"}
        className="h-full w-full"
      >
        {content}
      </div>
    );
  };

  const isCodeViewport = activeViewportTab?.kind === "code";

  return (
    <div className={`h-full flex flex-col bg-transparent text-[15px] transition-colors duration-300 ${isDarkMode ? "dark" : "light"}`}>
      <div className={`flex items-center border-b border-[var(--border)] min-h-11 px-2`}>
        <div className="flex items-center gap-0.5 px-1 py-0.5 overflow-x-auto w-full scrollbar-hide">
          {openFiles.length === 0 ? (
            <div className="px-3 py-1.5 text-[14px] text-slate-500 font-medium">열린 코드 탭이 없습니다</div>
          ) : (
            openFiles.map((file) => {
              const isActive = activeViewportTab?.kind === "code" && activeViewportTab.id === file.id;
              return (
                <div
                  key={file.id}
                  className={`group flex items-center gap-2 px-4 py-2 text-[14px] rounded-xl cursor-pointer transition-all ${
                    isActive
                      ? "bg-[var(--accent)]/10 text-[var(--accent)] font-bold shadow-sm"
                      : "text-slate-500 hover:text-slate-300 hover:bg-white/5"
                  }`}
                  onClick={() => activateCodeTab(file.id)}
                >
                  <Code2 size={13} className={isActive ? "text-[var(--accent)]" : "text-slate-500"} />
                  <span className="truncate max-w-[160px]">{file.name}</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); closeFile(file.id); }}
                    className="opacity-0 group-hover:opacity-100 hover:text-red-400 transition-opacity p-0.5"
                  >
                    <X size={11} />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>

      <div className={`flex items-center border-b border-[var(--border)] px-4 min-h-12 bg-transparent gap-1`}>
        <button
          onClick={() => activateOutputTab("home")}
          className={`flex items-center gap-2 px-4 py-2 text-[14px] font-bold rounded-xl transition-all ${
            activeOutputId === "home"
              ? "bg-[var(--accent)]/10 text-[var(--accent)] shadow-sm"
              : "text-slate-500 hover:text-slate-300 hover:bg-white/5"
          }`}
        >
          <House size={14} />
          <span>Home</span>
        </button>

        {hasProgress && (
          <button
            onClick={() => activateOutputTab("progress")}
            className={`flex items-center gap-2 px-4 py-2 text-[14px] font-bold rounded-xl transition-all ${
              activeOutputId === "progress"
                ? "bg-[var(--accent)]/10 text-[var(--accent)] shadow-sm"
                : "text-slate-500 hover:text-slate-300 hover:bg-white/5"
            }`}
          >
            <Activity size={14} />
            <span>Progress</span>
          </button>
        )}

        <button
          onClick={() => activateOutputTab("overview")}
          className={`flex items-center gap-2 px-4 py-2 text-[14px] font-bold rounded-xl transition-all ${
            activeOutputId === "overview"
              ? "bg-[var(--accent)]/10 text-[var(--accent)] shadow-sm"
              : "text-slate-500 hover:text-slate-300 hover:bg-white/5"
          }`}
        >
          <LayoutDashboard size={14} />
          <span>Overview</span>
        </button>

        <div className="relative h-full flex items-center" ref={pmRef}>
          <button
            onClick={() => setPmOpen((open) => !open)}
            className={`flex items-center gap-2 px-4 py-2 text-[14px] font-bold rounded-xl transition-all ${
              isPmActive
                ? "bg-[var(--accent)]/10 text-[var(--accent)] shadow-sm"
                : "text-slate-500 hover:text-slate-300 hover:bg-white/5"
            }`}
          >
            <span>PM</span>
            {isPmActive && (
              <span className="text-[12px] opacity-60 ml-1">› {PM_LABELS[activeOutputId]}</span>
            )}
            <ChevronDown size={13} className={`transition-transform duration-300 ${pmOpen ? "rotate-180" : ""}`} />
          </button>

          {pmOpen && (
            <div 
              className="absolute top-full left-0 z-50 glass-panel rounded-xl shadow-2xl overflow-hidden min-w-[200px] border border-white/10"
            >
              <div className="py-2">{PM_TABS.map((id) => (
                <button
                  key={id}
                  onClick={() => { activateOutputTab(id); setPmOpen(false); }}
                  className={`block w-full text-left px-5 py-2.5 text-[14px] font-medium transition-colors ${
                    activeOutputId === id
                      ? "bg-[var(--accent)]/20 text-[var(--accent)]"
                      : "text-slate-400 hover:bg-white/5 hover:text-white"
                  }`}
                >
                  {PM_LABELS[id]}
                </button>
              ))}</div>
            </div>
          )}
        </div>

        {hasSaData && (
          <div className="relative h-full flex items-center" ref={saRef}>
            <button
              onClick={() => setSaOpen((open) => !open)}
              className={`flex items-center gap-2 px-4 py-2 text-[14px] font-bold rounded-xl transition-all ${
                isSaActive
                  ? "bg-[var(--accent)]/10 text-[var(--accent)] shadow-sm"
                  : "text-slate-500 hover:text-slate-300 hover:bg-white/5"
              }`}
            >
              <span>SA</span>
              {isSaActive && (
                <span className="text-[12px] opacity-60 ml-1">› {SA_LABELS[activeOutputId]}</span>
              )}
              <ChevronDown size={13} className={`transition-transform duration-300 ${saOpen ? "rotate-180" : ""}`} />
            </button>

            {saOpen && (
              <div 
                className="absolute top-full left-0 z-50 glass-panel rounded-xl shadow-2xl overflow-hidden min-w-[200px] border border-white/10"
              >
                <div className="py-2">{SA_TABS.map((id) => (
                  <button
                    key={id}
                    onClick={() => { activateOutputTab(id); setSaOpen(false); }}
                    className={`block w-full text-left px-5 py-2.5 text-[14px] font-medium transition-colors ${
                      activeOutputId === id
                        ? "bg-[var(--accent)]/20 text-[var(--accent)]"
                        : "text-slate-400 hover:bg-white/5 hover:text-white"
                    }`}
                  >
                    {SA_LABELS[id]}
                  </button>
                ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex-1 overflow-hidden">
        {renderViewport()}
      </div>
    </div>
  );
}
