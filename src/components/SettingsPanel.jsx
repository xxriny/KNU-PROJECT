/**
 * SettingsPanel — 설정 패널 (분리된 독립 컴포넌트)
 */
import React, { useState, useEffect, useRef } from "react";
import useAppStore from "../store/useAppStore";
import { Key, Cpu, Users, Sun, Moon, Github, Check, X, Loader2, Shield, ChevronDown } from "lucide-react";

export default function SettingsPanel() {
  const {
    apiKey, setApiKey,
    model, setModel,
    availableModels,
    backendHasKey,
    isDarkMode, toggleDarkMode,
    backendPort,
    startGithubDeviceFlow,
    pollGithubDeviceFlow,
    disconnectGithub,
    setGithubSettings,
    githubToken,
    githubOwner,
    githubRepo,
  } = useAppStore();
  const authToken = useAppStore((s) => s.authToken);
  const currentUser = useAppStore((s) => s.currentUser);
  const isGithubConnected = !!currentUser?.github_id;

  const [teamName, setTeamNameLocal] = useState("");
  const [teamLoading, setTeamLoading] = useState(false);
  const [teamStatus, setTeamStatus] = useState(null); // null | "ok" | "error"
  const [oauthConfig, setOauthConfig] = useState({ client_id: "", client_secret: "", github_repo: "" });

  // 팀원 관리 state
  const [members, setMembers] = useState([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [roleUpdating, setRoleUpdating] = useState(null); // user_id being updated
  const [showMembers, setShowMembers] = useState(false);

  const fetchMembers = async () => {
    if (!authToken) return;
    setMembersLoading(true);
    try {
      const res = await fetch(`http://127.0.0.1:${backendPort}/api/teams/me/members`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      const data = await res.json();
      setMembers(data.members || []);
    } catch (_) {}
    finally { setMembersLoading(false); }
  };

  const updateRole = async (userId, newRole) => {
    setRoleUpdating(userId);
    try {
      await fetch(`http://127.0.0.1:${backendPort}/api/users/${userId}/role`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${authToken}` },
        body: JSON.stringify({ role: newRole }),
      });
      setMembers((prev) => prev.map((m) => m.id === userId ? { ...m, role: newRole } : m));
    } catch (_) {}
    finally { setRoleUpdating(null); }
  };

  // 레포 피커 state
  const [repoList, setRepoList] = useState([]);
  const [repoLoading, setRepoLoading] = useState(false);
  const [repoSearch, setRepoSearch] = useState("");
  const [showRepoPicker, setShowRepoPicker] = useState(false);
  const [repoScopeError, setRepoScopeError] = useState(false);
  const [oauthLoading, setOauthLoading] = useState(false);
  const [oauthStatus, setOauthStatus] = useState(null);
  const [showAdvancedOauth, setShowAdvancedOauth] = useState(false);

  // 전역 스토어의 레포 설정이 변경되면 로컬 설정도 동기화 (다른 컴포넌트에서의 변경 반영)
  useEffect(() => {
    if (githubOwner && githubRepo) {
      const fullPath = `${githubOwner}/${githubRepo}`;
      if (oauthConfig.github_repo !== fullPath) {
        setOauthConfig(p => ({ ...p, github_repo: fullPath }));
      }
    }
  }, [githubOwner, githubRepo, oauthConfig.github_repo]);

  useEffect(() => {
    if (!backendPort || !authToken) return;
    fetch(`http://127.0.0.1:${backendPort}/api/teams/me`, {
      headers: { Authorization: `Bearer ${authToken}` },
    })
      .then((r) => r.json())
      .then((d) => {
        if (d.team?.name) setTeamNameLocal(d.team.name);
        setOauthConfig((p) => ({
          ...p,
          client_id: d.team?.github_client_id || "",
          github_repo: d.team?.github_repo || "",
        }));
        // ★ githubToken이 있을 때만 덮어씀 — 빈 토큰으로 localStorage가 망가지는 것 방지
        if (d.team?.github_repo && githubToken) {
          const parts = d.team.github_repo.split("/");
          if (parts.length === 2) {
             setGithubSettings(githubToken, parts[0], parts[1]);
          }
        }
      })
      .catch(() => {});
  }, [backendPort, authToken]); // githubToken은 의도적으로 dep에서 제외 (초기화 루프 방지)

  const saveTeamName = async () => {
    if (!teamName.trim()) return;
    setTeamLoading(true);
    setTeamStatus(null);
    try {
      const port = backendPort || 8000;
      const res = await fetch(`http://127.0.0.1:${port}/api/teams/me`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${authToken}` },
        body: JSON.stringify({ name: teamName.trim() }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      if (json.status === "ok") setTeamStatus("ok");
      else throw new Error(json.detail || "저장 실패");
    } catch (e) {
      setTeamStatus("error");
    } finally {
      setTeamLoading(false);
    }
  };

  const saveOauthConfig = async () => {
    setOauthLoading(true);
    setOauthStatus(null);
    try {
      const port = backendPort || 8000;
      const payload = { github_repo: oauthConfig.github_repo };
      if (oauthConfig.client_id) payload.client_id = oauthConfig.client_id;
      if (oauthConfig.client_secret) payload.client_secret = oauthConfig.client_secret;

      const res = await fetch(`http://127.0.0.1:${port}/api/teams/me/github`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${authToken}` },
        body: JSON.stringify(payload),
      });
      const json = await res.json();
      if (json.status === "ok") setOauthStatus("ok");
      else throw new Error(json.detail || "저장 실패");
    } catch (e) {
      setOauthStatus("error");
    } finally {
      setOauthLoading(false);
    }
  };

  // ── Auto Save Logic ──
  const teamSaveTimer = useRef(null);
  const oauthSaveTimer = useRef(null);
  const isFirstMount = useRef(true);

  useEffect(() => {
    if (isFirstMount.current) return;
    if (!teamName.trim()) return;
    clearTimeout(teamSaveTimer.current);
    teamSaveTimer.current = setTimeout(saveTeamName, 1000);
    return () => clearTimeout(teamSaveTimer.current);
  }, [teamName]);

  useEffect(() => {
    if (isFirstMount.current) {
      isFirstMount.current = false;
      return;
    }
    clearTimeout(oauthSaveTimer.current);
    oauthSaveTimer.current = setTimeout(saveOauthConfig, 1000);
    return () => clearTimeout(oauthSaveTimer.current);
  }, [oauthConfig.client_id, oauthConfig.client_secret]);

  const loadRepos = async () => {
    if (!isGithubConnected) return;
    setRepoLoading(true);
    setRepoScopeError(false);
    setShowRepoPicker(false);
    try {
      const res = await fetch(`http://127.0.0.1:${backendPort}/auth/github/repos`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      const data = await res.json();
      if (data.status === "ok") {
        setRepoList(data.repos);
        setShowRepoPicker(true);
      } else {
        setRepoScopeError(true);
      }
    } catch (_) {
      setRepoScopeError(true);
    } finally {
      setRepoLoading(false);
    }
  };

  const selectRepo = async (repo) => {
    setOauthConfig((p) => ({ ...p, github_repo: repo.full_name }));
    setGithubSettings(githubToken, repo.owner, repo.name);
    setShowRepoPicker(false);
    setRepoSearch("");
    
    // 선택 즉시 백엔드에 저장합니다.
    try {
      const port = backendPort || 8000;
      await fetch(`http://127.0.0.1:${port}/api/teams/me/github`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${authToken}` },
        body: JSON.stringify({ github_repo: repo.full_name }),
      });
    } catch (_) {}
  };

  const [deviceFlowData, setDeviceFlowData] = useState(null);
  const [ghPolling, setGhPolling] = useState(false);
  const [ghError, setGhError] = useState("");

  const pollTimerRef = useRef(null);
  const expireTimerRef = useRef(null);
  const pollIntervalRef = useRef(5000);

  useEffect(() => () => {
    clearInterval(pollTimerRef.current);
    clearTimeout(expireTimerRef.current);
  }, []);

  const GH_ERRORS = {
    access_denied: "인증이 취소되었습니다. GitHub에서 승인을 거부했습니다.",
    expired_token: "인증 코드가 만료되었습니다. 다시 시도하세요.",
    incorrect_client_credentials: "OAuth 클라이언트 설정이 잘못되었습니다.",
  };

  const stopPolling = (errMsg = null) => {
    clearInterval(pollTimerRef.current);
    clearTimeout(expireTimerRef.current);
    setDeviceFlowData(null);
    setGhPolling(false);
    if (errMsg) setGhError(errMsg);
  };

  const startGithubLogin = async () => {
    clearInterval(pollTimerRef.current);
    clearTimeout(expireTimerRef.current);
    setGhError("");
    try {
      const data = await startGithubDeviceFlow();
      setDeviceFlowData(data);
      window.open(data.verification_uri, "_blank");
      setGhPolling(true);
      pollIntervalRef.current = (data.interval || 5) * 1000;

      const doPoll = async () => {
        try {
          const result = await pollGithubDeviceFlow(data.device_code);
          if (result.status === "ok") {
            stopPolling();
          } else if (result.status === "error") {
            stopPolling(GH_ERRORS[result.error] || result.error || "인증 실패");
          } else if (result.error === "slow_down") {
            clearInterval(pollTimerRef.current);
            pollIntervalRef.current += 5000;
            pollTimerRef.current = setInterval(doPoll, pollIntervalRef.current);
          }
        } catch (_) {}
      };

      pollTimerRef.current = setInterval(doPoll, pollIntervalRef.current);

      expireTimerRef.current = setTimeout(() => {
        stopPolling("인증 코드가 만료되었습니다. 다시 시도하세요.");
      }, (data.expires_in || 900) * 1000);
    } catch (e) {
      setGhError(e.message);
    }
  };

  const cancelGithubLogin = () => stopPolling();

  return (
    <div className="p-5 space-y-5 max-w-md mx-auto mt-4 overflow-x-hidden">
      <h2 className="text-base font-semibold text-[var(--text-primary)] mb-1">설정</h2>

      {/* API Key */}
      <div className="glass-card rounded-xl p-4 space-y-2">
        <label className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] font-medium">
          <Key size={12} />
          Gemini API Key
          {backendHasKey && !apiKey && (
            <span className="ml-auto text-xs text-[var(--green)] font-semibold">.env 사용 중</span>
          )}
        </label>
        <input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder={backendHasKey ? ".env에서 자동 로드됨" : "API 키를 입력하세요..."}
          className={`w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:border-[var(--accent)] transition-colors ${
            isDarkMode
              ? "bg-black/20 border-[var(--border)] text-[var(--text-primary)]"
              : "bg-slate-100/50 border-slate-200 text-slate-900"
          } placeholder-[var(--text-muted)]`}
        />
        {backendHasKey && !apiKey && (
          <p className="text-[11px] text-[var(--text-muted)]">직접 입력 시 .env보다 우선 적용됩니다</p>
        )}
      </div>

      {/* Model */}
      <div className="glass-card rounded-xl p-4 space-y-2">
        <label className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] font-medium">
          <Cpu size={12} />
          모델 선택
        </label>
        <select
          value={model}
          onChange={(e) => setModel(e.target.value)}
          className={`w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:border-[var(--accent)] transition-colors ${
            isDarkMode
              ? "bg-black/20 border-[var(--border)] text-[var(--text-primary)]"
              : "bg-slate-100/50 border-slate-200 text-slate-900"
          }`}
        >
          {availableModels.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>

      {/* 팀 설정 */}
      <div className="glass-card rounded-xl p-4 space-y-2">
        <label className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] font-medium">
          <Users size={12} />
          팀 설정
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={teamName}
            onChange={(e) => { setTeamNameLocal(e.target.value); setTeamStatus(null); }}
            placeholder="팀 이름"
            className={`flex-1 px-3 py-2 text-sm border rounded-lg focus:outline-none focus:border-[var(--accent)] transition-colors ${
              isDarkMode
                ? "bg-black/20 border-[var(--border)] text-[var(--text-primary)]"
                : "bg-slate-100/50 border-slate-200 text-slate-900"
            } placeholder-[var(--text-muted)]`}
          />
          <div className="flex items-center px-2">
            {teamLoading ? (
              <Loader2 size={16} className="animate-spin text-blue-500" />
            ) : teamStatus === "ok" ? (
              <Check size={16} className="text-emerald-500" />
            ) : teamStatus === "error" ? (
              <X size={16} className="text-red-500" />
            ) : null}
          </div>
        </div>
        {teamStatus === "ok" && <p className="text-[11px] text-emerald-400 flex items-center gap-1"><Check size={11} /> 자동 저장됨</p>}
        {teamStatus === "error" && <p className="text-[11px] text-red-400 flex items-center gap-1"><X size={11} /> 저장 실패</p>}
      </div>

      {/* 팀원 권한 관리 */}
      <div className="glass-card rounded-xl p-4 space-y-2">
        <button
          onClick={() => { setShowMembers((v) => !v); if (!showMembers) fetchMembers(); }}
          className="w-full flex items-center gap-1.5 text-xs text-[var(--text-secondary)] font-medium"
        >
          <Shield size={12} />
          팀원 권한 관리
          <ChevronDown size={12} className={`ml-auto transition-transform ${showMembers ? "rotate-180" : ""}`} />
        </button>

        {showMembers && (
          <div className="space-y-1 pt-1">
            {membersLoading ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 size={14} className="animate-spin opacity-50" />
              </div>
            ) : members.length === 0 ? (
              <p className="text-xs opacity-40 text-center py-3">팀원이 없습니다.</p>
            ) : (
              members.map((m) => {
                const isMe = m.id === currentUser?.id;
                const canEdit = currentUser?.role === "pm" && !isMe;
                const ROLE_LABELS = { pm: "PM", engineer: "Engineer", viewer: "Viewer" };
                const ROLE_COLORS = {
                  pm: "text-purple-400",
                  engineer: "text-blue-400",
                  viewer: "text-slate-400",
                };
                return (
                  <div
                    key={m.id}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg ${
                      isDarkMode ? "bg-white/5" : "bg-slate-50"
                    }`}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium truncate">
                        {m.name}
                        {isMe && <span className="ml-1 text-[10px] opacity-40">(나)</span>}
                      </p>
                      {m.github_login && (
                        <p className="text-[10px] opacity-40 truncate">@{m.github_login}</p>
                      )}
                    </div>
                    {canEdit ? (
                      <div className="relative">
                        <select
                          value={m.role}
                          disabled={roleUpdating === m.id}
                          onChange={(e) => updateRole(m.id, e.target.value)}
                          className={`text-xs px-2 py-1 rounded border appearance-none cursor-pointer transition-colors ${
                            isDarkMode
                              ? "bg-black/30 border-[var(--border)] text-[var(--text-primary)]"
                              : "bg-white border-slate-200 text-slate-700"
                          } ${ROLE_COLORS[m.role]}`}
                        >
                          <option value="pm">PM</option>
                          <option value="engineer">Engineer</option>
                          <option value="viewer">Viewer</option>
                        </select>
                        {roleUpdating === m.id && (
                          <Loader2 size={10} className="animate-spin absolute right-1.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                        )}
                      </div>
                    ) : (
                      <span className={`text-[10px] font-semibold shrink-0 ${ROLE_COLORS[m.role]}`}>
                        {ROLE_LABELS[m.role]}
                      </span>
                    )}
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>

      {/* GitHub 로그인 */}
      <div className="glass-card rounded-xl p-4 space-y-3">
        <label className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] font-medium">
          <Github size={12} />
          GitHub 로그인
          {isGithubConnected && (
            <span className="ml-auto text-xs text-emerald-400 font-semibold flex items-center gap-1">
              <Check size={10} /> {currentUser?.github_login || "연결됨"}
            </span>
          )}
        </label>

        {isGithubConnected ? (
          <div className="space-y-2">
            <div className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm ${isDarkMode ? "bg-emerald-500/10 border border-emerald-500/20" : "bg-emerald-50 border border-emerald-200"}`}>
              <Github size={14} className="text-emerald-400 shrink-0" />
              <span className={`font-semibold ${isDarkMode ? "text-emerald-300" : "text-emerald-700"}`}>@{currentUser?.github_login}</span>
              <span className="text-xs opacity-60 ml-auto">으로 연결됨</span>
            </div>
            <button
              onClick={disconnectGithub}
              className={`w-full flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-semibold transition-all ${
                isDarkMode ? "bg-white/5 hover:bg-red-500/20 text-slate-400 hover:text-red-400" : "bg-slate-100 hover:bg-red-50 text-slate-500 hover:text-red-600"
              }`}
            >
              <X size={14} /> 연결 해제
            </button>
          </div>
        ) : deviceFlowData ? (
          <div className="space-y-3">
            <p className="text-xs opacity-70">GitHub에서 아래 코드를 입력하세요:</p>
            <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${isDarkMode ? "bg-white/5 border-white/10" : "bg-slate-50 border-slate-200"}`}>
              <span className="text-2xl font-black tracking-widest text-blue-400 flex-1 text-center">
                {deviceFlowData.user_code}
              </span>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => window.open(deviceFlowData.verification_uri, "_blank")}
                className="flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-semibold bg-blue-600 hover:bg-blue-500 text-white transition-all"
              >
                <Github size={14} /> GitHub에서 인증
              </button>
              <button
                onClick={cancelGithubLogin}
                className={`px-4 py-2 rounded-lg text-sm transition-all ${isDarkMode ? "bg-white/5 hover:bg-white/10 text-slate-400" : "bg-slate-100 hover:bg-slate-200 text-slate-600"}`}
              >
                취소
              </button>
            </div>
            {ghPolling && (
              <div className="flex items-center gap-2 text-xs opacity-60">
                <Loader2 size={12} className="animate-spin" /> 인증 대기 중...
              </div>
            )}
          </div>
        ) : (
          <button
            onClick={startGithubLogin}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold bg-slate-800 hover:bg-slate-700 text-white dark:bg-white/10 dark:hover:bg-white/20 transition-all"
          >
            <Github size={14} /> GitHub로 연결하기
          </button>
        )}

        {ghError && (
          <p className="text-xs text-red-400 flex items-center gap-1">
            <X size={12} /> {ghError}
          </p>
        )}
        <p className="text-[11px] text-[var(--text-muted)]">
          GitHub 연결 시 LLM 분석 기능이 활성화되며 Issues 퍼블리시에 사용됩니다.
        </p>
      </div>

      {/* GitHub 대상 저장소 및 OAuth App 설정 (관리자용) */}
      <div className="glass-card rounded-xl p-4 space-y-3">
        <label className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] font-medium">
          <Key size={12} />
          GitHub 워크스페이스 설정
        </label>
        
        <div className="space-y-3">
          {/* 레포지토리 설정 */}
          <div className="space-y-1">
            <label className="text-[10px] text-[var(--text-muted)] font-semibold uppercase tracking-wider ml-1">대상 레포지토리</label>
            <div className="flex gap-2">
              <div className={`flex-1 px-3 py-2 text-sm border rounded-lg truncate ${
                isDarkMode ? "bg-black/20 border-[var(--border)] text-[var(--text-primary)]" : "bg-slate-50 border-slate-200 text-slate-900"
              }`}>
                {oauthConfig.github_repo
                  ? oauthConfig.github_repo
                  : <span className="opacity-40">{isGithubConnected ? "레포를 선택하세요" : "GitHub 로그인 후 선택 가능"}</span>
                }
              </div>
              {isGithubConnected && (
                <button
                  onClick={loadRepos}
                  disabled={repoLoading}
                  className={`px-3 py-2 text-xs font-semibold rounded-lg transition-all shrink-0 ${
                    isDarkMode
                      ? "bg-white/10 hover:bg-white/20 text-slate-300 disabled:opacity-40"
                      : "bg-slate-200 hover:bg-slate-300 text-slate-700 disabled:opacity-40"
                  }`}
                >
                  {repoLoading ? <Loader2 size={13} className="animate-spin" /> : "선택"}
                </button>
              )}
            </div>

            {repoScopeError && (
              <p className="text-[11px] text-amber-400 flex items-center gap-1 mt-1">
                <X size={11} /> GitHub 재연결이 필요합니다. 연결 해제 후 다시 연결하세요.
              </p>
            )}

            {showRepoPicker && repoList.length > 0 && (
              <div className={`mt-1 border rounded-xl overflow-hidden ${
                isDarkMode ? "bg-[#1a1f2e] border-[var(--border)]" : "bg-white border-slate-200"
              }`}>
                <div className={`px-3 py-2 border-b ${isDarkMode ? "border-[var(--border)]" : "border-slate-100"}`}>
                  <input
                    autoFocus
                    value={repoSearch}
                    onChange={(e) => setRepoSearch(e.target.value)}
                    placeholder="레포 검색..."
                    className={`w-full text-xs bg-transparent outline-none ${
                      isDarkMode ? "text-[var(--text-primary)] placeholder-[var(--text-muted)]" : "text-slate-800 placeholder-slate-400"
                    }`}
                  />
                </div>
                <ul className="max-h-52 overflow-y-auto">
                  {repoList
                    .filter((r) => r.full_name.toLowerCase().includes(repoSearch.toLowerCase()))
                    .map((repo) => (
                      <li
                        key={repo.full_name}
                        onClick={() => selectRepo(repo)}
                        className={`flex items-center gap-2 px-3 py-2.5 cursor-pointer text-sm transition-colors ${
                          isDarkMode ? "hover:bg-white/5 text-[var(--text-primary)]" : "hover:bg-slate-50 text-slate-800"
                        } ${oauthConfig.github_repo === repo.full_name ? (isDarkMode ? "bg-blue-500/10" : "bg-blue-50") : ""}`}
                      >
                        <span className="font-medium truncate">{repo.name}</span>
                        <span className="text-xs opacity-50 shrink-0">{repo.owner}</span>
                        <span className="ml-auto flex items-center gap-1.5 shrink-0">
                          {repo.language && <span className="text-[10px] opacity-40">{repo.language}</span>}
                          {repo.private && <span className="text-[10px] text-amber-400 font-semibold">private</span>}
                        </span>
                      </li>
                    ))}
                  {repoList.filter((r) => r.full_name.toLowerCase().includes(repoSearch.toLowerCase())).length === 0 && (
                    <li className="px-3 py-3 text-xs opacity-40 text-center">검색 결과 없음</li>
                  )}
                </ul>
                <div className={`px-3 py-1.5 border-t text-right ${isDarkMode ? "border-[var(--border)]" : "border-slate-100"}`}>
                  <button onClick={() => setShowRepoPicker(false)} className="text-[10px] opacity-40 hover:opacity-70 transition-opacity">닫기</button>
                </div>
              </div>
            )}
          </div>

          <button
            onClick={() => setShowAdvancedOauth(!showAdvancedOauth)}
            className="text-[11px] text-blue-400 hover:text-blue-300 transition-colors w-full text-left"
          >
            {showAdvancedOauth ? "- OAuth App 설정 닫기" : "+ 고급: OAuth App Client ID 재설정"}
          </button>

          {showAdvancedOauth && (
            <div className="space-y-2 p-3 rounded-lg bg-black/10 border border-white/5">
              <input
                type="text"
                value={oauthConfig.client_id}
                onChange={(e) => setOauthConfig(p => ({ ...p, client_id: e.target.value }))}
                placeholder="Client ID"
                className={`w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:border-[var(--accent)] transition-colors ${
                  isDarkMode ? "bg-black/20 border-[var(--border)] text-[var(--text-primary)]" : "bg-slate-50 border-slate-200 text-slate-900"
                }`}
              />
              <input
                type="password"
                value={oauthConfig.client_secret}
                onChange={(e) => setOauthConfig(p => ({ ...p, client_secret: e.target.value }))}
                placeholder="새 Client Secret (비워두면 유지)"
                className={`w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:border-[var(--accent)] transition-colors ${
                  isDarkMode ? "bg-black/20 border-[var(--border)] text-[var(--text-primary)]" : "bg-slate-50 border-slate-200 text-slate-900"
                }`}
              />
            </div>
          )}

          <div className="flex items-center justify-between py-1">
            <div className="text-[11px] text-[var(--text-muted)]">
              {oauthLoading ? (
                <span className="flex items-center gap-1"><Loader2 size={10} className="animate-spin" /> 저장 중...</span>
              ) : oauthStatus === "ok" ? (
                <span className="flex items-center gap-1 text-emerald-400"><Check size={10} /> 모든 설정 자동 저장됨</span>
              ) : oauthStatus === "error" ? (
                <span className="flex items-center gap-1 text-red-400"><X size={10} /> 저장 실패</span>
              ) : (
                <span>변경 시 자동 저장됩니다</span>
              )}
            </div>
          </div>
          
          <p className="text-[10px] text-[var(--text-muted)] leading-relaxed">
            * 이 설정은 팀 전체에 적용되며, GitHub 연동 및 LLM Issues 분석/퍼블리시에 사용됩니다.
          </p>
        </div>
      </div>

      {/* 테마 */}
      <div className="glass-card rounded-xl p-4">
        <button
          onClick={toggleDarkMode}
          className="w-full flex items-center gap-2.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        >
          {isDarkMode ? <Sun size={14} className="text-yellow-400" /> : <Moon size={14} className="text-blue-400" />}
          <span>{isDarkMode ? "라이트 모드로 전환" : "다크 모드로 전환"}</span>
        </button>
      </div>
    </div>
  );
}
