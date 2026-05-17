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
    setGithubBranch,
    githubToken,
    githubOwner,
    githubRepo,
    githubBranch,
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

  // 브랜치 피커 state
  const [branchList, setBranchList] = useState([]);
  const [branchLoading, setBranchLoading] = useState(false);
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
      // 브랜치 목록 자동 로드 (authToken 준비 후)
      if (authToken && branchList.length === 0) {
        loadBranches(githubOwner, githubRepo);
      }
    }
  }, [githubOwner, githubRepo, authToken]); // eslint-disable-line react-hooks/exhaustive-deps

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

  const loadBranches = async (owner, repo) => {
    if (!owner || !repo || !authToken) return;
    setBranchLoading(true);
    try {
      const res = await fetch(`http://127.0.0.1:${backendPort}/api/github/branches`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${authToken}` },
        body: JSON.stringify({ owner, repo }),
      });
      const data = await res.json();
      if (data.status === "ok") setBranchList(data.data || []);
    } catch (_) {}
    finally { setBranchLoading(false); }
  };

  const selectRepo = async (repo) => {
    setOauthConfig((p) => ({ ...p, github_repo: repo.full_name }));
    setGithubSettings(githubToken, repo.owner, repo.name, "main");
    setShowRepoPicker(false);
    setRepoSearch("");
    loadBranches(repo.owner, repo.name);

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

  const inputCls = `w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:border-[var(--accent)] transition-colors placeholder-[var(--text-muted)] ${
    isDarkMode ? "bg-black/20 border-[var(--border)] text-[var(--text-primary)]" : "bg-slate-50 border-slate-200 text-slate-900"
  }`;
  const sectionCls = `glass-card rounded-2xl overflow-hidden`;
  const SectionHeader = ({ icon: Icon, title, badge }) => (
    <div className={`flex items-center gap-2.5 px-5 py-3.5 border-b ${isDarkMode ? "border-white/5 bg-white/[0.02]" : "border-slate-100 bg-slate-50/60"}`}>
      <Icon size={14} className="opacity-50 shrink-0" />
      <span className="text-xs font-bold uppercase tracking-wide opacity-60">{title}</span>
      {badge}
    </div>
  );

  const ROLE_META = {
    pm:       { label: "PM",        cls: "bg-purple-500/15 text-purple-400 border-purple-500/20" },
    engineer: { label: "Engineer",  cls: "bg-blue-500/15 text-blue-400 border-blue-500/20" },
    backend:  { label: "백엔드",    cls: "bg-emerald-500/15 text-emerald-400 border-emerald-500/20" },
    frontend: { label: "프론트엔드",cls: "bg-amber-500/15 text-amber-400 border-amber-500/20" },
    devops:   { label: "DevOps",    cls: "bg-rose-500/15 text-rose-400 border-rose-500/20" },
    viewer:   { label: "Viewer",    cls: "bg-slate-500/15 text-slate-400 border-slate-500/20" },
  };
  const RoleBadge = ({ role }) => {
    const meta = ROLE_META[role] || { label: role, cls: "bg-slate-500/15 text-slate-400 border-slate-500/20" };
    return (
      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${meta.cls}`}>{meta.label}</span>
    );
  };

  return (
    <div className="flex flex-col h-full overflow-y-auto custom-scrollbar">
      {/* Page header */}
      <div className={`px-6 py-5 border-b shrink-0 ${isDarkMode ? "border-white/5" : "border-slate-200"}`}>
        <h1 className={`text-lg font-black tracking-tight ${isDarkMode ? "text-white" : "text-slate-900"}`}>설정</h1>
        <p className="text-xs opacity-40 mt-0.5">워크스페이스 및 팀 설정을 관리합니다</p>
      </div>

      <div className="p-5 space-y-4 max-w-md mx-auto w-full">

        {/* AI 설정 */}
        <div className={sectionCls}>
          <SectionHeader icon={Cpu} title="AI 설정" />
          <div className="p-4 space-y-3">
            <div className="space-y-1.5">
              <label className="flex items-center justify-between text-xs font-semibold opacity-60">
                <span className="flex items-center gap-1.5"><Key size={11} /> Gemini API Key</span>
                {backendHasKey && !apiKey && <span className="text-emerald-400 font-bold">.env 사용 중</span>}
              </label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={backendHasKey ? ".env에서 자동 로드됨" : "sk-..."}
                className={inputCls}
              />
              {backendHasKey && !apiKey && (
                <p className="text-[10px] opacity-40">직접 입력 시 .env보다 우선 적용됩니다</p>
              )}
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-semibold opacity-60">모델 선택</label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className={inputCls}
              >
                {availableModels.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* 팀 설정 */}
        <div className={sectionCls}>
          <SectionHeader icon={Users} title="팀 설정" />
          <div className="p-4 space-y-3">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold opacity-60">팀 이름</label>
              <div className="flex gap-2 items-center">
                <input
                  type="text"
                  value={teamName}
                  onChange={(e) => { setTeamNameLocal(e.target.value); setTeamStatus(null); }}
                  placeholder="팀 이름을 입력하세요"
                  className={`${inputCls} flex-1`}
                />
                <div className="w-6 flex items-center justify-center shrink-0">
                  {teamLoading ? (
                    <Loader2 size={14} className="animate-spin text-blue-400" />
                  ) : teamStatus === "ok" ? (
                    <Check size={14} className="text-emerald-400" />
                  ) : teamStatus === "error" ? (
                    <X size={14} className="text-red-400" />
                  ) : null}
                </div>
              </div>
            </div>
          </div>

          {/* 팀원 관리 */}
          <div className={`border-t ${isDarkMode ? "border-white/5" : "border-slate-100"}`}>
            <button
              onClick={() => { setShowMembers((v) => !v); if (!showMembers) fetchMembers(); }}
              className={`w-full flex items-center gap-2.5 px-4 py-3 text-xs font-semibold transition-colors ${
                isDarkMode ? "hover:bg-white/5" : "hover:bg-slate-50"
              }`}
            >
              <Shield size={13} className="opacity-50" />
              <span className="opacity-70">팀원 권한 관리</span>
              <ChevronDown size={12} className={`ml-auto opacity-40 transition-transform duration-200 ${showMembers ? "rotate-180" : ""}`} />
            </button>

            {showMembers && (
              <div className={`px-4 pb-3 space-y-1.5 border-t ${isDarkMode ? "border-white/5" : "border-slate-100"}`}>
                <div className="pt-2">
                  {membersLoading ? (
                    <div className="flex items-center justify-center py-5">
                      <Loader2 size={16} className="animate-spin opacity-30" />
                    </div>
                  ) : members.length === 0 ? (
                    <p className="text-xs opacity-30 text-center py-4">팀원이 없습니다.</p>
                  ) : (
                    members.map((m) => {
                      const isMe = m.id === currentUser?.id;
                      const canEdit = currentUser?.role === "pm" && !isMe;
                      return (
                        <div
                          key={m.id}
                          className={`flex items-center gap-3 px-3 py-2.5 rounded-xl ${
                            isDarkMode ? "bg-white/[0.03] hover:bg-white/[0.06]" : "bg-slate-50 hover:bg-slate-100/80"
                          } transition-colors`}
                        >
                          <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-black shrink-0 ${
                            isDarkMode ? "bg-white/10 text-white/60" : "bg-slate-200 text-slate-600"
                          }`}>
                            {m.name?.[0]?.toUpperCase() || "?"}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className={`text-xs font-semibold truncate ${isDarkMode ? "text-slate-200" : "text-slate-800"}`}>
                              {m.name}
                              {isMe && <span className="ml-1.5 text-[10px] opacity-40 font-normal">나</span>}
                            </p>
                            {m.github_login && (
                              <p className="text-[10px] opacity-40 truncate">@{m.github_login}</p>
                            )}
                          </div>
                          {canEdit ? (
                            <div className="relative shrink-0">
                              <select
                                value={m.role}
                                disabled={roleUpdating === m.id}
                                onChange={(e) => updateRole(m.id, e.target.value)}
                                style={{ colorScheme: isDarkMode ? "dark" : "light" }}
                                className={`text-[10px] font-bold px-2.5 py-1 rounded-full border appearance-none cursor-pointer transition-colors outline-none ${
                                  ROLE_META[m.role]?.cls || "bg-slate-500/15 text-slate-400 border-slate-500/20"
                                } ${isDarkMode ? "bg-black/20" : ""}`}
                              >
                                <option value="pm">PM</option>
                                <option value="engineer">Engineer</option>
                                <option value="backend">백엔드</option>
                                <option value="frontend">프론트엔드</option>
                                <option value="devops">DevOps</option>
                                <option value="viewer">Viewer</option>
                              </select>
                              {roleUpdating === m.id && (
                                <Loader2 size={10} className="animate-spin absolute right-1.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                              )}
                            </div>
                          ) : (
                            <RoleBadge role={m.role} />
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* GitHub */}
        <div className={sectionCls}>
          <SectionHeader
            icon={Github}
            title="GitHub 연동"
            badge={isGithubConnected && (
              <span className="ml-auto flex items-center gap-1 text-[10px] font-bold text-emerald-400">
                <Check size={9} /> 연결됨
              </span>
            )}
          />

          <div className="p-4 space-y-4">
            {/* 연결 상태 */}
            {isGithubConnected ? (
              <div className={`flex items-center gap-3 p-3 rounded-xl ${
                isDarkMode ? "bg-emerald-500/10 border border-emerald-500/20" : "bg-emerald-50 border border-emerald-200"
              }`}>
                <Github size={16} className="text-emerald-400 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-bold truncate ${isDarkMode ? "text-emerald-300" : "text-emerald-700"}`}>
                    @{currentUser?.github_login}
                  </p>
                  <p className="text-[10px] opacity-50">GitHub 계정으로 연결됨</p>
                </div>
                <button
                  onClick={disconnectGithub}
                  className={`shrink-0 text-xs px-3 py-1.5 rounded-lg font-semibold transition-all ${
                    isDarkMode ? "bg-white/10 hover:bg-red-500/20 text-slate-400 hover:text-red-400" : "bg-white hover:bg-red-50 text-slate-500 hover:text-red-600 border border-slate-200"
                  }`}
                >
                  해제
                </button>
              </div>
            ) : deviceFlowData ? (
              <div className={`space-y-3 p-3 rounded-xl border ${isDarkMode ? "bg-white/5 border-white/10" : "bg-slate-50 border-slate-200"}`}>
                <p className="text-xs opacity-60 text-center">GitHub에서 아래 코드를 입력하세요</p>
                <div className="text-2xl font-black tracking-widest text-blue-400 text-center py-2">
                  {deviceFlowData.user_code}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => window.open(deviceFlowData.verification_uri, "_blank")}
                    className="flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-bold bg-blue-600 hover:bg-blue-500 text-white transition-all"
                  >
                    <Github size={12} /> GitHub에서 인증
                  </button>
                  <button
                    onClick={cancelGithubLogin}
                    className={`px-3 py-2 rounded-lg text-xs transition-all ${isDarkMode ? "bg-white/5 hover:bg-white/10 text-slate-400" : "bg-white hover:bg-slate-100 text-slate-600 border border-slate-200"}`}
                  >
                    취소
                  </button>
                </div>
                {ghPolling && (
                  <div className="flex items-center justify-center gap-2 text-xs opacity-40">
                    <Loader2 size={11} className="animate-spin" /> 인증 대기 중...
                  </div>
                )}
              </div>
            ) : (
              <button
                onClick={startGithubLogin}
                className={`w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-bold transition-all ${
                  isDarkMode
                    ? "bg-white/10 hover:bg-white/15 text-white border border-white/10"
                    : "bg-slate-900 hover:bg-slate-800 text-white"
                }`}
              >
                <Github size={15} /> GitHub로 연결하기
              </button>
            )}

            {ghError && (
              <p className="text-xs text-red-400 flex items-center gap-1.5 px-1">
                <X size={11} /> {ghError}
              </p>
            )}

            {/* 레포지토리 & 브랜치 */}
            {isGithubConnected && (
              <div className={`space-y-3 pt-1 border-t ${isDarkMode ? "border-white/5" : "border-slate-100"}`}>
                <p className="text-[10px] font-bold uppercase tracking-wider opacity-40 pt-1">워크스페이스</p>

                <div className="space-y-1.5">
                  <label className="text-xs opacity-60 font-semibold">대상 레포지토리</label>
                  <div className="flex gap-2">
                    <div className={`flex-1 px-3 py-2 text-sm border rounded-lg truncate font-medium ${
                      isDarkMode ? "bg-black/20 border-[var(--border)] text-[var(--text-primary)]" : "bg-slate-50 border-slate-200 text-slate-900"
                    } ${!oauthConfig.github_repo ? "opacity-40" : ""}`}>
                      {oauthConfig.github_repo || "레포를 선택하세요"}
                    </div>
                    <button
                      onClick={loadRepos}
                      disabled={repoLoading}
                      className={`px-3 py-2 text-xs font-bold rounded-lg transition-all shrink-0 ${
                        isDarkMode ? "bg-white/10 hover:bg-white/20 text-slate-300 disabled:opacity-30" : "bg-slate-200 hover:bg-slate-300 text-slate-700 disabled:opacity-30"
                      }`}
                    >
                      {repoLoading ? <Loader2 size={13} className="animate-spin" /> : "선택"}
                    </button>
                  </div>

                  {repoScopeError && (
                    <p className="text-[10px] text-amber-400 flex items-center gap-1">
                      <X size={10} /> 재연결이 필요합니다 (연결 해제 후 다시 연결)
                    </p>
                  )}

                  {showRepoPicker && repoList.length > 0 && (
                    <div className={`border rounded-xl overflow-hidden shadow-xl ${
                      isDarkMode ? "bg-[#1a1f2e] border-[var(--border)]" : "bg-white border-slate-200"
                    }`}>
                      <div className={`px-3 py-2 border-b ${isDarkMode ? "border-[var(--border)]" : "border-slate-100"}`}>
                        <input
                          autoFocus
                          value={repoSearch}
                          onChange={(e) => setRepoSearch(e.target.value)}
                          placeholder="레포 검색..."
                          className="w-full text-xs bg-transparent outline-none"
                        />
                      </div>
                      <ul className="max-h-48 overflow-y-auto">
                        {repoList
                          .filter((r) => r.full_name.toLowerCase().includes(repoSearch.toLowerCase()))
                          .map((repo) => (
                            <li
                              key={repo.full_name}
                              onClick={() => selectRepo(repo)}
                              className={`flex items-center gap-2 px-3 py-2 cursor-pointer text-sm transition-colors ${
                                isDarkMode ? "hover:bg-white/5 text-[var(--text-primary)]" : "hover:bg-slate-50 text-slate-800"
                              } ${oauthConfig.github_repo === repo.full_name ? (isDarkMode ? "bg-blue-500/10" : "bg-blue-50") : ""}`}
                            >
                              <span className="font-semibold truncate text-xs">{repo.name}</span>
                              <span className="text-[10px] opacity-40 shrink-0">{repo.owner}</span>
                              <span className="ml-auto flex items-center gap-1.5 shrink-0">
                                {repo.language && <span className="text-[10px] opacity-30">{repo.language}</span>}
                                {repo.private && <span className="text-[10px] text-amber-400 font-bold">private</span>}
                              </span>
                            </li>
                          ))}
                        {repoList.filter((r) => r.full_name.toLowerCase().includes(repoSearch.toLowerCase())).length === 0 && (
                          <li className="px-3 py-3 text-xs opacity-30 text-center">검색 결과 없음</li>
                        )}
                      </ul>
                      <div className={`px-3 py-1.5 border-t text-right ${isDarkMode ? "border-[var(--border)]" : "border-slate-100"}`}>
                        <button onClick={() => setShowRepoPicker(false)} className="text-[10px] opacity-30 hover:opacity-60 transition-opacity">닫기</button>
                      </div>
                    </div>
                  )}
                </div>

                {githubOwner && githubRepo && (
                  <div className="space-y-1.5">
                    <label className="text-xs opacity-60 font-semibold">기본 브랜치</label>
                    <div className="flex gap-2">
                      <select
                        value={githubBranch}
                        onChange={(e) => setGithubBranch(e.target.value)}
                        className={`${inputCls} flex-1 cursor-pointer`}
                        style={{ colorScheme: isDarkMode ? "dark" : "light" }}
                      >
                        {branchList.length === 0 && (
                          <option value={githubBranch} className={isDarkMode ? "bg-[#1a1a2e] text-white" : "bg-white text-slate-900"}>
                            {githubBranch}
                          </option>
                        )}
                        {branchList.map((b) => (
                          <option 
                            key={b.name} 
                            value={b.name} 
                            className={isDarkMode ? "bg-[#1a1a2e] text-white" : "bg-white text-slate-900"}
                          >
                            {b.name}{b.protected ? " 🔒" : ""}
                          </option>
                        ))}
                      </select>
                      <button
                        onClick={() => loadBranches(githubOwner, githubRepo)}
                        disabled={branchLoading}
                        className={`px-3 py-2 text-xs font-bold rounded-lg transition-all shrink-0 ${
                          isDarkMode ? "bg-white/10 hover:bg-white/20 text-slate-300 disabled:opacity-30" : "bg-slate-200 hover:bg-slate-300 text-slate-700 disabled:opacity-30"
                        }`}
                      >
                        {branchLoading ? <Loader2 size={13} className="animate-spin" /> : "↻"}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* 고급 OAuth 설정 */}
            <div>
              <button
                onClick={() => setShowAdvancedOauth(!showAdvancedOauth)}
                className={`text-[11px] font-semibold transition-colors flex items-center gap-1 ${
                  showAdvancedOauth ? "text-blue-400" : "opacity-40 hover:opacity-70"
                }`}
              >
                <ChevronDown size={11} className={`transition-transform ${showAdvancedOauth ? "rotate-180" : ""}`} />
                {showAdvancedOauth ? "OAuth App 설정 닫기" : "고급: OAuth App 설정"}
              </button>

              {showAdvancedOauth && (
                <div className={`mt-2 space-y-2 p-3 rounded-xl border ${
                  isDarkMode ? "bg-black/20 border-white/5" : "bg-slate-50 border-slate-200"
                }`}>
                  <input
                    type="text"
                    value={oauthConfig.client_id}
                    onChange={(e) => setOauthConfig(p => ({ ...p, client_id: e.target.value }))}
                    placeholder="Client ID"
                    className={inputCls}
                  />
                  <input
                    type="password"
                    value={oauthConfig.client_secret}
                    onChange={(e) => setOauthConfig(p => ({ ...p, client_secret: e.target.value }))}
                    placeholder="새 Client Secret (비워두면 유지)"
                    className={inputCls}
                  />
                </div>
              )}
            </div>

            {/* 저장 상태 */}
            <div className="text-[10px] opacity-50 flex items-center gap-1">
              {oauthLoading ? (
                <><Loader2 size={9} className="animate-spin" /> 저장 중...</>
              ) : oauthStatus === "ok" ? (
                <span className="text-emerald-400 opacity-100"><Check size={9} className="inline mr-1" />자동 저장됨</span>
              ) : oauthStatus === "error" ? (
                <span className="text-red-400 opacity-100"><X size={9} className="inline mr-1" />저장 실패</span>
              ) : "변경 시 자동 저장"}
            </div>
          </div>
        </div>

        {/* 기타 */}
        <div className={sectionCls}>
          <button
            onClick={toggleDarkMode}
            className={`w-full flex items-center gap-3 px-5 py-3.5 text-sm transition-colors ${
              isDarkMode ? "hover:bg-white/5" : "hover:bg-slate-50"
            }`}
          >
            {isDarkMode
              ? <Sun size={14} className="text-yellow-400 shrink-0" />
              : <Moon size={14} className="text-blue-400 shrink-0" />
            }
            <span className="opacity-70 text-xs font-semibold">
              {isDarkMode ? "라이트 모드로 전환" : "다크 모드로 전환"}
            </span>
          </button>
        </div>

      </div>
    </div>
  );
}
