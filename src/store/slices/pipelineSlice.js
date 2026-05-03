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

  // Debug logs
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

    const recommendations = data.recommendations || data.sa_advisor_output?.recommendations || [];
    if (recommendations.length > 0) {
      const existingTexts = new Set(get().userComments.map((c) => c.text));
      const newMemos = recommendations
        .filter((r) => !existingTexts.has(r.action))
        .map((r) => ({
          id: `auto_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
          text: r.action,
          selectedText: r.target,
          section: `Advisor (${r.priority})`,
          createdAt: Date.now(),
        }));

      if (newMemos.length > 0) {
        set((state) => ({ userComments: [...state.userComments, ...newMemos] }));
      }
    }

    const nextPipelineType = inferPipelineTypeFromResult(data);
    const defaultOutputTab = nextPipelineType === "develop_plan" ? "overview" : "memo";

    const nextResultData = {
      pipelineStatus: "done",
      pipelineType: nextPipelineType,
      ...spreadResultData(data),
      chatHistory: data.chat_history || get().chatHistory,
      activeViewportTab: { kind: "output", id: defaultOutputTab },
      lastOutputTab: defaultOutputTab,
    };

    set(nextResultData);
  },

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

  resetPipeline: () => set(() => ({
    pipelineStatus: "idle",
    pipelineError: null,
    pipelineNodes: {},
    thinkingLog: [],
    ...EMPTY_RESULT_FIELDS,
    activeViewportTab: { kind: "output", id: "home" },
    chatHistory: [],
  })),
});
