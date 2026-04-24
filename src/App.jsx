import React, { useEffect, useState } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import useAppStore from "./store/useAppStore";
import GlobalErrorBoundary from "./components/GlobalErrorBoundary";
import Sidebar from "./components/Sidebar";
import ChatPanel from "./components/ChatPanel";
import CodeViewer from "./components/CodeViewer";
import ResultViewer from "./components/ResultViewer";
import HomeScreen from "./components/HomeScreen";
import PipelineProgress from "./components/PipelineProgress";
import StatusBar from "./components/StatusBar";
import SessionPanel from "./components/SessionPanel";
import SettingsPanel from "./components/SettingsPanel";

// Extracted Components
import TopBar from "./components/layout/TopBar";
import StudioCard from "./components/layout/StudioCard";
import PanelWrapper from "./components/layout/PanelWrapper";
import ToastContainer from "./components/ui/ToastContainer";
import { ICON_PANELS } from "./constants/uiConstants";

import {
  X, Code2, Bot, PanelRightClose, PanelRightOpen
} from "lucide-react";

export default function App() {
  const isDarkMode = useAppStore((state) => state.isDarkMode);
  const setBackendPort = useAppStore((state) => state.setBackendPort);
  const connectWebSocket = useAppStore((state) => state.connectWebSocket);
  const fetchConfig = useAppStore((state) => state.fetchConfig);
  const activeViewportTab = useAppStore((state) => state.activeViewportTab);
  const activateOutputTab = useAppStore((state) => state.activateOutputTab);
  const activateCodeTab = useAppStore((state) => state.activateCodeTab);
  const openFiles = useAppStore((state) => state.openFiles);
  const closeFile = useAppStore((state) => state.closeFile);
  const pipelineStatus = useAppStore((state) => state.pipelineStatus);
  const pipelineType = useAppStore((state) => state.pipelineType);
  const thinkingLog = useAppStore((state) => state.thinkingLog);
  const resultData = useAppStore((state) => state.resultData);
  const sa_artifacts = useAppStore((state) => state.sa_artifacts);

  const [activeIconPanel, setActiveIconPanel] = useState(null);
  const [showSessions, setShowSessions] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [isStudioOpen, setIsStudioOpen] = useState(true);
  const [showSidebarChat, setShowSidebarChat] = useState(false);

  const activeOutputId = activeViewportTab?.kind === "output" ? activeViewportTab.id : null;
  const isCodeView = activeViewportTab?.kind === "code";

  const SA_PIPELINE_TYPES = ["analysis_create", "analysis_reverse", "analysis_update"];
  const hasSaData = Boolean(sa_artifacts || resultData?.sa_output) ||
    (SA_PIPELINE_TYPES.includes(pipelineType) && pipelineStatus !== "idle");
  const hasProgress = pipelineStatus === "running" || pipelineStatus === "error" || thinkingLog.length > 0;

  useEffect(() => {
    async function initBackend() {
      let port = null;
      if (window.electronAPI) port = await window.electronAPI.getBackendPort();
      if (!port) port = 8765;
      setBackendPort(port);
      connectWebSocket(port);
      fetchConfig(port);
    }
    initBackend();
  }, []);

  useEffect(() => {
    if (window.electronAPI?.setTitleBarTheme) {
      const timer = setTimeout(() => window.electronAPI.setTitleBarTheme(isDarkMode), 100);
      return () => clearTimeout(timer);
    }
  }, [isDarkMode]);

  const handleIconPanel = (id) => {
    setActiveIconPanel((prev) => (prev === id ? null : id));
    setShowSessions(false);
    setShowSettingsModal(false);
  };

  const renderCenter = () => {
    if (showSessions) {
      return (
        <PanelWrapper title="세션" onClose={() => setShowSessions(false)}>
          <SessionPanel />
        </PanelWrapper>
      );
    }
    if (showSettingsModal) {
      return (
        <PanelWrapper title="설정" onClose={() => setShowSettingsModal(false)}>
          <SettingsPanel />
        </PanelWrapper>
      );
    }

    if (activeIconPanel) {
      if (activeIconPanel === "home") return <HomeScreen />;
      if (activeIconPanel === "progress") return <PipelineProgress />;
      
      const panel = ICON_PANELS.find(p => p.id === activeIconPanel);
      if (!panel) {
        setTimeout(() => setActiveIconPanel(null), 0);
        return <HomeScreen />;
      }

      return (
        <PanelWrapper title={panel.label || ""} onClose={() => setActiveIconPanel(null)}>
          <ResultViewer tabId={activeIconPanel} />
        </PanelWrapper>
      );
    }
    if (isCodeView) return <CodeViewer />;
    
    switch (activeOutputId) {
      case "progress": return <PipelineProgress />;
      case "home":
      default: return <HomeScreen />;
    }
  };

  return (
    <div className={`h-screen w-screen flex flex-col overflow-hidden ${!isDarkMode ? "light" : ""}`}
      style={{ background: "var(--bg-root)", color: "var(--text-primary)" }}>
      
      <TopBar
        activeOutputId={activeOutputId}
        activateOutputTab={activateOutputTab}
        hasProgress={hasProgress}
        hasSaData={hasSaData}
        resultData={resultData}
        showSessions={showSessions}
        setShowSessions={(v) => { setShowSessions(v); setShowSettingsModal(false); }}
        showSettings={showSettingsModal}
        setShowSettings={(v) => { setShowSettingsModal(v); setShowSessions(false); }}
      />

      <div className="flex-1 min-h-0 overflow-hidden flex app-no-drag">
        <PanelGroup direction="horizontal" className="h-full w-full min-h-0">
          <Panel defaultSize={15} minSize={10} maxSize={25}
            className="glass-panel border-r border-[var(--border)] border-t-0 border-b-0 border-l-0">
            <Sidebar />
          </Panel>

          <PanelResizeHandle />

          <Panel defaultSize={85} minSize={40} className="flex flex-col bg-transparent min-h-0">
            {openFiles.length > 0 && (
              <div className="flex items-center border-b border-[var(--border)] min-h-10 px-2 bg-[rgba(255,255,255,0.02)] shrink-0">
                <div className="flex items-center gap-0.5 overflow-x-auto w-full py-1">
                  {openFiles.map((file) => {
                    const isActive = activeViewportTab?.kind === "code" && activeViewportTab.id === file.id;
                    return (
                      <div
                        key={file.id}
                        className={`group flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-t cursor-pointer transition-colors shrink-0 ${isActive
                          ? "bg-[var(--accent)]/15 text-[var(--accent)] border-b-2 border-[var(--accent)]"
                          : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/5"
                          }`}
                        onClick={() => { activateCodeTab(file.id); setActiveIconPanel(null); }}
                      >
                        <Code2 size={11} />
                        <span className="truncate max-w-[140px] text-xs">{file.name}</span>
                        <button
                          onClick={(e) => { e.stopPropagation(); closeFile(file.id); }}
                          className="opacity-0 group-hover:opacity-100 hover:text-red-400 transition-opacity ml-1"
                        >
                          <X size={10} />
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            <div className="flex-1 min-h-0 overflow-hidden">
              <GlobalErrorBoundary>
                {renderCenter()}
              </GlobalErrorBoundary>
            </div>
          </Panel>
        </PanelGroup>

        <div
          className={`relative h-full flex flex-col border-l border-[var(--border)] overflow-hidden transition-all duration-250 ease-out ${isStudioOpen ? "w-[360px]" : "w-[72px]"
            } ${isDarkMode ? "bg-[#0F1219]" : "bg-transparent"}`}
        >
          <div className={`h-14 flex items-center justify-center shrink-0 border-b ${isDarkMode ? "border-white/5" : "border-[var(--border)]"
            } ${isStudioOpen ? "px-6 !justify-between" : "w-full"}`}>
            {isStudioOpen ? (
              <div className="flex flex-col">
                <span className="text-[10px] font-black text-blue-400 uppercase tracking-[0.3em]">Workbench</span>
                <h3 className={`text-[15px] font-black tracking-tight ${isDarkMode ? "text-gradient" : "text-blue-600"}`}>스튜디오</h3>
              </div>
            ) : null}
            <button
              onClick={() => {
                if (showSidebarChat) {
                  setShowSidebarChat(false);
                } else {
                  const newState = !isStudioOpen;
                  setIsStudioOpen(newState);
                  if (!newState) setShowSidebarChat(false);
                }
              }}
              className={`transition-all flex items-center justify-center rounded-xl ${isStudioOpen ? "w-10 h-10" : "w-full h-14"
                } ${isDarkMode ? "hover:bg-white/5 text-slate-400 hover:text-white" : "hover:bg-black/5 text-slate-600"
                }`}
            >
              {showSidebarChat ? (
                <X size={18} />
              ) : isStudioOpen ? (
                <PanelRightClose size={20} />
              ) : (
                <PanelRightOpen size={20} />
              )}
            </button>
          </div>

          <div className="flex-1 flex flex-col overflow-hidden relative">
            {isStudioOpen ? (
              <>
                {showSidebarChat ? (
                  <div className="flex-1 flex flex-col h-full bg-[#0F1219] absolute inset-0 z-10 shadow-[-10px_0_30px_rgba(0,0,0,0.3)]">
                    <div className="flex-1 min-h-0 relative">
                      <ChatPanel />
                    </div>
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col overflow-y-auto custom-scrollbar pb-24">
                    <div className="p-4 grid grid-cols-2 gap-3 shrink-0">
                      {ICON_PANELS.map((panel) => {
                        const isDisabled = false; // 항상 활성화
                        const isActive = activeIconPanel === panel.id;
                        return (
                          <StudioCard
                            key={panel.id}
                            {...panel}
                            isDarkMode={isDarkMode}
                            isActive={isActive}
                            isDisabled={isDisabled}
                            onClick={() => !isDisabled && handleIconPanel(panel.id)}
                          />
                        );
                      })}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="flex-1 flex flex-col items-center py-4 gap-4 w-full overflow-y-auto custom-scrollbar pb-24">
                <div className="w-10 border-t border-white/5 my-1" />
                {ICON_PANELS.map((panel) => {
                  const isDisabled = false; // 항상 활성화
                  const isActive = activeIconPanel === panel.id;
                  return (
                    <div key={panel.id} className="w-full flex justify-center">
                      <button
                        onClick={() => !isDisabled && handleIconPanel(panel.id)}
                        disabled={isDisabled}
                        title={panel.label}
                        className={`w-12 h-12 flex items-center justify-center rounded-xl transition-all ${isActive
                          ? "bg-[var(--accent)]/20 text-[var(--accent)] shadow-glow"
                          : isDisabled
                            ? "text-slate-700 opacity-20 cursor-not-allowed"
                            : "text-slate-500 hover:text-white hover:bg-white/10"
                          }`}
                      >
                        <panel.Icon size={20} />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}

            {!showSidebarChat && (
              <div className="absolute bottom-10 left-0 right-0 flex justify-center pointer-events-none z-50 animate-fade-in">
                <button
                  onClick={() => {
                    if (!isStudioOpen) {
                      setIsStudioOpen(true);
                      setShowSidebarChat(true);
                    } else {
                      setShowSidebarChat(true);
                    }
                  }}
                  className="pointer-events-auto flex items-center justify-center w-12 h-12 rounded-full transition-all hover:scale-110 shadow-[0_10px_30_rgba(0,0,0,0.5)] bg-gradient-to-tr from-blue-600 to-indigo-500 text-white"
                  title="AI 어시스턴트"
                >
                  <Bot size={24} className="drop-shadow-md" />
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="app-no-drag shrink-0">
        <StatusBar />
      </div>

      <ToastContainer />
    </div>
  );
}
