/**
 * PM Agent Pipeline v2 — App (Root Layout)
 *
 * 레이아웃:
 * ┌─────────────────────────────────────────────────────┐
 * │  TopBar: [● ● ●] [Title] [Nav Tabs]     [Session][Settings] │
 * ├──────────┬──────────────────────────────────┬───────┤
 * │  File    │         Center Viewport           │ Icon  │
 * │  Tree    │  (Home/Progress/Code/Result/Chat) │  Bar  │
 * ├──────────┴──────────────────────────────────┴───────┤
 * │  StatusBar                                          │
 * └─────────────────────────────────────────────────────┘
 */

import React, { useEffect, useState, useRef } from "react";
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
import {
  MessageSquare, LayoutDashboard, Table2, FileText,
  ShieldCheck, Layers, Globe, Database,
  House, Activity, ChevronDown, Code2, X,
  Clock3, Settings,
} from "lucide-react";

// 우측 아이콘 패널 목록
const ICON_PANELS = [
  { id: "chat", label: "AI 채팅", Icon: MessageSquare, group: null },
  { id: "overview", label: "Overview", Icon: LayoutDashboard, group: "pm" },
  { id: "rtm", label: "RTM & Stack", Icon: Table2, group: "pm" },
  { id: "context", label: "PM Report", Icon: FileText, group: "pm" },
  { id: "sa_overview", label: "QA Report", Icon: ShieldCheck, group: "sa" },
  { id: "sa_components", label: "Components", Icon: Layers, group: "sa" },
  { id: "sa_api", label: "API Spec", Icon: Globe, group: "sa" },
  { id: "sa_db", label: "Database", Icon: Database, group: "sa" },
];

export default function App() {
  const {
    isDarkMode,
    setBackendPort,
    connectWebSocket,
    fetchConfig,
    activeViewportTab,
    activateOutputTab,
    activateCodeTab,
    openFiles,
    closeFile,
    pipelineStatus,
    pipelineType,
    thinkingLog,
    resultData,
    sa_artifacts,
  } = useAppStore();


  const [activeIconPanel, setActiveIconPanel] = useState(null);
  const [showSessions, setShowSessions] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);

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

  // 아이콘 버튼 클릭: 같은 버튼 클릭 시 토글(닫기), 다른 버튼이면 전환
  const handleIconPanel = (id) => {
    setActiveIconPanel((prev) => (prev === id ? null : id));
    // 세션/설정 모달 닫기
    setShowSessions(false);
    setShowSettingsModal(false);
  };

  // 중앙 콘텐츠 렌더러
  const renderCenter = () => {
    // 우측 아이콘 패널이 열려 있으면 → 그걸 중앙에 표시
    if (activeIconPanel) {
      if (activeIconPanel === "chat") {
        return (
          <PanelWrapper title="AI 채팅" onClose={() => setActiveIconPanel(null)}>
            <ChatPanel />
          </PanelWrapper>
        );
      }
      if (showSessions) {
        return (
          <PanelWrapper title="세션" onClose={() => setShowSessions(false)}>
            <SessionPanel />
          </PanelWrapper>
        );
      }
      return (
        <PanelWrapper title={ICON_PANELS.find(p => p.id === activeIconPanel)?.label || ""} onClose={() => setActiveIconPanel(null)}>
          <ResultViewer tabId={activeIconPanel} />
        </PanelWrapper>
      );
    }
    // 세션 패널
    if (showSessions) {
      return (
        <PanelWrapper title="세션" onClose={() => setShowSessions(false)}>
          <SessionPanel />
        </PanelWrapper>
      );
    }
    // 설정 패널
    if (showSettingsModal) {
      return (
        <PanelWrapper title="설정" onClose={() => setShowSettingsModal(false)}>
          <SettingsPanel />
        </PanelWrapper>
      );
    }
    // 코드 뷰어
    if (isCodeView) return <CodeViewer />;
    // 기본 탭 콘텐츠
    switch (activeOutputId) {
      case "progress": return <PipelineProgress />;
      case "home":
      default: return <HomeScreen />;
    }
  };

  return (
    <div className={`h-screen w-screen flex flex-col overflow-hidden ${!isDarkMode ? "light" : ""}`}
      style={{ background: "var(--bg-root)", color: "var(--text-primary)" }}>
      {/* TopBar */}
      <TopBar
        activeOutputId={activeOutputId}
        activateOutputTab={activateOutputTab}
        hasProgress={hasProgress}
        hasSaData={hasSaData}
        resultData={resultData}
        showSessions={showSessions}
        setShowSessions={(v) => { setShowSessions(v); setActiveIconPanel(null); setShowSettingsModal(false); }}
        showSettings={showSettingsModal}
        setShowSettings={(v) => { setShowSettingsModal(v); setActiveIconPanel(null); setShowSessions(false); }}
      />

      {/* 메인 영역 */}
      <div className="flex-1 min-h-0 overflow-hidden flex app-no-drag">
        <PanelGroup direction="horizontal" className="h-full w-full min-h-0">

          {/* Left: 파일 트리 */}
          <Panel defaultSize={15} minSize={10} maxSize={25}
            className="glass-panel border-r border-[var(--border)] border-t-0 border-b-0 border-l-0">
            <Sidebar />
          </Panel>

          <PanelResizeHandle />

          {/* Center: 메인 뷰포트 */}
          <Panel defaultSize={85} minSize={40} className="flex flex-col bg-transparent min-h-0">
            {/* 코드 파일 탭바 (열린 파일 있을 때만) */}
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

            {/* 메인 콘텐츠 */}
            <div className="flex-1 min-h-0 overflow-hidden">
              <GlobalErrorBoundary>
                {renderCenter()}
              </GlobalErrorBoundary>
            </div>
          </Panel>

          {/* Right: 세로 아이콘 바 */}
          <div className="flex flex-col items-center py-3 gap-1 border-l border-[var(--border)] bg-[rgba(255,255,255,0.02)] w-12 shrink-0">
            {/* PM 그룹 구분선 */}
            <div className="w-6 border-t border-[var(--border)] my-1" />
            {ICON_PANELS.map(({ id, label, Icon, group }) => {
              const isDisabled = (group === "pm" && !resultData) || (group === "sa" && !hasSaData);
              const isActive = activeIconPanel === id;
              return (
                <button
                  key={id}
                  onClick={() => !isDisabled && handleIconPanel(id)}
                  disabled={isDisabled}
                  title={label}
                  className={`w-9 h-9 flex items-center justify-center rounded-lg transition-all ${isActive
                      ? "bg-[var(--accent)]/20 text-[var(--accent)] shadow-[0_0_8px_rgba(56,189,248,0.3)]"
                      : isDisabled
                        ? "text-[var(--text-muted)] opacity-30 cursor-not-allowed"
                        : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/10"
                    }`}
                >
                  <Icon size={15} />
                </button>
              );
            })}
          </div>
        </PanelGroup>
      </div>

      {/* StatusBar */}
      <div className="app-no-drag shrink-0">
        <StatusBar />
      </div>
    </div>
  );
}

// ─── 중앙 패널 래퍼 (X 닫기 버튼 포함) ─────────────────
function PanelWrapper({ title, onClose, children }) {
  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--border)] shrink-0 bg-[rgba(255,255,255,0.02)]">
        <span className="text-sm font-medium text-[var(--text-secondary)]">{title}</span>
        <button
          onClick={onClose}
          className="p-1.5 rounded-md text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/10 transition-colors"
        >
          <X size={14} />
        </button>
      </div>
      <div className="flex-1 min-h-0 overflow-auto">
        {children}
      </div>
    </div>
  );
}

// ─── TopBar ─────────────────────────────────────────────
function TopBar({
  activeOutputId, activateOutputTab,
  hasProgress, hasSaData, resultData,
  showSessions, setShowSessions,
  showSettings, setShowSettings,
}) {
  const { isDarkMode } = useAppStore();
  const [pmOpen, setPmOpen] = useState(false);
  const [saOpen, setSaOpen] = useState(false);
  const pmRef = useRef(null);
  const saRef = useRef(null);

  const PM_TABS = [
    { id: "overview", label: "Overview" },
    { id: "rtm", label: "RTM & Stack" },
    { id: "context", label: "PM Report" },
  ];
  const SA_TABS = [
    { id: "sa_overview", label: "QA Report" },
    { id: "sa_components", label: "Components" },
    { id: "sa_api", label: "API Spec" },
    { id: "sa_db", label: "Database" },
  ];

  const isPmActive = PM_TABS.some(t => t.id === activeOutputId);
  const isSaActive = SA_TABS.some(t => t.id === activeOutputId);

  // 외부 클릭 시 드롭다운 닫기
  useEffect(() => {
    const handler = (e) => {
      if (pmRef.current && !pmRef.current.contains(e.target)) setPmOpen(false);
      if (saRef.current && !saRef.current.contains(e.target)) setSaOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const NavBtn = ({ id, label, active, onClick, disabled }) => (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`flex items-center gap-1 px-3 py-1 text-[13px] rounded-md transition-colors disabled:opacity-30 disabled:cursor-not-allowed ${active
          ? "bg-[var(--accent)]/15 text-[var(--accent)] font-semibold"
          : `text-[var(--text-secondary)] hover:text-[var(--text-primary)] ${isDarkMode ? "hover:bg-white/8" : "hover:bg-black/5"}`
        }`}
    >
      {label}
    </button>
  );

  return (
    <div className={`h-10 app-drag flex items-center px-3 gap-2 border-b border-[var(--border)] backdrop-blur-xl shrink-0 z-20 relative ${isDarkMode ? "bg-[rgba(14,21,33,0.8)]" : "bg-[rgba(255,255,255,0.85)]"
      }`}>
      {/* macOS 신호등 */}
      <div className="flex items-center gap-1.5 app-no-drag shrink-0">
        <div className="w-3 h-3 rounded-full bg-red-500/90" />
        <div className="w-3 h-3 rounded-full bg-yellow-500/90" />
        <div className="w-3 h-3 rounded-full bg-green-500/90" />
      </div>

      {/* 앱 타이틀 */}
      <span className="text-xs font-display font-semibold text-gradient tracking-wide shrink-0 select-none ml-1">
        PM Agent Pipeline v2
      </span>

      <div className="w-px h-5 bg-[var(--border)] shrink-0 mx-1" />

      {/* 네비게이션 탭들 — 중앙 */}
      <div className="flex items-center gap-0.5 app-no-drag overflow-x-auto">
        <NavBtn id="home" label="Home" icon={<House size={11} />}
          active={activeOutputId === "home" && !showSessions && !showSettings}
          onClick={() => activateOutputTab("home")} />
        {hasProgress && (
          <NavBtn id="progress" label="Progress"
            active={activeOutputId === "progress"}
            onClick={() => activateOutputTab("progress")} />
        )}

        {/* PM 드롭다운 */}
        <div className="relative app-no-drag" ref={pmRef}>
          <button
            onClick={() => { setPmOpen(v => !v); setSaOpen(false); }}
            disabled={!resultData}
            className={`flex items-center gap-1 px-3 py-1 text-[13px] rounded-md transition-colors disabled:opacity-30 disabled:cursor-not-allowed ${pmOpen || isPmActive
                ? "bg-[var(--accent)]/15 text-[var(--accent)]"
                : `text-[var(--text-secondary)] hover:text-[var(--text-primary)] ${isDarkMode ? "hover:bg-white/8" : "hover:bg-black/5"}`
              }`}
          >
            PM <ChevronDown size={11} className={`transition-transform ${pmOpen ? "rotate-180" : ""}`} />
          </button>
          {pmOpen && (
            <div className="absolute top-full left-0 mt-1 z-50 glass-card rounded-lg shadow-2xl overflow-hidden min-w-[140px] py-1">
              {PM_TABS.map(t => (
                <button key={t.id}
                  onClick={() => { activateOutputTab(t.id); setPmOpen(false); }}
                  className={`block w-full text-left px-4 py-2 text-xs transition-colors ${activeOutputId === t.id
                      ? "bg-[var(--bg-hover)] text-[var(--accent)]"
                      : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
                    }`}
                >{t.label}</button>
              ))}
            </div>
          )}
        </div>

        {/* SA 드롭다운 */}
        {hasSaData && (
          <div className="relative app-no-drag" ref={saRef}>
            <button
              onClick={() => { setSaOpen(v => !v); setPmOpen(false); }}
              className={`flex items-center gap-1 px-3 py-1 text-[13px] rounded-md transition-colors ${saOpen || isSaActive
                  ? "bg-[var(--accent)]/15 text-[var(--accent)]"
                  : `text-[var(--text-secondary)] hover:text-[var(--text-primary)] ${isDarkMode ? "hover:bg-white/8" : "hover:bg-black/5"}`
                }`}
            >
              SA <ChevronDown size={11} className={`transition-transform ${saOpen ? "rotate-180" : ""}`} />
            </button>
            {saOpen && (
              <div className="absolute top-full left-0 mt-1 z-50 glass-card rounded-lg shadow-2xl overflow-hidden min-w-[140px] py-1">
                {SA_TABS.map(t => (
                  <button key={t.id}
                    onClick={() => { activateOutputTab(t.id); setSaOpen(false); }}
                    className={`block w-full text-left px-4 py-2 text-xs transition-colors ${activeOutputId === t.id
                        ? "bg-[var(--bg-hover)] text-[var(--accent)]"
                        : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
                      }`}
                  >{t.label}</button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex-1" />

      {/* 세션 & 설정 버튼 (우측 윈도우 컨트롤러 140px 여백 확보) */}
      <div className="flex items-center gap-1 app-no-drag shrink-0 mr-[140px]">
        <button
          onClick={() => setShowSessions(!showSessions)}
          className={`flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md border transition-all ${showSessions
              ? "bg-[var(--accent)]/15 border-[var(--accent)]/40 text-[var(--accent)]"
              : `border-[var(--border)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] ${isDarkMode ? "hover:bg-white/8" : "hover:bg-black/5"}`
            }`}
        >
          <Clock3 size={11} />
          <span>세션</span>
        </button>
        <button
          onClick={() => setShowSettings(!showSettings)}
          className={`flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md border transition-all ${showSettings
              ? "bg-[var(--accent)]/15 border-[var(--accent)]/40 text-[var(--accent)]"
              : `border-[var(--border)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] ${isDarkMode ? "hover:bg-white/8" : "hover:bg-black/5"}`
            }`}
        >
          <Settings size={11} />
          <span>설정</span>
        </button>
      </div>
    </div>
  );
}
