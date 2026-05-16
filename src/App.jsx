import React, { useEffect, useState } from "react";
import useAppStore from "./store/useAppStore";
import GlobalErrorBoundary from "./components/GlobalErrorBoundary";
import ChatPanel from "./components/ChatPanel";
import ResultViewer from "./components/ResultViewer";
import HomeScreen from "./components/HomeScreen";
import PipelineProgress from "./components/PipelineProgress";
import StatusBar from "./components/StatusBar";
import SessionPanel from "./components/SessionPanel";
import SettingsPanel from "./components/SettingsPanel";
import LoginScreen from "./components/auth/LoginScreen";

// Extracted Components
import TopBar from "./components/layout/TopBar";
import StudioCard from "./components/layout/StudioCard";
import PanelWrapper from "./components/layout/PanelWrapper";
import ToastContainer from "./components/ui/ToastContainer";
import { ICON_PANELS } from "./constants/uiConstants";

import {
  X, Bot, PanelRightClose, PanelRightOpen
} from "lucide-react";

export default function App() {
  const isDarkMode = useAppStore((state) => state.isDarkMode);
  const setBackendPort = useAppStore((state) => state.setBackendPort);
  const connectWebSocket = useAppStore((state) => state.connectWebSocket);
  const fetchConfig = useAppStore((state) => state.fetchConfig);
  const activeViewportTab = useAppStore((state) => state.activeViewportTab);
  const activateOutputTab = useAppStore((state) => state.activateOutputTab);
  const pipelineStatus = useAppStore((state) => state.pipelineStatus);
  const pipelineType = useAppStore((state) => state.pipelineType);
  const thinkingLog = useAppStore((state) => state.thinkingLog);
  const resultData = useAppStore((state) => state.resultData);
  const sa_artifacts = useAppStore((state) => state.sa_artifacts);

  const authToken = useAppStore((state) => state.authToken);
  const authChecked = useAppStore((state) => state.authChecked);
  const hasUsers = useAppStore((state) => state.hasUsers);
  const checkAuthStatus = useAppStore((state) => state.checkAuthStatus);

  const [activeIconPanel, setActiveIconPanel] = useState(null);
  const [showSessions, setShowSessions] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [isStudioOpen, setIsStudioOpen] = useState(true);
  const [showSidebarChat, setShowSidebarChat] = useState(false);

  const activeOutputId = activeViewportTab?.kind === "output" ? activeViewportTab.id : null;

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
      // auth 상태 체크는 backendPort 설정 후 별도 호출
      setTimeout(() => checkAuthStatus(), 300);
    }
    initBackend();
  }, []);

  useEffect(() => {
    if (window.electronAPI?.setTitleBarTheme) {
      const timer = setTimeout(() => window.electronAPI.setTitleBarTheme(isDarkMode), 100);
      return () => clearTimeout(timer);
    }
  }, [isDarkMode]);

  // 분석이 시작되면 메모/세션/설정 등 활성 패널을 강제로 닫고 메인 viewport(Progress)를 노출.
  // store의 activateOutputTab만으로는 App의 로컬 state(activeIconPanel)를 끄지 못하므로
  // 여기서 보강. (Memos 탭 → "지적사항 반영 업데이트" 클릭 시 progress로 자동 전환되도록.)
  useEffect(() => {
    if (pipelineStatus === "running") {
      setActiveIconPanel(null);
      setShowSessions(false);
      setShowSettingsModal(false);
    }
  }, [pipelineStatus]);

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
    switch (activeOutputId) {
      case "progress": return <PipelineProgress />;
      case "home":
      default: return <HomeScreen />;
    }
  };

  // 인증 체크 전 — 백엔드 응답 대기 중 앱 접근 차단
  if (!authChecked) {
    return (
      <div className="h-screen w-screen flex items-center justify-center"
        style={{ background: "var(--bg-root)" }}>
        <div className="flex flex-col items-center gap-3 opacity-40">
          <div className="w-8 h-8 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
          <span className="text-sm font-medium">초기화 중...</span>
        </div>
      </div>
    );
  }

  // 인증 체크 완료 후 토큰 없으면 항상 LoginScreen 표시
  // hasUsers === null (백엔드 미응답)도 로그인 화면으로 처리
  if (authChecked && !authToken) {
    return <LoginScreen isFirstRun={hasUsers === false} />;
  }

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
        <div className="flex-1 flex flex-col bg-transparent min-h-0 overflow-hidden">
          <div className="flex-1 min-h-0 overflow-hidden">
            <GlobalErrorBoundary>
              {renderCenter()}
            </GlobalErrorBoundary>
          </div>
        </div>

        <div
          className={`relative h-full flex flex-col border-l border-[var(--border)] overflow-hidden transition-all duration-250 ease-out ${isStudioOpen ? "w-[360px]" : "w-[72px]"
            } ${isDarkMode ? "bg-[#0F1219]" : "bg-transparent"}`}
        >
          <div className={`h-14 flex items-center justify-center shrink-0 border-b ${isDarkMode ? "border-white/5" : "border-[var(--border)]"
            } ${isStudioOpen ? "px-6 !justify-between" : "w-full"}`}>
            {isStudioOpen ? (
              <div className="flex flex-col">
                <span className="text-[10px] font-black text-blue-400 uppercase tracking-[0.3em]">Workbench</span>
                <h3 className={`text-[15px] font-black tracking-tight ${isDarkMode ? "text-gradient" : "text-blue-600"}`}>STUDIO</h3>
              </div>
            ) : null}
            <button
              onClick={() => setIsStudioOpen((prev) => !prev)}
              className={`transition-all flex items-center justify-center rounded-xl ${isStudioOpen ? "w-10 h-10" : "w-full h-14"
                } ${isDarkMode ? "hover:bg-white/5 text-slate-400 hover:text-white" : "hover:bg-black/5 text-slate-600"
                }`}
            >
              {isStudioOpen ? (
                <PanelRightClose size={20} />
              ) : (
                <PanelRightOpen size={20} />
              )}
            </button>
          </div>

          <div className="flex-1 flex flex-col overflow-hidden relative">
            {isStudioOpen ? (
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
                  onClick={() => setShowSidebarChat(true)}
                  className="pointer-events-auto flex items-center justify-center w-12 h-12 rounded-full transition-all hover:scale-110 shadow-[0_10px_30_rgba(0,0,0,0.5)] bg-gradient-to-tr from-blue-600 to-indigo-500 text-white"
                  title="AI 어시스턴트"
                >
                  <Bot size={24} className="drop-shadow-md" />
                </button>
              </div>
            )}
          </div>
        </div>

        {showSidebarChat && (
          <div
            className={`fixed bottom-16 right-6 z-[60] flex flex-col rounded-2xl border overflow-hidden animate-fade-in
              w-[340px] h-[500px] max-h-[calc(100vh-7rem)]
              ${isDarkMode
                ? "bg-[#0F1219] border-white/10 shadow-[0_20px_60px_rgba(0,0,0,0.55)]"
                : "bg-white border-[var(--border)] shadow-[0_20px_60px_rgba(15,23,42,0.18)]"}`}
            role="dialog"
            aria-label="AI 어시스턴트"
          >
            <div className={`h-12 shrink-0 flex items-center justify-between px-4 border-b ${isDarkMode ? "border-white/5" : "border-[var(--border)]"}`}>
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center">
                  <Bot size={15} className="text-white" />
                </div>
                <div className="flex flex-col leading-tight">
                  <span className="text-[10px] font-black text-blue-400 uppercase tracking-[0.25em]">Assistant</span>
                  <span className={`text-[13px] font-bold ${isDarkMode ? "text-white" : "text-slate-800"}`}>AI Navigator</span>
                </div>
              </div>
              <button
                onClick={() => setShowSidebarChat(false)}
                className={`w-8 h-8 flex items-center justify-center rounded-lg transition-colors ${isDarkMode ? "hover:bg-white/5 text-slate-400 hover:text-white" : "hover:bg-black/5 text-slate-500 hover:text-slate-800"}`}
                title="닫기"
              >
                <X size={16} />
              </button>
            </div>
            <div className="flex-1 min-h-0 flex flex-col">
              <ChatPanel />
            </div>
          </div>
        )}
      </div>

      <div className="app-no-drag shrink-0">
        <StatusBar />
      </div>

      <ToastContainer />
    </div>
  );
}
