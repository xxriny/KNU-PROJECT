// Platform abstraction layer — swap this file's implementation for React Native (mobile).
// All window.electronAPI calls are isolated here; no other file should reference it directly.

const electron = typeof window !== "undefined" ? window.electronAPI : null;

export const platform = {
  /** Returns the backend port. Electron provides it dynamically; fallback is 8765. */
  getBackendPort: async () => {
    if (electron?.getBackendPort) return electron.getBackendPort();
    return 8765;
  },

  /** Syncs the native title-bar color to the current theme. No-op on non-Electron. */
  setTitleBarTheme: (isDarkMode) => {
    electron?.setTitleBarTheme?.(isDarkMode);
  },

  /** Opens a URL in the system browser. Electron uses IPC; fallback uses window.open. */
  openExternal: (url) => {
    if (electron?.openGithubAuth) {
      electron.openGithubAuth(url);
    } else {
      window.open(url, "_blank");
    }
  },

  /** Opens a native folder-picker dialog. Returns the path string or null. */
  selectFolder: async () => {
    if (electron?.selectFolder) return electron.selectFolder();
    return null;
  },

  /** True when running inside Electron. */
  isElectron: !!electron,
};
