import { sessionService } from "../../api/services/sessionService";
import { loadSessions, persistSessions, cloneViewportTab, normalizeOutputTabId, extractRunId, spreadResultData, EMPTY_RESULT_FIELDS } from "../storeHelpers";

// 활성 세션이 없을 때 채팅/팝오버 메모를 묶어두는 폴백 세션 키.
// 백엔드 memo_db는 session_id 형식을 강제하지 않으므로 안전한 임의 문자열을 사용.
const CHAT_GLOBAL_SESSION_ID = "chat_global";

export const createSessionSlice = (set, get) => ({
  sessions: loadSessions(),
  currentSessionId: null,
  userComments: [],
  chatHistory: [],
  chatInput: "",
  designSnapshots: [],
  designSnapshotCounter: 0,
  // 온보딩: 첫 진입 / 새 프로젝트 시작 직후에 ModeBridge 모달을 띄움
  showOnboardingBridge: true,
  setShowOnboardingBridge: (v) => set({ showOnboardingBridge: !!v }),

  /** Sync 직전에 현재 설계 상태를 스냅샷으로 저장. FIFO로 최근 5개만 유지. */
  pushDesignSnapshot: () => {
    const s = get();
    const counter = s.designSnapshotCounter || 0;
    const entry = {
      version: `v1.${counter}`,
      takenAt: new Date().toISOString(),
      chatHistoryLength: (s.chatHistory || []).length,
      resultData: s.resultData ? structuredClone(s.resultData) : null,
      requirements_rtm: s.requirements_rtm ? structuredClone(s.requirements_rtm) : null,
      components: s.components ? structuredClone(s.components) : null,
      apis: s.apis ? structuredClone(s.apis) : null,
      tables: s.tables ? structuredClone(s.tables) : null,
      tech_stacks: s.tech_stacks ? structuredClone(s.tech_stacks) : null,
      project_structure: s.project_structure ? structuredClone(s.project_structure) : null,
      test_cases: s.test_cases ? structuredClone(s.test_cases) : null,
      recommendations: s.recommendations ? structuredClone(s.recommendations) : null,
      sa_artifacts: s.sa_artifacts ? structuredClone(s.sa_artifacts) : null,
    };
    set((state) => {
      const next = [...(state.designSnapshots || []), entry].slice(-5);
      return { designSnapshots: next, designSnapshotCounter: counter + 1 };
    });
    return entry;
  },

  /** 스냅샷 인덱스로 resultData를 되돌림. chatHistory는 유지하고 rollback 마커를 append.
   *  추가로, fromVersion에서 새로 추가된 메모(reflectedVersion === fromVersion)는 함께 삭제하여
   *  설계서와 메모 라이프사이클의 정합성을 맞춘다. 더 과거 버전(v1.0 등) 메모는 보존. */
  restoreDesignSnapshot: (snapshotIndex) => {
    const s = get();
    const snap = (s.designSnapshots || [])[snapshotIndex];
    if (!snap) {
      get().addNotification?.("스냅샷을 찾을 수 없습니다.", "error");
      return;
    }
    const currentVersion = (() => {
      const lastSync = [...(s.chatHistory || [])].reverse().find(
        (m) => m && m.role === "system_marker" && m.kind === "sync"
      );
      return lastSync?.version || `v1.${(s.designSnapshots || []).length}`;
    })();

    // fromVersion에 새로 반영된 메모만 제거 — 더 과거 버전 메모는 그대로 둔다
    const memosToDrop = (s.userComments || []).filter(
      (m) => m.reflectedVersion === currentVersion
    );

    set({
      resultData: snap.resultData,
      requirements_rtm: snap.requirements_rtm || [],
      components: snap.components || [],
      apis: snap.apis || [],
      tables: snap.tables || [],
      tech_stacks: snap.tech_stacks || [],
      project_structure: snap.project_structure || null,
      test_cases: snap.test_cases || null,
      recommendations: snap.recommendations || [],
      sa_artifacts: snap.sa_artifacts || null,
      chatHistory: [
        ...(s.chatHistory || []),
        {
          role: "system_marker",
          kind: "rollback",
          fromVersion: currentVersion,
          toVersion: snap.version,
          appliedAt: new Date().toISOString(),
        },
      ],
    });

    // 메모 삭제는 set() 이후에 비동기로 처리 — removeComment가 백엔드 DELETE도 호출
    memosToDrop.forEach((m) => {
      if (m && m.id) get().removeComment?.(m.id);
    });

    const droppedNote = memosToDrop.length > 0
      ? ` · 메모 ${memosToDrop.length}건 삭제`
      : "";
    get().addNotification?.(
      `${currentVersion} → ${snap.version} 롤백 완료${droppedNote}`,
      "success",
      3000
    );
  },

  clearDesignSnapshots: () => set({ designSnapshots: [], designSnapshotCounter: 0 }),

  createSession: (initialTitle = null) => {
    const state = get();
    const id = Date.now().toString();
    const now = new Date();
    const session = {
      id,
      name: initialTitle && initialTitle !== "새 프로젝트" ? initialTitle : `세션 ${now.toLocaleDateString("ko")} ${now.toLocaleTimeString("ko", { hour: "2-digit", minute: "2-digit" })}`,
      createdAt: now.getTime(),
      team_id: state.currentUser?.team_id || null,
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
      designSnapshots: [],
      designSnapshotCounter: 0,
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
        designSnapshots: state.designSnapshots,
        designSnapshotCounter: state.designSnapshotCounter,
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

    // 즉시 세션 상태 반영 (RAG 복구 전 로컬 데이터 우선) + ModeBridge 닫기
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
      designSnapshots: session.designSnapshots || [],
      designSnapshotCounter: session.designSnapshotCounter || (session.designSnapshots?.length || 0),
      showOnboardingBridge: false,
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
    // 활성 세션이 없으면 다른 세션의 메모를 노출하지 않도록 즉시 비운다.
    if (!currentSessionId) {
      set({ userComments: [] });
      return;
    }
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
        reflectedVersion: m.metadata?.reflected_version || null,
        createdAt: Date.now(),
      }));

      const local = get().userComments || [];
      const inFlight = local.filter(
        (c) => typeof c?.id === "string" && c.id.startsWith("temp_")
      );

      // 서버가 빈 목록을 반환해도 저장 완료된 로컬 메모를 날리지 않는다.
      // (새 세션 시작 직후 syncMemos가 호출되면 서버엔 아직 없지만 로컬엔 있을 수 있음)
      if (serverItems.length === 0 && local.some((c) => !c.id?.startsWith("temp_"))) {
        // inFlight만 제거하고 나머지는 유지
        set({ userComments: local.filter((c) => !c.id?.startsWith("temp_")) });
        return;
      }

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
    // 활성 프로젝트가 없으면 메모 자체를 저장하지 않는다 (chat_global 누적 차단).
    if (!currentSessionId) {
      get().addNotification("활성 프로젝트가 없어 메모를 저장하지 못했습니다.", "warning", 3000);
      return;
    }
    const tempId = "temp_" + Date.now() + "_" + Math.random().toString(36).slice(2, 6);
    const sessionIdForPersist = currentSessionId;

    console.log(
      `[addComment] 진입 — backendPort=${backendPort} currentSessionId=${currentSessionId} ` +
      `sessionIdForPersist=${sessionIdForPersist} text="${(comment?.text || "").slice(0, 50)}"`
    );

    // 1. 로컬 상태 즉시 반영 (UI 반응성)
    set((s) => ({
      userComments: [...s.userComments, { id: tempId, ...comment, createdAt: Date.now() }],
    }));

    // 2. 백엔드 영속화 (위 가드로 currentSessionId가 보장된 상태).
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
  markMemosApplied: async (memoIds, opts = {}) => {
    const { backendPort } = get();
    if (!Array.isArray(memoIds) || memoIds.length === 0) return;
    const reflectedVersion = opts.reflectedVersion || null;
    if (!backendPort) {
      console.warn("[markMemosApplied] backendPort 없어 백엔드 갱신 스킵");
      return;
    }
    try {
      const res = await sessionService.applyMemos(backendPort, memoIds, reflectedVersion);
      if (res?.status === "ok") {
        const ts = new Date().toISOString();
        set((s) => ({
          userComments: (s.userComments || []).map((c) =>
            memoIds.includes(c.id)
              ? {
                  ...c,
                  applied: true,
                  appliedAt: ts,
                  ...(reflectedVersion ? { reflectedVersion } : {}),
                }
              : c
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

  /** 모든 작업 상태를 초기화하여 ModeBridge → 빈 프롬프트 흐름으로 돌아간다.
   *  현재 세션은 sessions 배열에 그대로 남아 라이브러리에서 다시 열 수 있음. */
  startNewProject: () => {
    set({
      currentSessionId: null,
      chatHistory: [],
      chatInput: "",
      userComments: [],
      designSnapshots: [],
      designSnapshotCounter: 0,
      showOnboardingBridge: true,
      pipelineStatus: "idle",
      pipelineError: null,
      pipelineNodes: {},
      thinkingLog: [],
      pipelineType: "analysis",
      agileVerifyResult: null,
      agileImpactResult: null,
      lastIdeaReady: false,
      lastIdeaSummary: "",
      lastSuggestedMode: null,
      lastFollowups: [],
      _syncInFlight: false,
      _syncMemoIdsForApply: [],
      _syncTargetVersion: null,
      activeViewportTab: { kind: "output", id: "home" },
      lastOutputTab: "home",
      ...EMPTY_RESULT_FIELDS,
    });
  },

  updateSessionName: (id, name) => {
    set((state) => {
      const updated = state.sessions.map((s) => (s.id === id ? { ...s, name } : s));
      persistSessions(updated);
      return { sessions: updated };
    });
  },
});
