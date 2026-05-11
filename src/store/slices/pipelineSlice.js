import {
  EMPTY_RESULT_FIELDS,
  MODE_TO_ACTION_TYPE,
  MODE_TO_PIPELINE_TYPE,
  inferPipelineTypeFromResult,
  spreadResultData,
  normalizeMode,
  synthesizeMemoIdea
} from "../storeHelpers";

export const createPipelineSlice = (set, get) => ({
  pipelineStatus: "idle",
  pipelineError: null,
  pipelineNodes: {},
  thinkingLog: [],
  pipelineType: "analysis",
  resultData: null,
  // 메모 반영 UPDATE 진행 중일 때, 분석 성공 직후 'applied' 처리할 메모 ID 목록.
  pendingAppliedMemoIds: [],
  ...EMPTY_RESULT_FIELDS,

  // 디버그 시스템
  debugLogs: [],
  addDebugLog: (log) => set((state) => ({
    debugLogs: [{ ...log, timestamp: Date.now() }, ...state.debugLogs].slice(0, 50)
  })),

  _handleWsMessage: (msg) => {
    const { type, node, data } = msg;
    switch (type) {
      case "status":
        set((state) => ({ pipelineNodes: { ...state.pipelineNodes, [node]: data.status } }));
        break;
      case "thinking":
        set((state) => ({
          thinkingLog: [...state.thinkingLog, { node, text: data.text, timestamp: Date.now() }]
        }));
        break;
      case "result":
        get()._processResult(data, node);
        break;
      case "error":
        set({ pipelineStatus: "error", pipelineError: data.message });
        get().addDebugLog({
          level: "error",
          message: `Pipeline WS Error: ${data.message}`,
          rawData: data
        });
        get().addNotification(`파이프라인 오류: ${data.message}`, "error");
        break;
      case "rag_retrieval":
      case "rag_status":
        // RAG 관련 상태는 필요 시 추가 (현재는 생략 가능)
        break;
    }
  },

  _processResult: (data, node = "complete") => {
    if (node === "idea_chat") {
      const reply = data.chat_reply || data.assistant_message || "";
      if (reply) {
        set((state) => ({ chatHistory: [...state.chatHistory, { role: "assistant", content: reply }] }));
      }

      // 사용자가 대화에서 "이 기능 추가/메모해줘" 의도를 명시했을 때만
      // LLM이 notes_to_add를 채워서 보내준다. 중복 텍스트는 건너뛰고 addComment로 저장.
      const notesToAdd = Array.isArray(data.notes_to_add) ? data.notes_to_add : [];
      // 진단: WS로 메모가 도착했는지 즉시 확인 (회귀 발생 시 콘솔에서 추적)
      console.log(
        `[idea_chat] notes_to_add 수신: ${notesToAdd.length}건`,
        notesToAdd
      );
      // 백엔드(run_idea_chat)가 이미 ChromaDB(memo_db)에 영속화한 메모 목록을 받는다.
      // notes_to_add 항목은 { id, text, section } 형식이며, id는 백엔드가 부여한 진짜 ID.
      // 프론트는 (1) 로컬 userComments에 ID 기반 dedup으로 즉시 push하고
      //         (2) syncMemos로 한 번 더 백엔드와 동기화해 안전망을 확보한다.
      if (notesToAdd.length > 0) {
        const existingIds = new Set((get().userComments || []).map((c) => c.id));
        const existingTexts = new Set(
          (get().userComments || []).map((c) => (c.text || "").trim())
        );
        const newLocal = notesToAdd
          .filter((n) => {
            const text = (n?.text || "").trim();
            if (!text) return false;
            if (n?.id && existingIds.has(n.id)) return false;
            if (existingTexts.has(text)) return false;
            return true;
          })
          .map((n) => ({
            id: n.id || `chat_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
            text: (n.text || "").trim(),
            selectedText: "",
            section: n.section || "Idea Chat",
            detail: (n.detail || "").trim(),
            createdAt: Date.now(),
          }));

        if (newLocal.length > 0) {
          set((state) => ({ userComments: [...state.userComments, ...newLocal] }));
          get().addNotification(
            `AI 어시스턴트가 메모 ${newLocal.length}건을 추가했습니다.`,
            "success"
          );
        }

        // 백엔드 상태와 한 번 더 동기화 (다음 MemoManager 마운트를 기다리지 않도록).
        if (typeof get().syncMemos === "function") {
          Promise.resolve(get().syncMemos()).catch(() => {});
        }
      }
      return;
    }

    // AI 어드바이저 제안사항을 메모로 자동 변환
    const recommendations = data.recommendations || data.sa_advisor_output?.recommendations || [];
    if (recommendations.length > 0) {
      const existingTexts = new Set(get().userComments.map(c => c.text));
      const newMemos = recommendations
        .filter(r => !existingTexts.has(r.action))
        .map(r => ({
          id: `auto_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
          text: r.action,
          selectedText: r.target,
          section: `Advisor (${r.priority})`,
          createdAt: Date.now(),
        }));
      
      if (newMemos.length > 0) {
        // 백엔드에도 동기화 (선택 사항, 여기서는 로컬 UI 우선 반영)
        set((state) => ({ userComments: [...state.userComments, ...newMemos] }));
      }
    }

    const nextResultData = {
      pipelineStatus: "done",
      pipelineType: inferPipelineTypeFromResult(data),
      ...spreadResultData(data),
      chatHistory: data.chat_history || get().chatHistory,
      activeViewportTab: { kind: "output", id: "memo" }, // 리포트 대신 메모 탭으로 즉시 이동
      lastOutputTab: "memo",
    };

    set(nextResultData);

    // ── 메모 반영 UPDATE 후처리 ────────────────────────────
    // startMemoDrivenUpdate가 pendingAppliedMemoIds에 채워뒀던 ID들을
    // 분석 성공 시점에 'applied' 처리하고 비운다.
    const pendingIds = get().pendingAppliedMemoIds;
    console.log(
      `[memo-driven-update] _processResult 후처리: pendingIds=${pendingIds?.length || 0}건, pipeline_type=${data?.pipeline_type}`
    );
    if (Array.isArray(pendingIds) && pendingIds.length > 0) {
      const markFn = get().markMemosApplied;
      if (typeof markFn === "function") {
        Promise.resolve(markFn(pendingIds))
          .then(() => console.log(`[memo-driven-update] markMemosApplied 완료 (${pendingIds.length}건)`))
          .catch((err) =>
            console.error("[memo-driven-update] markMemosApplied 실패:", err)
          );
      } else {
        console.warn("[memo-driven-update] markMemosApplied 함수를 찾을 수 없음");
      }
      set({ pendingAppliedMemoIds: [] });
      get().addNotification(
        `메모 ${pendingIds.length}건이 반영되었습니다. 이전 메모 보기에서 확인 가능합니다.`,
        "success"
      );
    }
  },

  startAnalysis: (idea, context = "", apiKey = "", model = "gemini-3.1-flash-lite-preview", selectedMode = "create", initialTitle = null, options = {}) => {
    // options.reuseSession=true 이면 currentSessionId 그대로 두고 새 세션 생성을 건너뛴다.
    // "메모 반영 UPDATE"처럼 의미상 같은 프로젝트의 점진적 갱신인 흐름에서 사용 — 새 세션을 만들면
    // syncMemos가 currentSessionId 변경으로 인해 빈 응답을 받아 화면에서 메모가 사라지는 회귀가 있다.
    const { reuseSession = false } = options || {};
    const normalizedMode = normalizeMode(selectedMode);
    const sourceDir = get().projectFolder || "";
    if (!reuseSession) {
      get().createSession(initialTitle);
    }

    // 분석 시작 시 기존 메모(userComments)는 유지하고,
    // 결과 필드는 running 상태에 맞춰 필요한 것만 초기화합니다.
    const setPayload = {
      pipelineStatus: "running",
      pipelineError: null,
      pipelineNodes: {},
      thinkingLog: [],
      pipelineType: MODE_TO_PIPELINE_TYPE[normalizedMode] || "analysis_create",
      // EMPTY_RESULT_FIELDS 중 데이터 표시와 직결되는 핵심 필드만 초기화 (점진적 업데이트를 위함)
      // resultData: null, // 기존 데이터를 바로 날리지 않고 새 결과가 오면 덮어씁니다.
      chatInput: "",
      selectedMode: normalizedMode,
      activeViewportTab: { kind: "output", id: "progress" },
      lastOutputTab: "progress",
    };
    // reuseSession 흐름(예: "메모 반영 UPDATE")에서는 채팅 기록도 같은 세션의 연속이므로
    // 비우지 않는다. 일반 CREATE/UPDATE/REVERSE 진입은 새 세션 시작이라 빈 채팅이 자연스러움.
    if (!reuseSession) {
      setPayload.chatHistory = [];
    }
    set(setPayload);
    get().sendWsMessage("analyze", {
      idea, context, api_key: apiKey, model,
      action_type: MODE_TO_ACTION_TYPE[normalizedMode],
      source_dir: sourceDir,
    });
  },

  /**
   * 사용자가 선택한 메모 ID들을 idea로 합성해 UPDATE 분석을 시작한다.
   * 분석 성공 시 _processResult가 pendingAppliedMemoIds를 보고
   * 자동으로 markMemosApplied를 호출 → 메모는 보존되며 'applied' 표시만.
   */
  startMemoDrivenUpdate: (selectedIds) => {
    const state = get();
    const {
      userComments,
      projectFolder,
      apiKey,
      model,
      pipelineStatus,
      resultData,
    } = state;

    if (pipelineStatus === "running") {
      state.addNotification("이미 분석이 진행 중입니다.", "warning");
      return;
    }
    if (!Array.isArray(selectedIds) || selectedIds.length === 0) {
      state.addNotification("반영할 메모를 선택하세요.", "warning");
      return;
    }
    if (!projectFolder) {
      state.addNotification(
        "UPDATE는 프로젝트 폴더가 필요합니다. 홈 화면에서 폴더를 먼저 선택해주세요.",
        "warning"
      );
      return;
    }
    if (!resultData) {
      state.addNotification(
        "기존 분석 결과가 없습니다. 먼저 분석을 한 번 실행해주세요.",
        "warning"
      );
      return;
    }

    const idSet = new Set(selectedIds);
    const selected = (userComments || []).filter((c) => idSet.has(c.id));
    if (selected.length === 0) {
      state.addNotification("선택된 메모를 찾을 수 없습니다.", "warning");
      return;
    }

    const idea = synthesizeMemoIdea(selected);

    // 분석 성공 시 자동으로 applied 표시할 ID 목록을 미리 기록.
    set({ pendingAppliedMemoIds: selected.map((c) => c.id) });

    state.addNotification(
      `메모 ${selected.length}건을 반영해 UPDATE 분석을 시작합니다.`,
      "info"
    );

    // reuseSession=true 로 호출해 현재 currentSessionId를 그대로 유지한다.
    // → markMemosApplied 이후 MemoManager의 syncMemos가 같은 session_id로 조회해
    //    'applied' 표시된 메모들이 "이전 메모 보기"에 정상 노출된다.
    state.startAnalysis(
      idea,
      "",
      apiKey,
      model,
      "update",
      null,
      { reuseSession: true }
    );
  },

  sendIdeaChat: (message, apiKey, model) => {
    const text = (message || "").trim();
    if (!text) return;

    // chatHistory가 이미 사용자 메시지를 포함한 상태로 호출되므로,
    // 백엔드가 user_request를 다시 history에 append하지 않도록 마지막 user 메시지를 제외
    const all = get().chatHistory;
    const last = all[all.length - 1];
    const history =
      last && last.role === "user" && last.content === text
        ? all.slice(0, -1)
        : all;

    // 백엔드가 채팅 메모를 memo_db에 직접 영속화할 때 사용할 세션 키.
    // currentSessionId가 있으면 그걸로 묶어 syncMemos 시 같은 세션에 노출되고,
    // 없으면 chat_global 폴백 (백엔드 동일 폴백과 일치).
    const sessionId = get().currentSessionId || "chat_global";

    get().sendWsMessage("idea_chat", {
      message: text,
      chat_history: history,
      previous_result: get().resultData || {},
      api_key: apiKey || "",
      model: model || "gemini-3.1-flash-lite-preview",
      session_id: sessionId,
    });
  },

  resetPipeline: () => set((state) => ({
    pipelineStatus: "idle",
    pipelineError: null,
    pipelineNodes: {},
    thinkingLog: [],
    ...EMPTY_RESULT_FIELDS,
    activeViewportTab: { kind: "output", id: "home" },
    chatHistory: [],
    // userComments: [], // 메모 유지
  })),
});
