/**
 * authSlice — 인증 상태 관리
 * 로그인/로그아웃, 현재 사용자, 역할/플랜 정보
 */

import { EMPTY_RESULT_FIELDS } from "../storeHelpers";

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
  userPlan: stored.user?.plan ?? "free",
  authChecked: false,
  hasUsers: null,
  myTeams: [],           // 다중 팀 목록
  teamWorkspaces: {},    // { [teamId]: parked workspace snapshot }
  analysisOwnerTeamId: null, // 현재 실행 중인 분석을 시작한 팀

  // ── 액션 ────────────────────────────────────────────────
  setAuth: (token, user) => {
    saveAuth(token, user);
    set({
      authToken: token,
      currentUser: user,
      userRole: user?.role ?? null,
      userPlan: user?.plan ?? "free",
    });
  },

  clearAuth: () => {
    clearStoredAuth();
    set({ authToken: null, currentUser: null, userRole: null, userPlan: "free" });
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
    const { backendPort, authToken } = get();
    if (!backendPort) return;
    try {
      // /auth/status와 /auth/me를 동시에 요청 (토큰이 있을 때)
      const [statusRes, meRes] = await Promise.all([
        fetch(`http://127.0.0.1:${backendPort}/auth/status`),
        authToken
          ? fetch(`http://127.0.0.1:${backendPort}/auth/me`, { headers: get().getAuthHeader() })
          : Promise.resolve(null),
      ]);

      const statusData = await statusRes.json();
      set({ hasUsers: statusData.has_users, authChecked: true });

      if (meRes) {
        if (!meRes.ok) {
          get().clearAuth();
        } else {
          const meData = await meRes.json();
          get().setAuth(get().authToken, meData);
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

  /** 팀 생성 (로그인 후 팀이 없는 사용자) */
  createTeam: async (teamName) => {
    const { backendPort } = get();
    const res = await fetch(`http://127.0.0.1:${backendPort}/api/teams`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...get().getAuthHeader() },
      body: JSON.stringify({ name: teamName }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "팀 생성 실패");
    }
    const data = await res.json();
    if (data.user) {
      get().setAuth(get().authToken, data.user);
    }
    get().loadMyTeams();
    return data;
  },

  /** 내 팀 목록 불러오기 */
  loadMyTeams: async () => {
    const { backendPort, isAuthenticated, getAuthHeader } = get();
    if (!backendPort || !isAuthenticated()) return;
    try {
      const res = await fetch(`http://127.0.0.1:${backendPort}/api/users/me/teams`, {
        headers: getAuthHeader(),
      });
      if (res.ok) {
        const data = await res.json();
        set({ myTeams: data.teams || [] });
      }
    } catch (e) {
      console.error("Failed to load my teams", e);
    }
  },

  // 파킹/복원 대상 필드 목록
  _workspaceFields: [
    "pipelineStatus", "pipelineError", "pipelineNodes", "thinkingLog",
    "agileVerifyResult", "agileImpactResult",
    "currentSessionId", "userComments", "chatHistory", "chatInput",
    "activeViewportTab", "activeIconPanel",
    "snapshots", "activeSnapshot", "localResults", "publishError",
    ...Object.keys(EMPTY_RESULT_FIELDS),
  ],

  /** 현재 팀 워크스페이스 상태를 teamWorkspaces에 파킹 */
  _parkCurrentWorkspace: () => {
    const s = get();
    const teamId = s.currentUser?.team_id;
    if (!teamId) return;
    const snapshot = {};
    for (const f of s._workspaceFields) snapshot[f] = s[f];
    // 팀 전용 세션 목록도 파킹
    snapshot._sessions = (s.sessions || []).filter(
      (sess) => !sess.team_id || sess.team_id === teamId
    );
    set((prev) => ({
      teamWorkspaces: { ...prev.teamWorkspaces, [teamId]: snapshot },
    }));
  },

  /** teamWorkspaces에서 팀 상태 복원, 없으면 빈 상태 */
  _restoreWorkspace: (teamId) => {
    const parked = get().teamWorkspaces[teamId];
    const BLANK_WORKSPACE = {
      pipelineStatus: "idle", pipelineError: null, pipelineNodes: {}, thinkingLog: [],
      agileVerifyResult: null, agileImpactResult: null,
      currentSessionId: null, userComments: [], chatHistory: [], chatInput: "",
      activeViewportTab: { kind: "output", id: "home" }, activeIconPanel: null,
      snapshots: [], activeSnapshot: null, localResults: [], publishError: null,
      ...EMPTY_RESULT_FIELDS,
    };
    const workspace = parked || BLANK_WORKSPACE;
    const { _sessions, ...rest } = workspace;
    set((s) => ({
      ...rest,
      sessions: _sessions || (s.sessions || []).filter(
        (sess) => !sess.team_id || sess.team_id === teamId
      ),
    }));
  },

  /** 팀 전환 (옵티미스틱: UI 즉시 전환 → API 백그라운드 확인 → 실패 시 롤백) */
  switchTeam: async (teamId) => {
    const { backendPort, getAuthHeader, currentUser } = get();
    if (currentUser?.team_id === teamId) return;

    // ── 1. 즉시 UI 전환 (API 기다리지 않음) ──────────────────
    get()._parkCurrentWorkspace();
    const prevUser = currentUser;

    // 현재 사용자 정보를 팀만 바꿔서 임시 적용
    const optimisticUser = { ...currentUser, team_id: teamId };
    get().setAuth(get().authToken, optimisticUser);
    get()._restoreWorkspace(teamId);

    const isFirstVisit = !get().teamWorkspaces[teamId];

    // 팀 목록 + 첫 방문 시 스냅샷·로컬결과를 모두 병렬로 fire-and-forget
    Promise.all([
      get().loadMyTeams(),
      ...(isFirstVisit ? [get().loadSnapshots(), get().loadLocalResults()] : []),
    ]);

    // ── 2. 백그라운드에서 서버 확인 ──────────────────────────
    try {
      const res = await fetch(`http://127.0.0.1:${backendPort}/api/users/me/teams/switch`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeader() },
        body: JSON.stringify({ team_id: teamId }),
      });
      if (!res.ok) throw new Error((await res.json()).detail || "팀 전환 실패");
      const data = await res.json();
      // 서버에서 받은 정확한 유저 정보로 교체 (role 등 반영)
      get().setAuth(get().authToken, data.user);
      return data.user;
    } catch (e) {
      // ── 3. 실패 시 롤백 ────────────────────────────────────
      get()._parkCurrentWorkspace();
      get().setAuth(get().authToken, prevUser);
      get()._restoreWorkspace(prevUser.team_id);
      get().addNotification(`팀 전환 실패: ${e.message}`, "error");
      throw e;
    }
  },

  /** GitHub OAuth Web Flow: 인증 URL + session_id 가져오기 */
  getGithubOAuthUrl: async () => {
    const { backendPort } = get();
    const res = await fetch(`http://127.0.0.1:${backendPort}/auth/github/oauth-url`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "GitHub OAuth URL 조회 실패");
    return { url: data.url, sessionId: data.session_id };
  },

  /** GitHub OAuth Web Flow: 폴링으로 결과 확인 */
  pollGithubOAuthResult: async (sessionId) => {
    const { backendPort } = get();
    const res = await fetch(`http://127.0.0.1:${backendPort}/auth/github/callback-poll/${sessionId}`);
    if (!res.ok) return { status: "error", error: "세션 만료" };
    const data = await res.json();
    if (data.status === "done") {
      get().setAuth(data.access_token, data.user);
      set({ hasUsers: true });
    }
    return data;
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
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      return { status: "error", error: errBody.detail || `서버 오류 (${res.status})` };
    }
    const data = await res.json();
    if (data.status === "ok") {
      get().setAuth(data.access_token, data.user);
      set({ hasUsers: true });
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
