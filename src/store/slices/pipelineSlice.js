import {
  EMPTY_RESULT_FIELDS,
  MODE_TO_ACTION_TYPE,
  MODE_TO_PIPELINE_TYPE,
  inferPipelineTypeFromResult,
  spreadResultData,
  normalizeMode
} from "../storeHelpers";

export const createPipelineSlice = (set, get) => ({
  pipelineStatus: "idle",
  pipelineError: null,
  pipelineNodes: {},
  thinkingLog: [],
  pipelineType: "analysis",
  resultData: null,
  agileVerifyResult: null,
  agileImpactResult: null,
  ...EMPTY_RESULT_FIELDS,

  setAgileVerifyResult: (result) => set({ agileVerifyResult: result }),
  setAgileImpactResult: (result) => set({ agileImpactResult: result }),

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

    // UPDATE 모드에서 components/apis/tables는 백엔드 결과를 그대로 사용.
    // 백엔드 component_scheduler/sa_unified_modeler의 UPDATE_PROMPT가 이미
    // 기존 항목 보존 + 신규 항목 추가를 처리하므로 프론트엔드 병합 불필요.
    // (이전 스토어 데이터와 병합하면 stale 세션 데이터가 섞여 로컬과 공유 DB 표시가 달라지는 버그 발생)

    const nextResultData = {
      pipelineStatus: "done",
      pipelineType: inferPipelineTypeFromResult(data),
      ...spreadResultData(data),
      chatHistory: data.chat_history || get().chatHistory,
      activeViewportTab: { kind: "output", id: "memo" }, // 리포트 대신 메모 탭으로 즉시 이동
      lastOutputTab: "memo",
    };

    set(nextResultData);
  },

  startAnalysis: (idea, context = "", apiKey = "", model = "gemini-3.1-flash-lite-preview", selectedMode = "create", initialTitle = null) => {
    const { currentUser } = get();
    if (!currentUser?.github_id) {
      get().addNotification("GitHub 로그인이 필요합니다. 설정에서 연결하세요.", "error");
      return;
    }
    if (currentUser.role !== "pm") {
      get().addNotification("LLM 분석은 PM 권한이 필요합니다. PM에게 문의하세요.", "error");
      return;
    }
    const normalizedMode = normalizeMode(selectedMode);
    const sourceDir = get().projectFolder || "";
    get().createSession(initialTitle);
    
    // 분석 시작 시 기존 메모(userComments)는 유지하고, 
    // 결과 필드는 running 상태에 맞춰 필요한 것만 초기화합니다.
    set({
      pipelineStatus: "running",
      pipelineError: null,
      pipelineNodes: {},
      thinkingLog: [],
      pipelineType: MODE_TO_PIPELINE_TYPE[normalizedMode] || "analysis_create",
      // EMPTY_RESULT_FIELDS 중 데이터 표시와 직결되는 핵심 필드만 초기화 (점진적 업데이트를 위함)
      // resultData: null, // 기존 데이터를 바로 날리지 않고 새 결과가 오면 덮어씁니다.
      chatHistory: [],
      chatInput: "",
      selectedMode: normalizedMode,
      activeViewportTab: { kind: "output", id: "progress" },
      lastOutputTab: "progress",
    });
    get().sendWsMessage("analyze", {
      idea, context, api_key: apiKey, model,
      action_type: MODE_TO_ACTION_TYPE[normalizedMode],
      source_dir: sourceDir,
      auth_token: get().authToken,
    });
  },

  startMemoDrivenUpdate: (memoIds) => {
    const { currentUser } = get();
    if (!currentUser?.github_id) {
      get().addNotification("GitHub 로그인이 필요합니다. 설정에서 연결하세요.", "error");
      return;
    }
    if (currentUser.role !== "pm") {
      get().addNotification("LLM 분석은 PM 권한이 필요합니다. PM에게 문의하세요.", "error");
      return;
    }
    const { userComments, apiKey, model, createSession, projectFolder } = get();
    const memos = (userComments || []).filter((c) => memoIds.includes(c.id));
    const memoText = memos
      .map((m, i) => `${i + 1}. [${m.section || "일반"}] ${m.text}`)
      .join('\n');

    // 기존 미적용 메모를 아카이브(applied=true)로 마킹한 후 새 세션 시작
    const prevMemos = get().userComments || [];
    const archivedMemos = prevMemos.map((m) =>
      m.applied ? m : { ...m, applied: true, appliedAt: new Date().toISOString() }
    );
    set({ userComments: archivedMemos });
    createSession("지적사항 반영 업데이트");
    set({
      pipelineStatus: "running",
      pipelineError: null,
      pipelineNodes: {},
      thinkingLog: [],
      pipelineType: "analysis_update",
      chatHistory: [],
      chatInput: "",
      agileImpactResult: null,
      activeViewportTab: { kind: "output", id: "progress" },
      lastOutputTab: "progress",
    });
    // 이전 분석 결과를 JSON으로 직렬화하여 SA 파이프라인이 기존 설계를 인식하도록 전달
    const prevDesign = {
      requirements_rtm: get().requirements_rtm || [],
      components: get().components || [],
      apis: get().apis || [],
      tables: get().tables || [],
      tech_stacks: get().tech_stacks || [],
    };
    const prevContext = `[이전 분석 결과 — 반드시 아래 설계를 기반으로 업데이트하세요]\n${JSON.stringify(prevDesign, null, 2)}`;

    get().sendWsMessage("analyze", {
      idea: memoText,
      context: prevContext,
      api_key: apiKey || "",
      model: model || "gemini-3.1-flash-lite-preview",
      action_type: "UPDATE",
      source_dir: projectFolder || "",
      auth_token: get().authToken,
    });
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

    get().sendWsMessage("idea_chat", {
      message: text,
      chat_history: history,
      previous_result: get().resultData || {},
      api_key: apiKey || "",
      model: model || "gemini-3.1-flash-lite-preview",
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
