import { DEFAULT_VIEWPORT_TAB, normalizeMode, normalizeOutputTabId } from "../storeHelpers";

export const createUiSlice = (set, get) => ({
  isDarkMode: localStorage.getItem("theme") ? localStorage.getItem("theme") === "dark" : true,
  activeViewportTab: { ...DEFAULT_VIEWPORT_TAB },
  lastOutputTab: "home",
  selectedMode: "create",

  setDarkMode: (isDark) => {
    set({ isDarkMode: isDark });
    localStorage.setItem("theme", isDark ? "dark" : "light");
  },
  toggleDarkMode: () => get().setDarkMode(!get().isDarkMode),

  activateCodeTab: (tabId) => set({ activeViewportTab: { kind: "code", id: tabId } }),
  activateOutputTab: (tabId) => set({
    activeViewportTab: { kind: "output", id: tabId },
    lastOutputTab: tabId,
  }),

  setSelectedMode: (mode) => set({ selectedMode: normalizeMode(mode) }),
});
