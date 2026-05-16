/**
 * authSlice — 인증 상태 관리
 * 로그인/로그아웃, 현재 사용자, 역할 정보
 */

const AUTH_KEY = "navigator_auth";

function loadStoredAuth() {
  try {
    const raw = localStorage.getItem(AUTH_KEY);
    if (!raw) return { token: null, user: null };
    return JSON.parse(raw);
  } catch {
    return { token: null, user: null };
  }
}

function saveAuth(token, user) {
  localStorage.setItem(AUTH_KEY, JSON.stringify({ token, user }));
}

function clearStoredAuth() {
  localStorage.removeItem(AUTH_KEY);
}

const stored = loadStoredAuth();

export const createAuthSlice = (set, get) => ({
  // ── 상태 ────────────────────────────────────────────────
  authToken: stored.token,
  currentUser: stored.user,
  userRole: stored.user?.role ?? null,
  authChecked: false,       // 최초 상태 체크 완료 여부
  hasUsers: null,           // null = 아직 체크 안 함

  // ── 액션 ────────────────────────────────────────────────
  setAuth: (token, user) => {
    saveAuth(token, user);
    set({ authToken: token, currentUser: user, userRole: user?.role ?? null });
  },

  clearAuth: () => {
    clearStoredAuth();
    set({ authToken: null, currentUser: null, userRole: null });
  },

  isAuthenticated: () => !!get().authToken,

  setAuthChecked: (checked) => set({ authChecked: checked }),
  setHasUsers: (v) => set({ hasUsers: v }),

  // ── API 헬퍼 ────────────────────────────────────────────
  getAuthHeader: () => {
    const token = get().authToken;
    return token ? { Authorization: `Bearer ${token}` } : {};
  },

  /** 앱 시작 시 서버에서 사용자 존재 여부 확인 */
  checkAuthStatus: async () => {
    const { backendPort } = get();
    if (!backendPort) return;
    try {
      const res = await fetch(`http://127.0.0.1:${backendPort}/auth/status`);
      const data = await res.json();
      set({ hasUsers: data.has_users, authChecked: true });

      // 저장된 토큰이 있으면 유효성 재확인
      if (get().authToken) {
        const meRes = await fetch(`http://127.0.0.1:${backendPort}/auth/me`, {
          headers: get().getAuthHeader(),
        });
        if (!meRes.ok) {
          get().clearAuth();
        }
      }
    } catch {
      set({ authChecked: true });
    }
  },

  /** 로그인 */
  login: async (email, password) => {
    const { backendPort } = get();
    const res = await fetch(`http://127.0.0.1:${backendPort}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "로그인 실패");
    }
    const data = await res.json();
    get().setAuth(data.access_token, data.user);
    return data.user;
  },

  /** 회원가입 */
  register: async (payload) => {
    const { backendPort } = get();
    const res = await fetch(`http://127.0.0.1:${backendPort}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "회원가입 실패");
    }
    const data = await res.json();
    get().setAuth(data.access_token, data.user);
    set({ hasUsers: true });
    return data.user;
  },

  /** 로그아웃 */
  logout: () => {
    get().clearAuth();
  },

  /** GitHub Device Flow 시작 */
  startGithubDeviceFlow: async () => {
    const { backendPort } = get();
    const res = await fetch(`http://127.0.0.1:${backendPort}/auth/github/device-start`, {
      method: "POST",
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "GitHub 인증 시작 실패");
    return data;
  },

  /** GitHub Device Flow 폴링 */
  pollGithubDeviceFlow: async (device_code) => {
    const { backendPort } = get();
    const res = await fetch(`http://127.0.0.1:${backendPort}/auth/github/device-poll`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_code }),
    });
    const data = await res.json();
    if (data.status === "ok") {
      get().setAuth(data.access_token, data.user);
    }
    return data;
  },

  disconnectGithub: async () => {
    const { backendPort, authToken } = get();
    try {
      await fetch(`http://127.0.0.1:${backendPort}/auth/github/disconnect`, {
        method: "POST",
        headers: { Authorization: `Bearer ${authToken}` },
      });
    } catch (_) {}
    set((s) => ({
      currentUser: s.currentUser ? { ...s.currentUser, github_id: null, github_login: null } : null,
      githubToken: "",
    }));
  },
});
