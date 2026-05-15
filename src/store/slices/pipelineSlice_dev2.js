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
  ...EMPTY_RESULT_FIELDS,

  // ?붾쾭洹??쒖뒪??  debugLogs: [],
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
        get().addNotification(`?뚯씠?꾨씪???ㅻ쪟: ${data.message}`, "error");
        break;
      case "rag_retrieval":
      case "rag_status":
        // RAG 愿???곹깭???꾩슂 ??異붽? (?꾩옱???앸왂 媛??
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

    // AI ?대뱶諛붿씠? ?쒖븞?ы빆??硫붾え濡??먮룞 蹂??    const recommendations = data.recommendations || data.sa_advisor_output?.recommendations || [];
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
        // 諛깆뿏?쒖뿉???숆린??(?좏깮 ?ы빆, ?ш린?쒕뒗 濡쒖뺄 UI ?곗꽑 諛섏쁺)
        set((state) => ({ userComments: [...state.userComments, ...newMemos] }));
      }
    }

    const nextResultData = {
      pipelineStatus: "done",
      pipelineType: inferPipelineTypeFromResult(data),
      ...spreadResultData(data),
      chatHistory: data.chat_history || get().chatHistory,
      activeViewportTab: { kind: "output", id: "memo" }, // 由ы룷?????硫붾え ??쑝濡?利됱떆 ?대룞
      lastOutputTab: "memo",
    };

    set(nextResultData);
  },

  startAnalysis: (idea, context = "", apiKey = "", model = "gemini-3.1-flash-lite-preview", selectedMode = "create", initialTitle = null) => {
    const normalizedMode = normalizeMode(selectedMode);
    const sourceDir = get().projectFolder || "";
    get().createSession(initialTitle);
    
    // 遺꾩꽍 ?쒖옉 ??湲곗〈 硫붾え(userComments)???좎??섍퀬, 
    // 寃곌낵 ?꾨뱶??running ?곹깭??留욎떠 ?꾩슂??寃껊쭔 珥덇린?뷀빀?덈떎.
    set({
      pipelineStatus: "running",
      pipelineError: null,
      pipelineNodes: {},
      thinkingLog: [],
      pipelineType: MODE_TO_PIPELINE_TYPE[normalizedMode] || "analysis_create",
      // EMPTY_RESULT_FIELDS 以??곗씠???쒖떆? 吏곴껐?섎뒗 ?듭떖 ?꾨뱶留?珥덇린??(?먯쭊???낅뜲?댄듃瑜??꾪븿)
      // resultData: null, // 湲곗〈 ?곗씠?곕? 諛붾줈 ?좊━吏 ?딄퀬 ??寃곌낵媛 ?ㅻ㈃ ??뼱?곷땲??
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
    });
  },

  sendIdeaChat: (message, apiKey, model) => {
    const text = (message || "").trim();
    if (!text) return;

    // chatHistory媛 ?대? ?ъ슜??硫붿떆吏瑜??ы븿???곹깭濡??몄텧?섎?濡?
    // 諛깆뿏?쒓? user_request瑜??ㅼ떆 history??append?섏? ?딅룄濡?留덉?留?user 硫붿떆吏瑜??쒖쇅
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
    // userComments: [], // 硫붾え ?좎?
  })),
});
