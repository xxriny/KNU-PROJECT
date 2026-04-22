/**
 * NAVIGATOR — Global State (Zustand)
 *
 * 관리하는 핵심 상태:
 * 1. 백엔드 연결 (WebSocket 세션, 포트, 상태)
 * 2. 중앙 공유 뷰포트 탭 상태
 * 3. 열려있는 코드 파일 목록
 * 4. 파이프라인 산출물 데이터
 * 5. 채팅 히스토리
 * 6. 세션 스냅샷
 */

import { create } from "zustand";
import {
  DEFAULT_VIEWPORT_TAB,
  MODE_TO_ACTION_TYPE,
  MODE_TO_PIPELINE_TYPE,
  EMPTY_RESULT_FIELDS,
  normalizeMode,
  loadSessions,
  persistSessions,
  cloneViewportTab,
  normalizeOutputTabId,
  extractRunId,
  inferPipelineTypeFromResult,
  spreadResultData,
} from "./storeHelpers";
import { createWsSlice } from "./slices/wsSlice";
import { createConfigSlice } from "./slices/configSlice";
import { debounce } from "./debounce";

const useAppStore = create((set, get) => {
  const debouncedSave = debounce(() => get().saveCurrentSession(), 500);

  // 초기 테마 로드 (기본값 다크)
  const savedTheme = localStorage.getItem("theme");
  const initialDarkMode = savedTheme ? savedTheme === "dark" : true;

  return {
    isDarkMode: initialDarkMode,
    setDarkMode: (isDark) => {
      set({ isDarkMode: isDark });
      localStorage.setItem("theme", isDark ? "dark" : "light");
    },
    toggleDarkMode: () => {
      const nextDark = !get().isDarkMode;
      get().setDarkMode(nextDark);
    },
    ...createWsSlice(set, get),
    ...createConfigSlice(set, get),

    _handleWsMessage: (msg) => {
      const { type, node, data } = msg;

      switch (type) {
        case "status":
          set((state) => ({
            pipelineNodes: {
              ...state.pipelineNodes,
              [node]: data.status,
            },
          }));
          debouncedSave();
          break;

        case "thinking":
          set((state) => ({
            thinkingLog: [
              ...state.thinkingLog,
              { node, text: data.text, timestamp: Date.now() },
            ],
          }));
          debouncedSave();
          break;

        case "result":
          get()._processResult(data, node);
          break;

        case "error":
          set({
            pipelineStatus: "error",
            pipelineError: data.message,
          });
          debouncedSave();
          break;

        case "pong":
          break;

        default:
          console.warn("[WS] Unknown message type:", type);
      }
    },

    // ═══════════════════════════════════════
    //  파이프라인 실행 상태
    // ═══════════════════════════════════════
    pipelineStatus: "idle",
    pipelineError: null,
    pipelineNodes: {},
    thinkingLog: [],
    pipelineType: "analysis",

    setPipelineStatus: (status) => set({ pipelineStatus: status }),
    setSelectedMode: (selectedMode) => set({ selectedMode: normalizeMode(selectedMode) }),

    startAnalysis: (idea, context = "", apiKey = "", model = "gemini-2.5-flash", selectedMode = "create") => {
      const normalizedMode = normalizeMode(selectedMode);
      const sourceDir = get().projectFolder || "";
      get().createSession();
      set({
        pipelineStatus: "running",
        pipelineError: null,
        pipelineNodes: {},
        thinkingLog: [],
        pipelineType: MODE_TO_PIPELINE_TYPE[normalizedMode] || "analysis_create",
        ...EMPTY_RESULT_FIELDS,
        chatHistory: [],
        chatInput: "",
        selectedMode: normalizedMode,
        activeViewportTab: { kind: "output", id: "progress" },
        lastOutputTab: "progress",
      });
      debouncedSave();
      get().sendWsMessage("analyze", {
        idea,
        context,
        api_key: apiKey,
        model,
        action_type: MODE_TO_ACTION_TYPE[normalizedMode],
        source_dir: sourceDir,
      });
    },

    startRevision: (userRequest, apiKey = "", model = "gemini-2.5-flash") => {
      const { resultData, chatHistory } = get();
      set({
        pipelineStatus: "running",
        pipelineError: null,
        pipelineNodes: {},
        thinkingLog: [],
        pipelineType: "revision",
        activeViewportTab: { kind: "output", id: "progress" },
        lastOutputTab: "progress",
      });
      debouncedSave();
      get().sendWsMessage("revise", {
        user_request: userRequest,
        previous_result: resultData || {},
        chat_history: chatHistory,
        api_key: apiKey,
        model,
      });
    },

    sendIdeaChat: (message, apiKey = "", model = "gemini-2.5-flash") => {
      const { chatHistory, resultData } = get();
      set({ pipelineType: "idea_chat" });
      get().sendWsMessage("idea_chat", {
        message,
        chat_history: chatHistory,
        previous_result: resultData || {},
        api_key: apiKey,
        model,
      });
    },

    // ═══════════════════════════════════════
    //  산출물 데이터
    // ═══════════════════════════════════════
    resultData: null,
    requirements_rtm: [],
    semantic_graph: null,
    context_spec: null,
    sa_reverse_context: null,
    sa_output: null,
    sa_artifacts: null,
    system_scan: null,
    sa_phase2: null,
    sa_phase3: null,
    sa_phase4: null,
    sa_phase5: null,
    sa_phase6: null,
    sa_phase7: null,
    sa_phase8: null,
    metadata: null,
    selectedMode: "create",

    // ── 디버그 시스템 ──
    debugLogs: [],
    addDebugLog: (log) => set((state) => ({
      debugLogs: [{ ...log, timestamp: Date.now() }, ...state.debugLogs].slice(0, 50)
    })),
    clearDebugLogs: () => set({ debugLogs: [] }),

    _processResult: (data, node = "complete") => {
      if (node === "idea_chat") {
        const reply = data.chat_reply || data.assistant_message || data.message || "";
        if (reply) {
          set((state) => ({
            chatHistory: [...state.chatHistory, { role: "assistant", content: reply }],
          }));
          debouncedSave();
        }
        return;
      }

      set({
        pipelineStatus: "done",
        pipelineType: inferPipelineTypeFromResult(data),
        ...spreadResultData(data),
        chatHistory: data.chat_history || get().chatHistory,
        activeViewportTab: { kind: "output", id: "overview" },
        lastOutputTab: "overview",
      });
      debouncedSave();
    },

    // ═══════════════════════════════════════
    //  공유 뷰포트 탭 관리
    // ═══════════════════════════════════════
    activeViewportTab: { ...DEFAULT_VIEWPORT_TAB },
    lastOutputTab: "home",
    openFiles: [],

    activateCodeTab: (tabId) => set({ activeViewportTab: { kind: "code", id: tabId } }),

    activateOutputTab: (tabId) => set({
      activeViewportTab: { kind: "output", id: tabId },
      lastOutputTab: tabId,
    }),

    openFile: (file) => {
      const { openFiles } = get();
      const exists = openFiles.find((entry) => entry.id === file.id);
      const nextFiles = exists
        ? openFiles.map((entry) => (entry.id === file.id ? { ...entry, ...file } : entry))
        : [...openFiles, file];

      set({
        openFiles: nextFiles,
        selectedFile: file,
        activeViewportTab: { kind: "code", id: file.id },
      });
      debouncedSave();
    },

    updateOpenFileContent: (fileId, content) => {
      set((state) => {
        const nextFiles = state.openFiles.map((file) => (
          file.id === fileId ? { ...file, content } : file
        ));
        const nextSelectedFile = state.selectedFile?.id === fileId
          ? { ...state.selectedFile, content }
          : state.selectedFile;

        return {
          openFiles: nextFiles,
          selectedFile: nextSelectedFile,
        };
      });
    },

    closeFile: (fileId) => {
      const { openFiles, activeViewportTab, lastOutputTab, resultData } = get();
      const filtered = openFiles.filter((file) => file.id !== fileId);
      const fallbackOutput = resultData ? "overview" : (lastOutputTab || "home");

      let nextViewport = activeViewportTab;
      if (activeViewportTab.kind === "code" && activeViewportTab.id === fileId) {
        nextViewport = filtered.length > 0
          ? { kind: "code", id: filtered[filtered.length - 1].id }
          : { kind: "output", id: fallbackOutput };
      }

      set({
        openFiles: filtered,
        selectedFile: filtered.find((file) => file.id === nextViewport.id) || null,
        activeViewportTab: nextViewport,
      });
      debouncedSave();
    },

    // ═══════════════════════════════════════
    //  사용자 피드백 (댓글 및 메모)
    // ═══════════════════════════════════════
    userComments: [],

    syncMemos: async () => {
      const { backendPort, currentSessionId } = get();
      if (!backendPort) return;
      try {
        const url = currentSessionId
          ? `http://127.0.0.1:${backendPort}/api/memos?session_id=${currentSessionId}`
          : `http://127.0.0.1:${backendPort}/api/memos`;
        const res = await fetch(url);
        const data = await res.json();
        if (data.status === "ok") {
          const formatted = data.memos.map(m => ({
            id: m.id,
            text: m.text,
            selectedText: m.metadata.selected_text,
            section: m.metadata.section,
            createdAt: Date.now(), // dummy for now
          }));
          set({ userComments: formatted });
        }
      } catch (e) {
        console.error("[MemoSync] Failed:", e);
      }
    },

    addComment: async (comment) => {
      const { backendPort, currentSessionId } = get();
      set((state) => ({
        userComments: [...state.userComments, { id: "temp_" + Date.now(), ...comment, createdAt: Date.now() }]
      }));
      debouncedSave();

      if (backendPort && currentSessionId) {
        try {
          await fetch(`http://127.0.0.1:${backendPort}/api/memos`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              session_id: currentSessionId,
              text: comment.text,
              selected_text: comment.selectedText || "",
              section: comment.section || "Global"
            }),
          });
          get().syncMemos();
        } catch (e) {
          console.error("[MemoAdd] Backend failed:", e);
        }
      }
    },

    removeComment: async (id) => {
      const { backendPort } = get();
      set((state) => ({
        userComments: state.userComments.filter(c => c.id !== id)
      }));
      debouncedSave();

      if (backendPort && !id.startsWith("temp_")) {
        try {
          await fetch(`http://127.0.0.1:${backendPort}/api/memos/${id}`, { method: "DELETE" });
        } catch (e) {
          console.error("[MemoDelete] Backend failed:", e);
        }
      }
    },

    // ═══════════════════════════════════════
    //  채팅
    // ═══════════════════════════════════════
    chatHistory: [],
    chatInput: "",

    addChatMessage: (role, content) => {
      set((state) => ({
        chatHistory: [...state.chatHistory, { role, content }],
      }));
      debouncedSave();
    },

    setChatInput: (text) => set({ chatInput: text }),

    clearChat: () => {
      set({ chatHistory: [], chatInput: "" });
      debouncedSave();
    },

    // ═══════════════════════════════════════
    //  파일 트리 (사이드바)
    // ═══════════════════════════════════════
    fileTree: [],
    selectedFile: null,
    projectFolder: null,

    setFileTree: (tree) => set({ fileTree: tree }),
    setSelectedFile: (file) => set({ selectedFile: file }),
    setProjectFolder: (path) => set({ projectFolder: path }),

    ensureProjectFolderAccess: async (folderPath) => {
      const { backendPort } = get();
      if (!backendPort || !folderPath) return false;

      try {
        const res = await fetch(`http://127.0.0.1:${backendPort}/api/scan-folder`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: folderPath, max_depth: 3 }),
        });
        const data = await res.json();
        if (data.status === "ok") {
          set({ fileTree: data.tree || get().fileTree, projectFolder: data.root || folderPath });
          debouncedSave();
          return true;
        }
        console.error("[ProjectAccess] Error:", data.error);
        return false;
      } catch (e) {
        console.error("[ProjectAccess] Fetch failed:", e);
        return false;
      }
    },

    selectAndScanFolder: async () => {
      if (!window.electronAPI?.selectFolder) return;
      const folderPath = await window.electronAPI.selectFolder();
      if (!folderPath) return;

      const { backendPort } = get();
      try {
        const res = await fetch(`http://127.0.0.1:${backendPort}/api/scan-folder`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: folderPath, max_depth: 3 }),
        });
        const data = await res.json();
        if (data.status === "ok") {
          set({ fileTree: data.tree || [], projectFolder: data.root || folderPath });
          debouncedSave();
        } else {
          console.error("[FolderScan] Error:", data.error);
        }
      } catch (e) {
        console.error("[FolderScan] Fetch failed:", e);
      }
    },

    openProjectFile: async (node) => {
      const { backendPort, projectFolder } = get();
      if (!backendPort || !node?.path) return;

      const readFile = async () => {
        const res = await fetch(`http://127.0.0.1:${backendPort}/api/read-file`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: node.path }),
        });
        return res.json();
      };

      try {
        let data = await readFile();

        const needsRescan = data.status !== "ok" && (
          String(data.error || "").includes("먼저 프로젝트 폴더를 스캔하세요") ||
          String(data.error || "").includes("프로젝트 폴더 밖의 파일")
        );

        if (needsRescan && projectFolder) {
          const restored = await get().ensureProjectFolderAccess(projectFolder);
          if (restored) {
            data = await readFile();
          }
        }

        if (data.status !== "ok") {
          console.error("[ReadFile] Error:", data.error);
          return;
        }

        get().openFile({
          id: node.path,
          name: node.name,
          path: node.path,
          content: data.content || "",
          language: get().detectLanguage(node.name),
        });
      } catch (e) {
        console.error("[ReadFile] Fetch failed:", e);
      }
    },

    detectLanguage: (filename) => {
      const ext = filename.split(".").pop()?.toLowerCase();
      const map = {
        py: "python",
        js: "javascript",
        jsx: "javascript",
        ts: "typescript",
        tsx: "typescript",
        json: "json",
        md: "markdown",
        yaml: "yaml",
        yml: "yaml",
        html: "html",
        css: "css",
      };
      return map[ext] || "plaintext";
    },

    // ═══════════════════════════════════════
    //  세션 관리
    // ═══════════════════════════════════════
    sessions: loadSessions(),
    currentSessionId: null,

    createSession: () => {
      const state = get();
      const id = Date.now().toString();
      const now = new Date();
      const name = `세션 ${now.toLocaleDateString("ko")} ${now.toLocaleTimeString("ko", { hour: "2-digit", minute: "2-digit" })}`;
      const session = {
        id,
        name,
        createdAt: now.getTime(),
        projectName: null,
        projectFolder: state.projectFolder,
        fileTree: state.fileTree,
        openFiles: state.openFiles,
        selectedFile: state.selectedFile,
        activeViewportTab: { kind: "output", id: "progress" },
        resultData: null,
        chatHistory: [],
        pipelineStatus: "running",
        pipelineType: state.pipelineType,
        pipelineError: null,
        pipelineNodes: {},
        thinkingLog: [],
        selectedMode: state.selectedMode,
        model: state.model,
        userComments: [],
      };

      set((current) => {
        const sessions = [session, ...current.sessions];
        persistSessions(sessions);
        return { sessions, currentSessionId: id };
      });
    },

    saveCurrentSession: () => {
      const state = get();
      const { sessions, currentSessionId } = state;
      if (!currentSessionId) return;

      const projectName = state.metadata?.project_name || null;
      const updated = sessions.map((session) => (
        session.id === currentSessionId
          ? {
            ...session,
            projectName,
            projectFolder: state.projectFolder,
            fileTree: state.fileTree,
            openFiles: state.openFiles,
            selectedFile: state.selectedFile,
            activeViewportTab: cloneViewportTab(state.activeViewportTab),
            resultData: state.resultData,
            chatHistory: state.chatHistory,
            pipelineStatus: state.pipelineStatus,
            pipelineType: state.pipelineType,
            pipelineError: state.pipelineError,
            pipelineNodes: state.pipelineNodes,
            thinkingLog: state.thinkingLog,
            selectedMode: state.selectedMode,
            model: state.model,
            userComments: state.userComments,
          }
          : session
      ));

      persistSessions(updated);
      set({ sessions: updated });
    },

    loadSession: (id) => {
      const { sessions } = get();
      const session = sessions.find((entry) => entry.id === id);
      if (!session) return;

      const normalizedViewportTab = cloneViewportTab(session.activeViewportTab);
      if (normalizedViewportTab.kind === "output") {
        normalizedViewportTab.id = normalizeOutputTabId(normalizedViewportTab.id);
      }

      set({
        currentSessionId: id,
        projectFolder: session.projectFolder || null,
        fileTree: session.fileTree || [],
        openFiles: session.openFiles || [],
        selectedFile: session.selectedFile || null,
        activeViewportTab: normalizedViewportTab,
        lastOutputTab: session.activeViewportTab?.kind === "output"
          ? normalizeOutputTabId(session.activeViewportTab.id)
          : (session.resultData ? "overview" : "home"),
        ...spreadResultData(session.resultData),
        chatHistory: session.chatHistory || [],
        pipelineStatus: session.resultData ? "done" : "idle",
        pipelineType: session.pipelineType || inferPipelineTypeFromResult(session.resultData || {}),
        pipelineError: null,
        pipelineNodes: session.pipelineNodes || {},
        thinkingLog: session.thinkingLog || [],
        selectedMode: normalizeMode(session.selectedMode),
        model: session.model || get().model,
        userComments: session.userComments || [],
      });
      
      // [Knowledge Restore] Phase 3: 세션 로드 시 자동으로 RAG 복구 시도
      get().restoreSessionFromRag(id);

      if (session.projectFolder) {
        setTimeout(() => {
          get().ensureProjectFolderAccess(session.projectFolder);
        }, 0);
      }
    },

    restoreSessionFromRag: async (id) => {
      const { sessions, backendPort, _processResult } = get();
      const session = sessions.find(s => s.id === id);
      const runId = session?.resultData?.run_id || extractRunId(id);
      
      if (!runId || !backendPort) return;
      
      try {
        console.log(`[RAG Restore] Syncing session ${runId}...`);
        const res = await fetch(`http://127.0.0.1:${backendPort}/api/session/${runId}/restore`);
        const resData = await res.json();
        
        if (resData.status === "ok") {
          console.log(`[RAG Restore] Success for ${runId}:`, resData.data);
          _processResult(resData.data);
          return true;
        }
        return false;
      } catch (err) {
        console.error("[RAG Restore] Failed:", err);
        return false;
      }
    },

    deleteSession: async (id) => {
      const { backendPort, sessions } = get();
      const session = sessions.find((entry) => entry.id === id);
      const backendDeleteId = session?.resultData?.run_id
        || extractRunId(id) || null;

      // 백엔드 DELETE API 호출 (세션 완전 삭제: JSON + ChromaDB)
      if (backendPort && backendDeleteId) {
        try {
          const res = await fetch(`http://127.0.0.1:${backendPort}/api/session/${backendDeleteId}`, {
            method: "DELETE",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({}),
          });
          if (!res.ok) {
            const errorData = await res.json();
            console.warn("[Delete Session] API error:", errorData);
          } else {
            const result = await res.json();
            console.log("[Delete Session] Success:", result);
          }
        } catch (err) {
          console.error("[Delete Session] Fetch failed:", err);
        }
      }

      // 로컬 상태 정리 (기존 로직)
      set((state) => {
        const sessions = state.sessions.filter((entry) => entry.id !== id);
        persistSessions(sessions);
        return {
          sessions,
          currentSessionId: state.currentSessionId === id ? null : state.currentSessionId,
        };
      });
    },

    updateSessionName: (sessionId, newName) => {
      set((state) => {
        const sessions = state.sessions.map((s) =>
          s.id === sessionId ? { ...s, name: newName, projectName: newName } : s
        );
        persistSessions(sessions);

        const updates = { sessions };
        if (state.currentSessionId === sessionId) {
          // 현재 세션일 경우 공통 메타데이터 동기화
          const nextMetadata = state.metadata ? { ...state.metadata, project_name: newName } : { project_name: newName };
          const nextResultData = state.resultData ? {
            ...state.resultData,
            project_overview: {
              ...(state.resultData.project_overview || {}),
              project_name: newName
            }
          } : state.resultData;

          updates.metadata = nextMetadata;
          updates.resultData = nextResultData;
        }

        return updates;
      });
    },

    // ═══════════════════════════════════════
    //  리셋
    // ═══════════════════════════════════════
    resetPipeline: () => set((state) => ({
      pipelineStatus: "idle",
      pipelineError: null,
      pipelineNodes: {},
      thinkingLog: [],
      ...EMPTY_RESULT_FIELDS,
      activeViewportTab: { kind: "output", id: "home" },
      lastOutputTab: "home",
      chatHistory: [],
      chatInput: "",
      openFiles: state.openFiles,
      selectedFile: state.selectedFile,
      fileTree: state.fileTree,
      projectFolder: state.projectFolder,
      userComments: [],
    })),
  };
});

export default useAppStore;

