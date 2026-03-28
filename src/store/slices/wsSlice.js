/**
 * WebSocket connection slice
 */
export const createWsSlice = (set, get) => ({
  backendPort: null,
  wsConnection: null,
  wsStatus: "disconnected",

  setBackendPort: (port) => set({ backendPort: port }),
  setWsStatus: (status) => set({ wsStatus: status }),

  connectWebSocket: (port) => {
    const currentWs = get().wsConnection;
    if (currentWs && currentWs.readyState === WebSocket.OPEN) return;

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
});
