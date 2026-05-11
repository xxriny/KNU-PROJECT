import { sessionService } from "../../api/services/sessionService";
import { loadSessions, persistSessions, cloneViewportTab, normalizeOutputTabId, extractRunId, spreadResultData } from "../storeHelpers";

// 활성 세션이 없을 때 채팅/팝오버 메모를 묶어두는 폴백 세션 키.
// 백엔드 memo_db는 session_id 형식을 강제하지 않으므로 안전한 임의 문자열을 사용.
const CHAT_GLOBAL_SESSION_ID = "chat_global";

export const createSessionSlice = (set, get) => ({
  sessions: loadSessions(),
  currentSessionId: null,
  userComments: [],
  chatHistory: [],
  chatInput: "",

  createSession: (initialTitle = null) => {
    const state = get();
    const id = Date.now().toString();
    const now = new Date();
    const session = {
      id,
      name: initialTitle && initialTitle !== "새 프로젝트" ? initialTitle : `세션 ${now.toLocaleDateString("ko")} ${now.toLocaleTimeString("ko", { hour: "2-digit", minute: "2-digit" })}`,
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
      if (data.status !== "ok") return;

      const serverItems = (data.memos || []).map((m) => ({
        id: m.id,
        text: m.text,
        selectedText: m.metadata?.selected_text || "",
        section: m.metadata?.section || "Global",
        detail: m.metadata?.detail || "",
        applied: !!m.metadata?.applied,
        appliedAt: m.metadata?.applied_at || null,
        createdAt: Date.now(),
      }));

      // 서버 응답으로 무지성 덮어쓰면 in-flight(`temp_`) 항목이 사라진다.
      // POST가 아직 끝나지 않은 로컬 메모를 보존하고, 텍스트 기준으로 중복 제거.
      const local = get().userComments || [];
      const inFlight = local.filter(
        (c) => typeof c?.id === "string" && c.id.startsWith("temp_")
      );
      const seenTexts = new Set(serverItems.map((s) => (s.text || "").trim()));
      const merged = [
        ...serverItems,
        ...inFlight.filter((c) => !seenTexts.has((c.text || "").trim())),
      ];

      set({ userComments: merged });
    } catch (e) {
      console.error("[MemoSync] Failed:", e);
      get().addDebugLog({ level: "error", message: "메모 동기화 실패", rawData: { error: e.message } });
    }
  },

  addComment: async (comment, opts = {}) => {
    const { silent = false } = opts;
    const { backendPort, currentSessionId } = get();
    const tempId = "temp_" + Date.now() + "_" + Math.random().toString(36).slice(2, 6);
    const sessionIdForPersist = currentSessionId || CHAT_GLOBAL_SESSION_ID;

    console.log(
      `[addComment] 진입 — backendPort=${backendPort} currentSessionId=${currentSessionId} ` +
      `sessionIdForPersist=${sessionIdForPersist} text="${(comment?.text || "").slice(0, 50)}"`
    );

    // 1. 로컬 상태 즉시 반영 (UI 반응성)
    set((s) => ({
      userComments: [...s.userComments, { id: tempId, ...comment, createdAt: Date.now() }],
    }));

    // 2. 백엔드 영속화 — 활성 세션이 없어도 chat_global 폴백으로 저장한다.
    //    이전에는 `currentSessionId`가 null이면 영속화를 건너뛰어, MemoManager가
    //    syncMemos로 로컬 상태를 덮어쓸 때 메모가 증발하는 문제가 있었다.
    if (!backendPort) {
      console.warn("[addComment] backendPort가 없어 백엔드 저장을 건너뜀 (로컬에만 보존)");
      return;
    }
    try {
      console.log(`[addComment] POST /api/memos 시도 — session_id=${sessionIdForPersist}`);
      const res = await sessionService.addMemo(backendPort, {
        session_id: sessionIdForPersist,
        text: comment.text,
        selected_text: comment.selectedText || "",
        section: comment.section || "Global",
        detail: comment.detail || "",
      });
      console.log(`[addComment] POST 응답:`, res);

      if (res.status === "ok") {
        // 서버에서 생성된 진짜 ID로 교체
        set((s) => ({
          userComments: s.userComments.map((c) =>
            c.id === tempId ? { ...c, id: res.memo_id } : c
          ),
        }));
        if (!silent) {
          get().addNotification("메모가 저장되었습니다.", "success");
        }
      } else {
        // status가 "ok"가 아닌 응답 — 백엔드가 에러 응답을 보낸 경우
        console.warn("[addComment] 서버 응답이 ok가 아님:", res);
        get().addNotification(
          `메모 저장 응답 오류: ${res?.error || "unknown"}`,
          "error"
        );
      }
    } catch (e) {
      console.error("[addComment] POST 실패:", e);
      get().addDebugLog({ level: "error", message: "메모 서버 저장 실패", rawData: { error: e.message } });
      // 백엔드 저장 실패도 사용자에게 즉시 알림 (조용히 묻히지 않도록)
      get().addNotification(`메모 저장 실패: ${e?.message || e}`, "error");
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

  /**
   * 메모 ID 목록을 백엔드에 'applied' 표시 요청 + 로컬 userComments에도 반영.
   * "지적사항 반영 설계 업데이트" 흐름의 마지막 단계에서 _processResult가 호출.
   * 실패해도 사용자 흐름을 막지 않는다 (백엔드 일시 장애 등).
   */
  markMemosApplied: async (memoIds) => {
    const { backendPort } = get();
    if (!Array.isArray(memoIds) || memoIds.length === 0) return;
    if (!backendPort) {
      console.warn("[markMemosApplied] backendPort 없어 백엔드 갱신 스킵");
      return;
    }
    try {
      const res = await sessionService.applyMemos(backendPort, memoIds);
      if (res?.status === "ok") {
        const ts = new Date().toISOString();
        set((s) => ({
          userComments: (s.userComments || []).map((c) =>
            memoIds.includes(c.id) ? { ...c, applied: true, appliedAt: ts } : c
          ),
        }));
      } else {
        console.warn("[markMemosApplied] 백엔드 응답 비정상:", res);
      }
    } catch (e) {
      console.error("[markMemosApplied] 실패:", e);
      get().addDebugLog?.({
        level: "error",
        message: "메모 applied 표시 실패",
        rawData: { error: e?.message, ids: memoIds },
      });
    }
  },

  setChatInput: (text) => set({ chatInput: text }),
  addChatMessage: (role, content) =>
    set((s) => ({ chatHistory: [...s.chatHistory, { role, content }] })),
  clearChat: () => set({ chatHistory: [], chatInput: "" }),

  updateSessionName: (id, name) => {
    set((state) => {
      const updated = state.sessions.map((s) => (s.id === id ? { ...s, name } : s));
      persistSessions(updated);
      return { sessions: updated };
    });
  },
});
