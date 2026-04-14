/**
 * PM Agent Pipeline v2 — App (Root Layout)
 *
 * react-resizable-panels를 사용한 3단 분할 레이아웃:
 * - Left (20%): Sidebar — 파일 트리 + 설정
 * - Center (60%): Workspace — 코드 뷰어 + 결과 뷰어 (Two-Tier 탭)
 * - Right (20%): ChatPanel — AI 채팅 인터페이스
 *
 * 앱 마운트 시 Electron IPC로 백엔드 포트를 받아 WebSocket 연결을 수립한다.
 */

import React, { useEffect } from "react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import useAppStore from "./store/useAppStore";
import GlobalErrorBoundary from "./components/GlobalErrorBoundary";
import Sidebar from "./components/Sidebar";
import Workspace from "./components/Workspace";
import ChatPanel from "./components/ChatPanel";
import SessionPanel from "./components/SessionPanel";
import StatusBar from "./components/StatusBar";

export default function App() {
  const {
    isDarkMode,
    setBackendPort,
    connectWebSocket,
    fetchConfig,
  } = useAppStore();

  // ── 앱 마운트 시 백엔드 연결 ──────────
  useEffect(() => {
    async function initBackend() {
      let port = null;

      // Electron 환경: IPC로 포트 획득
      if (window.electronAPI) {
        port = await window.electronAPI.getBackendPort();
      }

      // 브라우저 개발 환경: 기본 포트 사용
      if (!port) {
        port = 8765;
      }

      console.log(`[App] Backend port: ${port}`);
      setBackendPort(port);
      connectWebSocket(port);
      // 백엔드 설정 동기화 (API 키 존재 여부, 기본 모델)
      fetchConfig(port);
    }

    initBackend();
  }, []);

  // ── 테마 동기화 (Electron TitleBarOverlay) ──
  useEffect(() => {
    if (window.electronAPI?.setTitleBarTheme) {
      // 윈도우 프레임 업데이트 안정성을 위해 아주 짧은 지연 후 호출
      const timer = setTimeout(() => {
        window.electronAPI.setTitleBarTheme(isDarkMode);
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [isDarkMode]);

  return (
    <div className={`h-screen w-screen flex flex-col overflow-hidden transition-colors duration-200 ${isDarkMode ? "dark bg-[var(--bg-primary)] text-[var(--text-primary)]" : "bg-[var(--bg-primary)] text-[var(--text-primary)]"}`}>
      <div className={`h-9 app-drag flex items-center border-b px-3 ${isDarkMode ? "border-[var(--border)] bg-[var(--bg-primary)]" : "border-[var(--border)] bg-[var(--bg-secondary)]"}`}>
        <span className={`text-[13px] tracking-wide ${isDarkMode ? "text-[var(--text-secondary)]" : "text-[var(--text-secondary)]"}`}>PM Agent Pipeline v2</span>
      </div>

      {/* ── 메인 3단 레이아웃 ──────────────── */}
      <div className="flex-1 overflow-hidden app-no-drag">
        <PanelGroup direction="horizontal">
          {/* Left Panel: Sidebar (20%) */}
          <Panel defaultSize={20} minSize={15} maxSize={30}>
            <Sidebar />
          </Panel>

          <PanelResizeHandle />

          {/* Center Panel: Workspace (60%) */}
          <Panel defaultSize={60} minSize={40}>
            <GlobalErrorBoundary>
              <Workspace />
            </GlobalErrorBoundary>
          </Panel>

          <PanelResizeHandle />

          {/* Right Panel: Chat + Sessions */}
          <Panel defaultSize={24} minSize={18} maxSize={38}>
            <div className="h-full min-h-0 flex border-l border-slate-700/50 bg-slate-900 overflow-hidden">
              <div className="flex-1 min-w-0 min-h-0 overflow-hidden">
                <ChatPanel />
              </div>
              <div className="w-56 border-l border-slate-700/50 min-w-0 min-h-0 overflow-hidden">
                <SessionPanel />
              </div>
            </div>
          </Panel>
        </PanelGroup>
      </div>

      {/* ── 하단 상태 바 ──────────────────── */}
      <div className="app-no-drag">
        <StatusBar />
      </div>
    </div>
  );
}
