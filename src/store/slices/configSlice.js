/**
 * Settings/config slice
 */
export const createConfigSlice = (set, get) => ({
  apiKey: "",
  model: "gemini-2.5-flash",
  backendHasKey: false,
  availableModels: ["gemini-2.5-flash"],

  setApiKey: (key) => set({ apiKey: key }),
  setModel: (model) => set({ model }),

  fetchConfig: async (port) => {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/api/config`);
      if (!res.ok) return;
      const cfg = await res.json();
      const nextAvailableModels = Array.isArray(cfg.available_models) && cfg.available_models.length > 0
        ? cfg.available_models
        : ["gemini-2.5-flash"];
      const currentModel = get().model;
      if (cfg.has_api_key) set({ backendHasKey: true });
      set({
        availableModels: nextAvailableModels,
        model: nextAvailableModels.includes(currentModel)
          ? currentModel
          : (cfg.default_model && nextAvailableModels.includes(cfg.default_model)
              ? cfg.default_model
              : nextAvailableModels[0]),
      });
    } catch (e) {
      console.warn("[Config] Failed to fetch /api/config:", e);
    }
  },
});
