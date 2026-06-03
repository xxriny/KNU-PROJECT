import { wsUrl } from "../../api/apiClient";

/**
 * WebSocket connection slice
 */
export const createWsSlice = (set, get) => ({
  backendPort: null,
  wsConnection: null,
  wsStatus: "disconnected",
  wsRetryCount: 0,

  setBackendPort: (port) => set({ backendPort: port }),
  setWsStatus: (status) => set({ wsStatus: status }),

  connectWebSocket: (port) => {
    const currentWs = get().wsConnection;
    if (currentWs && currentWs.readyState === WebSocket.OPEN) return;

    set({ wsStatus: "connecting" });
    const ws = new WebSocket(wsUrl("/ws/pipeline", port));

    ws.onopen = () => {
      console.log("[WS] Connected to backend");
      set({ wsConnection: ws, wsStatus: "connected", wsRetryCount: 0 });
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
      const { backendPort, wsRetryCount } = get();
      const delay = Math.min(3000 * Math.pow(2, wsRetryCount), 60_000);
      set({ wsRetryCount: wsRetryCount + 1 });
      setTimeout(() => {
        const { backendPort: port, wsStatus } = get();
        if (port && wsStatus === "disconnected") {
          get().connectWebSocket(port);
        }
      }, delay);
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
