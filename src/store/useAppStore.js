/**
 * PM Agent Pipeline v2 — Global State (Zustand)
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

const SESSION_STORAGE_KEY = "pm_sessions";
const DEFAULT_VIEWPORT_TAB = { kind: "output", id: "home" };
const MODE_TO_ACTION_TYPE = {
  create: "CREATE",
  update: "UPDATE",
  reverse: "REVERSE_ENGINEER",
};

const MODE_TO_PIPELINE_TYPE = {
  create: "analysis_create",
  update: "analysis_update",
  reverse: "analysis_reverse",
};

function normalizeMode(mode) {
  return MODE_TO_ACTION_TYPE[mode] ? mode : "create";
}

function loadSessions() {
  try {
    return JSON.parse(localStorage.getItem(SESSION_STORAGE_KEY) || "[]");
  } catch {
    return [];
  }
}

function persistSessions(sessions) {
  try {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(sessions));
  } catch {
    // Non-fatal localStorage failure.
  }
}

function cloneViewportTab(tab) {
  return tab ? { kind: tab.kind, id: tab.id } : { ...DEFAULT_VIEWPORT_TAB };
}

function extractRunId(value) {
  if (typeof value !== "string") {
    return null;
  }

  const match = value.match(/(\d{8}_\d{6})/);
  return match ? match[1] : null;
}

function inferPipelineTypeFromResult(data) {
  const hinted = data?.pipeline_type;
  if (typeof hinted === "string" && hinted) {
    return hinted;
  }

  const actionType = (data?.metadata?.action_type || "").toUpperCase();
  if (actionType === "REVERSE_ENGINEER") {
    return "analysis_reverse";
  }
  if (actionType === "UPDATE") {
    return "analysis_update";
  }
  return "analysis_create";
}

const useAppStore = create((set, get) => ({
  // ═══════════════════════════════════════
  //  백엔드 연결 상태
  // ═══════════════════════════════════════
  backendPort: null,
  wsConnection: null,
  wsStatus: "disconnected",

  setBackendPort: (port) => set({ backendPort: port }),
  setWsStatus: (status) => set({ wsStatus: status }),

  connectWebSocket: (port) => {
    const currentWs = get().wsConnection;
    if (currentWs && currentWs.readyState === WebSocket.OPEN) {
      return;
    }

    set({ wsStatus: "connecting" });
    const ws = new WebSocket(`ws://127.0.0.1:${port}/ws/pipeline`);

    ws.onopen = () => {
      console.log("[WS] Connected to backend");
      set({ wsConnection: ws, wsStatus: "connected" });
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        get()._handleWsMessage(msg);
      } catch (err) {
        console.error("[WS] Parse error:", err);
      }
    };

    ws.onclose = () => {
      console.log("[WS] Disconnected");
      set({ wsConnection: null, wsStatus: "disconnected" });
      setTimeout(() => {
        const { backendPort, wsStatus } = get();
        if (backendPort && wsStatus === "disconnected") {
          get().connectWebSocket(backendPort);
        }
      }, 3000);
    };

    ws.onerror = (err) => {
      console.error("[WS] Error:", err);
      set({ wsStatus: "error" });
    };

    set({ wsConnection: ws });
  },

  sendWsMessage: (type, payload) => {
    const ws = get().wsConnection;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type, payload }));
      return;
    }
    console.warn("[WS] Not connected, cannot send message");
  },

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
        setTimeout(() => get().saveCurrentSession(), 0);
        break;

      case "thinking":
        set((state) => ({
          thinkingLog: [
            ...state.thinkingLog,
            { node, text: data.text, timestamp: Date.now() },
          ],
        }));
        setTimeout(() => get().saveCurrentSession(), 0);
        break;

      case "result":
        get()._processResult(data, node);
        break;

      case "error":
        set({
          pipelineStatus: "error",
          pipelineError: data.message,
        });
        setTimeout(() => get().saveCurrentSession(), 0);
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
      resultData: null,
      requirements_rtm: [],
      semantic_graph: null,
      context_spec: null,
      sa_output: null,
      sa_phase1: null,
      sa_phase2: null,
      sa_phase3: null,
      sa_phase4: null,
      sa_phase5: null,
      sa_phase6: null,
      sa_phase7: null,
      sa_phase8: null,
      metadata: null,
      chatHistory: [],
      chatInput: "",
      selectedMode: normalizedMode,
      activeViewportTab: { kind: "output", id: "progress" },
      lastOutputTab: "progress",
    });
    setTimeout(() => get().saveCurrentSession(), 0);
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
    setTimeout(() => get().saveCurrentSession(), 0);
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
  sa_output: null,
  sa_phase1: null,
  sa_phase2: null,
  sa_phase3: null,
  sa_phase4: null,
  sa_phase5: null,
  sa_phase6: null,
  sa_phase7: null,
  sa_phase8: null,
  metadata: null,
  selectedMode: "create",
  availableModels: ["gemini-2.5-flash"],

  _processResult: (data, node = "complete") => {
    if (node === "idea_chat") {
      const reply = data.chat_reply || data.assistant_message || data.message || "";
      if (reply) {
        set((state) => ({
          chatHistory: [...state.chatHistory, { role: "assistant", content: reply }],
        }));
        setTimeout(() => get().saveCurrentSession(), 0);
      }
      return;
    }

    set({
      pipelineStatus: "done",
      pipelineType: inferPipelineTypeFromResult(data),
      resultData: data,
      requirements_rtm: data.requirements_rtm || [],
      semantic_graph: data.semantic_graph || null,
      context_spec: data.context_spec || null,
      sa_output: data.sa_output || null,
      sa_phase1: data.sa_phase1 || null,
      sa_phase2: data.sa_phase2 || null,
      sa_phase3: data.sa_phase3 || null,
      sa_phase4: data.sa_phase4 || null,
      sa_phase5: data.sa_phase5 || null,
      sa_phase6: data.sa_phase6 || null,
      sa_phase7: data.sa_phase7 || null,
      sa_phase8: data.sa_phase8 || null,
      metadata: data.metadata || null,
      chatHistory: data.chat_history || get().chatHistory,
      activeViewportTab: { kind: "output", id: "overview" },
      lastOutputTab: "overview",
    });
    setTimeout(() => get().saveCurrentSession(), 0);
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
    setTimeout(() => get().saveCurrentSession(), 0);
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
    setTimeout(() => get().saveCurrentSession(), 0);
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
    setTimeout(() => get().saveCurrentSession(), 0);
  },

  setChatInput: (text) => set({ chatInput: text }),

  clearChat: () => {
    set({ chatHistory: [], chatInput: "" });
    setTimeout(() => get().saveCurrentSession(), 0);
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

  selectAndScanFolder: async () => {
    if (!window.electronAPI?.selectFolder) return;
    const folderPath = await window.electronAPI.selectFolder();
    if (!folderPath) return;

    const { backendPort } = get();
    try {
      const res = await fetch(`http://127.0.0.1:${backendPort}/api/scan-folder`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: folderPath }),
      });
      const data = await res.json();
      if (data.status === "ok") {
        set({ fileTree: data.tree || [], projectFolder: data.root || folderPath });
        setTimeout(() => get().saveCurrentSession(), 0);
      } else {
        console.error("[FolderScan] Error:", data.error);
      }
    } catch (e) {
      console.error("[FolderScan] Fetch failed:", e);
    }
  },

  openProjectFile: async (node) => {
    const { backendPort } = get();
    if (!backendPort || !node?.path) return;

    try {
      const res = await fetch(`http://127.0.0.1:${backendPort}/api/read-file`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: node.path }),
      });
      const data = await res.json();
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
  //  설정
  // ═══════════════════════════════════════
  apiKey: "",
  model: "gemini-2.5-flash",
  backendHasKey: false,

  setApiKey: (key) => set({ apiKey: key }),
  setModel: (model) => set({ model }),

  fetchConfig: async (port) => {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/api/config`);
      if (!res.ok) return;
      const cfg = await res.json();
      const nextAvailableModels = Array.isArray(cfg.available_models) && cfg.available_models.length > 0
        ? cfg.available_models
        : ["gemini-2.5-flash"];
      const currentModel = get().model;
      if (cfg.has_api_key) {
        set({ backendHasKey: true });
      }
      set({
        availableModels: nextAvailableModels,
        model: nextAvailableModels.includes(currentModel)
          ? currentModel
          : (cfg.default_model && nextAvailableModels.includes(cfg.default_model)
              ? cfg.default_model
              : nextAvailableModels[0]),
      });
    } catch (e) {
      console.warn("[Config] Failed to fetch /api/config:", e);
    }
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

    set({
      currentSessionId: id,
      projectFolder: session.projectFolder || null,
      fileTree: session.fileTree || [],
      openFiles: session.openFiles || [],
      selectedFile: session.selectedFile || null,
      activeViewportTab: cloneViewportTab(session.activeViewportTab),
      lastOutputTab: session.activeViewportTab?.kind === "output"
        ? session.activeViewportTab.id
        : (session.resultData ? "overview" : "home"),
      resultData: session.resultData || null,
      chatHistory: session.chatHistory || [],
      requirements_rtm: session.resultData?.requirements_rtm || [],
      semantic_graph: session.resultData?.semantic_graph || null,
      context_spec: session.resultData?.context_spec || null,
      sa_output: session.resultData?.sa_output || null,
      sa_phase1: session.resultData?.sa_phase1 || null,
      sa_phase2: session.resultData?.sa_phase2 || null,
      sa_phase3: session.resultData?.sa_phase3 || null,
      sa_phase4: session.resultData?.sa_phase4 || null,
      sa_phase5: session.resultData?.sa_phase5 || null,
      sa_phase6: session.resultData?.sa_phase6 || null,
      sa_phase7: session.resultData?.sa_phase7 || null,
      sa_phase8: session.resultData?.sa_phase8 || null,
      metadata: session.resultData?.metadata || null,
      pipelineStatus: session.resultData ? "done" : "idle",
      pipelineType: session.pipelineType || inferPipelineTypeFromResult(session.resultData || {}),
      pipelineError: null,
      pipelineNodes: session.pipelineNodes || {},
      thinkingLog: session.thinkingLog || [],
      selectedMode: normalizeMode(session.selectedMode),
      model: session.model || get().model,
    });
  },

  deleteSession: async (id) => {
    const { backendPort, sessions } = get();
    const session = sessions.find((entry) => entry.id === id);
    const projectStatePath = session?.resultData?.project_state_path || "";
    const backendDeleteId = session?.resultData?.run_id
      || extractRunId(projectStatePath)
      || (extractRunId(id) || null);
    
    // 백엔드 DELETE API 호출 (세션 완전 삭제: JSON + PROJECT_STATE.md + ChromaDB)
    if (backendPort && backendDeleteId) {
      try {
        const res = await fetch(`http://127.0.0.1:${backendPort}/api/session/${backendDeleteId}`, {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project_state_path: projectStatePath }),
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
        // UI는 낙관적 업데이트했으므로 계속 진행
      }
    } else if (backendPort) {
      console.warn("[Delete Session] Missing backend deletion id", { id, projectStatePath });
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

  // ═══════════════════════════════════════
  //  리셋
  // ═══════════════════════════════════════
  resetPipeline: () => set((state) => ({
    pipelineStatus: "idle",
    pipelineError: null,
    pipelineNodes: {},
    thinkingLog: [],
    resultData: null,
    requirements_rtm: [],
    semantic_graph: null,
    context_spec: null,
    sa_output: null,
    sa_phase1: null,
    sa_phase2: null,
    sa_phase3: null,
    sa_phase4: null,
    sa_phase5: null,
    sa_phase6: null,
    sa_phase7: null,
    sa_phase8: null,
    metadata: null,
    activeViewportTab: { kind: "output", id: "home" },
    lastOutputTab: "home",
    chatHistory: [],
    chatInput: "",
    openFiles: state.openFiles,
    selectedFile: state.selectedFile,
    fileTree: state.fileTree,
    projectFolder: state.projectFolder,
  })),
}));

export default useAppStore;

