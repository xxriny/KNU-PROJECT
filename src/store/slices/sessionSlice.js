import { sessionService } from "../../api/services/sessionService";
import { loadSessions, persistSessions, cloneViewportTab, normalizeOutputTabId, extractRunId, spreadResultData } from "../storeHelpers";

export const createSessionSlice = (set, get) => ({
  sessions: loadSessions(),
  currentSessionId: null,
  userComments: [],
  chatHistory: [],
  chatInput: "",

  createSession: () => {
    const state = get();
    const id = Date.now().toString();
    const now = new Date();
    const session = {
      id,
      name: `세션 ${now.toLocaleDateString("ko")} ${now.toLocaleTimeString("ko", { hour: "2-digit", minute: "2-digit" })}`,
      createdAt: now.getTime(),
      projectFolder: state.projectFolder,
      fileTree: state.fileTree,
      openFiles: state.openFiles,
      activeViewportTab: { kind: "output", id: "progress" },
      resultData: null,
      chatHistory: [],
      pipelineStatus: "running",
      pipelineType: state.pipelineType,
      selectedMode: state.selectedMode,
      userComments: [],
    };
    set((state) => {
      const sessions = [session, ...state.sessions];
      persistSessions(sessions);
      return { sessions, currentSessionId: id };
    });
  },

  saveCurrentSession: () => {
    const state = get();
    if (!state.currentSessionId) return;
    const updated = state.sessions.map((s) => (
      s.id === state.currentSessionId ? {
        ...s,
        projectFolder: state.projectFolder,
        fileTree: state.fileTree,
        openFiles: state.openFiles,
        activeViewportTab: cloneViewportTab(state.activeViewportTab),
        resultData: state.resultData,
        chatHistory: state.chatHistory,
        pipelineStatus: state.pipelineStatus,
        pipelineType: state.pipelineType,
        userComments: state.userComments,
      } : s
    ));
    persistSessions(updated);
    set({ sessions: updated });
  },

  loadSession: (id) => {
    const session = get().sessions.find((s) => s.id === id);
    if (!session) return;
    const viewport = cloneViewportTab(session.activeViewportTab);
    if (viewport.kind === "output") viewport.id = normalizeOutputTabId(viewport.id);

    // 즉시 세션 상태 반영 (RAG 복구 전 로컬 데이터 우선)
    set({
      currentSessionId: id,
      projectFolder: session.projectFolder || null,
      fileTree: session.fileTree || [],
      openFiles: session.openFiles || [],
      activeViewportTab: viewport,
      ...spreadResultData(session.resultData),
      chatHistory: session.chatHistory || [],
      pipelineStatus: session.resultData ? "done" : "idle",
      userComments: session.userComments || [],
    });
    
    // RAG 복구는 백그라운드에서 조용히 수행 (로딩 인디케이터 없음)
    get().restoreSessionFromRag(id);
  },

  restoreSessionFromRag: async (id) => {
    const { sessions, backendPort, _processResult } = get();
    const session = sessions.find(s => s.id === id);
    const runId = session?.resultData?.run_id || extractRunId(id);
    if (!runId || !backendPort) return;
    try {
      const res = await sessionService.restoreSession(backendPort, runId);
      if (res.status === "ok") {
        // 복원된 데이터 반영 시 현재 탭 유지
        const currentTab = get().activeViewportTab;
        _processResult(res.data);
        set({ activeViewportTab: currentTab });
      }
    } catch (e) {
      // 조용히 처리
    }
  },

  syncMemos: async () => {
    const { backendPort, currentSessionId } = get();
    if (!backendPort) return;
    try {
      const data = await sessionService.getMemos(backendPort, currentSessionId);
      if (data.status === "ok") {
        set({ userComments: data.memos.map(m => ({ id: m.id, text: m.text, selectedText: m.metadata.selected_text, section: m.metadata.section, createdAt: Date.now() })) });
      }
    } catch (e) { 
      console.error("[MemoSync] Failed:", e);
      get().addDebugLog({ level: "error", message: "메모 동기화 실패", rawData: { error: e.message } });
    }
  },

  addComment: async (comment) => {
    const { backendPort, currentSessionId } = get();
    const tempId = "temp_" + Date.now();
    
    // 1. 로컬 상태 즉시 반영 (UI 반응성)
    set((s) => ({ 
      userComments: [...s.userComments, { id: tempId, ...comment, createdAt: Date.now() }] 
    }));
    
    // 2. 백엔드 동기화 (세션이 활성화된 경우만)
    if (backendPort && currentSessionId) {
        try {
          const res = await sessionService.addMemo(backendPort, {
            session_id: currentSessionId,
            text: comment.text,
            selected_text: comment.selectedText || "",
            section: comment.section || "Global"
          });
          
          if (res.status === "ok") {
            // 서버에서 생성된 진짜 ID로 교체
            set((s) => ({
              userComments: s.userComments.map(c => c.id === tempId ? { ...c, id: res.memo_id } : c)
            }));
            get().addNotification("메모가 저장되었습니다.", "success");
          }
        } catch (e) { 
          console.error("[MemoAdd] Failed:", e);
          get().addDebugLog({ level: "error", message: "메모 서버 저장 실패", rawData: { error: e.message } });
        }
    }
  },

  removeComment: async (id) => {
    const { backendPort } = get();
    if (!id) return;

    // 1. 로컬 상태 즉시 제거
    set((s) => ({ userComments: s.userComments.filter(c => c.id !== id) }));

    // 2. 백엔드 삭제 요청
    if (backendPort && !id.toString().startsWith("temp_")) {
      try {
        const res = await sessionService.removeMemo(backendPort, id);
        if (res.status === "ok") {
          get().addNotification("메모가 삭제되었습니다.", "success");
        } else {
          throw new Error(res.error || "Unknown error");
        }
      } catch (e) {
        console.error("[MemoDelete] Failed:", e);
        get().addDebugLog({ level: "error", message: "메모 삭제 실패", rawData: { error: e.message, id } });
        get().syncMemos(); // 오류 발생 시 서버 상태와 다시 맞춤
      }
    }
  },

  setChatInput: (text) => set({ chatInput: text }),
  clearChat: () => set({ chatHistory: [], chatInput: "" }),
});
