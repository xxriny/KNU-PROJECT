/**
 * NAVIGATOR — App (Root Layout)
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
  Clock3, Settings, PanelRightClose, PanelRightOpen,
  ChevronRight, Library, StickyNote, Bot, Trash2
} from "lucide-react";


// 우측 아이콘 패널 목록
const ICON_PANELS = [
  { id: "home", label: "Home", Icon: House, group: null, color: "text-white", bg: "bg-slate-500/10" },
  { id: "progress", label: "Progress", Icon: Activity, group: null, color: "text-yellow-400", bg: "bg-yellow-500/10" },
  { id: "rtm", label: "RTM", Icon: Table2, group: "pm", color: "text-cyan-400", bg: "bg-cyan-500/10" },
  { id: "stack", label: "Stack", Icon: Layers, group: "pm", color: "text-indigo-400", bg: "bg-indigo-500/10" },
  { id: "sa_components", label: "Components", Icon: Layers, group: "sa", color: "text-teal-400", bg: "bg-teal-500/10" },
  { id: "sa_api", label: "API Spec", Icon: Globe, group: "sa", color: "text-blue-400", bg: "bg-blue-500/10" },
  { id: "sa_db", label: "Database", Icon: Database, group: "sa", color: "text-rose-400", bg: "bg-rose-500/10" },
  { id: "memo", label: "Memos", Icon: StickyNote, group: null, color: "text-amber-300", bg: "bg-amber-500/10" },
  { id: "overview", label: "Report", Icon: FileText, group: null, color: "text-green-400", bg: "bg-green-500/10" },
];

const THEME_MAP = {
  slate: { bg: "bg-slate-50/50", activeBg: "bg-slate-100", text: "text-slate-700", activeText: "text-slate-900", border: "border-slate-100", iconBg: "bg-slate-500/10" },
  blue: { bg: "bg-blue-50/50", activeBg: "bg-blue-100/60", text: "text-blue-700", activeText: "text-blue-800", border: "border-blue-100", iconBg: "bg-blue-500/10" },
  sky: { bg: "bg-sky-50/50", activeBg: "bg-sky-100/60", text: "text-sky-600", activeText: "text-sky-800", border: "border-sky-100", iconBg: "bg-sky-500/10" },
  yellow: { bg: "bg-yellow-50/50", activeBg: "bg-yellow-100/60", text: "text-yellow-700", activeText: "text-yellow-800", border: "border-yellow-100", iconBg: "bg-yellow-500/10" },
  cyan: { bg: "bg-cyan-50/50", activeBg: "bg-cyan-100/60", text: "text-cyan-700", activeText: "text-cyan-800", border: "border-cyan-100", iconBg: "bg-cyan-500/10" },
  green: { bg: "bg-green-50/50", activeBg: "bg-green-100/60", text: "text-green-700", activeText: "text-green-800", border: "border-green-100", iconBg: "bg-green-500/10" },
  amber: { bg: "bg-amber-50/50", activeBg: "bg-amber-100/60", text: "text-amber-700", activeText: "text-amber-800", border: "border-amber-100", iconBg: "bg-amber-500/10" },
  indigo: { bg: "bg-indigo-50/50", activeBg: "bg-indigo-100/60", text: "text-indigo-700", activeText: "text-indigo-800", border: "border-indigo-100", iconBg: "bg-indigo-500/10" },
  teal: { bg: "bg-teal-50/50", activeBg: "bg-teal-100/60", text: "text-teal-700", activeText: "text-teal-800", border: "border-teal-100", iconBg: "bg-teal-500/10" },
  rose: { bg: "bg-rose-50/50", activeBg: "bg-rose-100/60", text: "text-rose-700", activeText: "text-rose-800", border: "border-rose-100", iconBg: "bg-rose-500/10" },
};

function StudioCard({ id, label, Icon, color, bg, isActive, isDisabled, onClick, isDarkMode }) {
  // 아이콘 색상 추출 및 보정
  let colorName = color.split("-")[1] || "slate";
  
  // Home(white)이나 특정 예외 처리
  if (id === "home") colorName = "slate";
  else if (id === "memo") colorName = "yellow";
  else if (id === "rtm") colorName = "sky";
  else if (id === "overview") colorName = "indigo";
  else if (id === "sa_overview") colorName = "amber";
  else if (colorName === "white") colorName = "slate";

  const theme = THEME_MAP[colorName] || THEME_MAP.slate;
  const themeColor = isDarkMode ? color : theme.text;

  return (
    <button
      onClick={onClick}
      disabled={isDisabled}
      className={`relative group flex flex-col items-start p-3.5 h-[90px] rounded-2xl border transition-all duration-300 ${isActive
        ? (isDarkMode 
            ? "bg-blue-600/15 border-blue-500/50 shadow-[0_0_20px_rgba(56,189,248,0.1)]" 
            : `${theme.activeBg} ${theme.border.replace("100", "300")} shadow-sm`)
        : isDisabled
          ? "opacity-10 grayscale cursor-not-allowed border-transparent"
          : isDarkMode 
            ? `bg-white/5 border-white/5 hover:bg-white/10` 
            : `${theme.bg} ${theme.border} hover:${theme.activeBg} hover:shadow-md`
        }`}
    >
      <div className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 mb-auto transition-transform group-hover:scale-110 ${
        isDarkMode ? bg : theme.iconBg.replace("500/10", "500/30")
      }`}>
        <Icon size={16} className={themeColor} />
      </div>

      <div className="w-full flex items-center justify-between gap-2 mt-2">
        <span className={`text-[13px] font-bold tracking-tight text-left leading-snug break-keep transition-colors ${
          isActive 
            ? (isDarkMode ? "text-blue-400" : theme.activeText) 
            : (isDarkMode ? "text-slate-200 group-hover:text-white" : theme.text)
        }`}>
          {label}
        </span>
        <ChevronRight size={14} className={`shrink-0 transition-transform group-hover:translate-x-1 ${
          isActive 
            ? (isDarkMode ? "text-blue-400" : theme.activeText) 
            : (isDarkMode ? "text-slate-600" : theme.text.replace("700", "400"))
        }`} />
      </div>

      {isActive && (
        <div className="absolute inset-0 rounded-2xl border border-blue-500/20 pointer-events-none" />
      )}
    </button>
  );
}

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
    userComments,
    addComment,
    syncMemos,
    projectFolder,
    selectedMode,
    selectAndScanFolder,
  } = useAppStore();


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

  // 아이콘 버튼 클릭: 같은 버튼 클릭 시 토글(닫기), 다른 버튼이면 전환
  const handleIconPanel = (id) => {
    setActiveIconPanel((prev) => (prev === id ? null : id));
    // 세션/설정 모달 닫기
    setShowSessions(false);
    setShowSettingsModal(false);
  };

  // 중앙 콘텐츠 렌더러
  const renderCenter = () => {
    // 세션 패널 우선 렌더링
    if (showSessions) {
      return (
        <PanelWrapper title="세션" onClose={() => setShowSessions(false)}>
          <SessionPanel />
        </PanelWrapper>
      );
    }
    // 설정 패널 우선 렌더링
    if (showSettingsModal) {
      return (
        <PanelWrapper title="설정" onClose={() => setShowSettingsModal(false)}>
          <SettingsPanel />
        </PanelWrapper>
      );
    }

    // 우측 아이콘 패널이 열려 있으면 → 그걸 중앙에 표시
    if (activeIconPanel) {
      if (activeIconPanel === "home") return <HomeScreen />;
      if (activeIconPanel === "progress") return <PipelineProgress />;
      return (
        <PanelWrapper title={ICON_PANELS.find(p => p.id === activeIconPanel)?.label || ""} onClose={() => setActiveIconPanel(null)}>
          <ResultViewer tabId={activeIconPanel} />
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
        setShowSessions={(v) => { setShowSessions(v); setShowSettingsModal(false); }}
        showSettings={showSettingsModal}
        setShowSettings={(v) => { setShowSettingsModal(v); setShowSessions(false); }}
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
        </PanelGroup>

        {/* Right: Studio Sidebar (Collapsible) */}
        <div
          className={`relative h-full flex flex-col border-l border-[var(--border)] overflow-hidden transition-all duration-250 ease-out ${isStudioOpen ? "w-[360px]" : "w-[72px]"
            } ${isDarkMode ? "bg-[#0F1219]" : "bg-transparent"}`}
        >
          {/* Studio Header */}
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

          {/* Studio Content */}
          <div className="flex-1 flex flex-col overflow-hidden relative">
            {isStudioOpen ? (
              <>
                {showSidebarChat ? (
                  /* Chat UI inside Sidebar */
                  <div className="flex-1 flex flex-col h-full bg-[#0F1219] absolute inset-0 z-10 shadow-[-10px_0_30px_rgba(0,0,0,0.3)]">
                    <div className="flex-1 min-h-0 relative">
                      <ChatPanel />
                    </div>
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col overflow-y-auto custom-scrollbar pb-24">
                    {/* Workbench Grid */}
                    <div className="p-4 grid grid-cols-2 gap-3 shrink-0">
                      {ICON_PANELS.map((panel) => {
                        const isDisabled = (panel.group === "pm" && !resultData) || (panel.group === "sa" && !hasSaData);
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
                  const isDisabled = (panel.group === "pm" && !resultData) || (panel.group === "sa" && !hasSaData);
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

            {/* Floating Bot FAB - Only visible when chat is closed */}
            {!showSidebarChat && (
              <div className="absolute bottom-10 left-0 right-0 flex justify-center pointer-events-none z-50 animate-in fade-in duration-300">
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

      {/* StatusBar */}
      <div className="app-no-drag shrink-0">
        <StatusBar />
      </div>
    </div>
  );
}

// ─── 중앙 패널 래퍼 (X 닫기 버튼 포함) ─────────────────
function PanelWrapper({ title, onClose, children }) {
  const { isDarkMode } = useAppStore();
  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--border)] shrink-0 bg-[rgba(255,255,255,0.02)]">
        <div className="flex items-center gap-2">
          <Library size={14} className="text-blue-400" />
          <span className="text-sm font-medium text-[var(--text-secondary)]">{title}</span>
        </div>
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
  const { isDarkMode, currentSessionId, sessions, updateSessionName } = useAppStore();
  const currentSession = sessions.find(s => s.id === currentSessionId);
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState("");

  useEffect(() => {
    if (currentSession) setEditValue(currentSession.name);
  }, [currentSession]);

  const handleRename = () => {
    if (editValue.trim() && currentSession) {
      updateSessionName(currentSessionId, editValue.trim());
    }
    setIsEditing(false);
  };

  return (
    <div className={`h-14 app-drag flex items-center px-6 gap-4 border-b border-[var(--border)] backdrop-blur-xl shrink-0 z-20 relative ${isDarkMode ? "bg-[rgba(19,23,31,0.9)]" : "bg-[rgba(255,255,255,0.9)]"
      }`}>
      {/* 로고 영역 */}
      <div className="flex items-center gap-3 shrink-0 app-no-drag">
        <span className="text-sm font-display font-black text-gradient tracking-[0.25em] select-none ml-2">
          NAVIGATOR
        </span>
      </div>

      <div className="w-px h-6 bg-[var(--border)] shrink-0 mx-2" />

      {/* 세션 이름 (좌측 정렬) */}
      <div className="flex-1 flex items-center app-no-drag overflow-hidden">
        {isEditing ? (
          <input
            autoFocus
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onBlur={handleRename}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleRename();
              if (e.key === "Escape") setIsEditing(false);
            }}
            className={`px-2 py-1 text-xl font-bold bg-transparent border-b-2 border-blue-500 outline-none w-full max-w-[600px] ${isDarkMode ? "text-white" : "text-slate-900"}`}
          />
        ) : (
          <div
            onDoubleClick={() => setIsEditing(true)}
            className={`group flex items-center gap-3 cursor-text px-3 py-1.5 rounded-xl transition-all hover:bg-white/5 truncate max-w-[800px]`}
            title="더블 클릭하여 별칭 수정"
          >
            <span className={`text-xl font-bold tracking-tight truncate ${isDarkMode ? "text-slate-100" : "text-slate-800"}`}>
              {currentSession?.name || "새 프로젝트 세션"}
            </span>
            <div className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center">
              <ChevronRight size={16} className="text-blue-500/50" />
            </div>
          </div>
        )}
      </div>

      {/* 세션 & 설정 버튼 (우측 윈도우 컨트롤러 140px 여백 확보) */}
      <div className="flex items-center gap-2 app-no-drag shrink-0 mr-[140px]">
        <button
          onClick={() => setShowSessions(!showSessions)}
          className={`flex items-center gap-2 px-4 py-2 text-[13px] font-bold rounded-xl border transition-all ${showSessions
            ? "bg-blue-500/10 border-blue-500/30 text-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.1)]"
            : `border-[var(--border)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] ${isDarkMode ? "hover:bg-white/10" : "hover:bg-black/5"}`
            }`}
        >
          <Library size={16} />
          <span>라이브러리</span>
        </button>
        <button
          onClick={() => setShowSettings(!showSettings)}
          className={`flex items-center gap-2 px-4 py-2 text-[13px] font-bold rounded-xl border transition-all ${showSettings
            ? "bg-blue-500/10 border-blue-500/30 text-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.1)]"
            : `border-[var(--border)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] ${isDarkMode ? "hover:bg-white/10" : "hover:bg-black/5"}`
            }`}
        >
          <Settings size={16} />
          <span>설정</span>
        </button>
      </div>
    </div>
  );
}
