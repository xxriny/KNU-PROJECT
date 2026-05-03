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

  startAnalysis: (idea, context = "", apiKey = "", model = "gemini-2.5-flash", selectedMode = "create") => {
    const normalizedMode = normalizeMode(selectedMode);
    const sourceDir = get().projectFolder || "";
    get().createSession();
    
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
