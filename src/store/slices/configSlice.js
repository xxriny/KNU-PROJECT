/**
 * Settings/config slice
 */
export const createConfigSlice = (set, get) => ({
  apiKey: localStorage.getItem("pm_api_key") || "",
  model: localStorage.getItem("pm_model") || "gemini-3.1-flash-lite-preview",
  backendHasKey: false,
  availableModels: ["gemini-3.1-flash-lite-preview"],

  setApiKey: (key) => {
    localStorage.setItem("pm_api_key", key);
    set({ apiKey: key });
  },
  setModel: (model) => {
    localStorage.setItem("pm_model", model);
    set({ model });
  },

  fetchConfig: async (port) => {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/api/config`);
      if (!res.ok) return;
      const cfg = await res.json();
      const nextAvailableModels = Array.isArray(cfg.available_models) && cfg.available_models.length > 0
        ? cfg.available_models
        : ["gemini-3.1-flash-lite-preview"];
      
      const currentModel = get().model;
      if (cfg.has_api_key) set({ backendHasKey: true });
      
      const updatedModel = nextAvailableModels.includes(currentModel)
        ? currentModel
        : (cfg.default_model && nextAvailableModels.includes(cfg.default_model)
            ? cfg.default_model
            : nextAvailableModels[0]);
            
      set({
        availableModels: nextAvailableModels,
        model: updatedModel,
      });
      // 동기화된 모델도 저장
      localStorage.setItem("pm_model", updatedModel);
    } catch (e) {
      console.warn("[Config] Failed to fetch /api/config:", e);
    }
  },
});
