/**
 * SettingsPanel — 설정 패널 (분리된 독립 컴포넌트)
 */
import React, { useState, useEffect, useRef } from "react";
import useAppStore from "../store/useAppStore";
import { Key, Cpu, Users, Sun, Moon, Github, Check, X, Loader2 } from "lucide-react";

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
  } = useAppStore();
  const authToken = useAppStore((s) => s.authToken);
  const currentUser = useAppStore((s) => s.currentUser);
  const isGithubConnected = !!currentUser?.github_id;

  const [teamName, setTeamNameLocal] = useState("");
  const [teamLoading, setTeamLoading] = useState(false);
  const [teamStatus, setTeamStatus] = useState(null); // null | "ok" | "error"
  const [oauthConfig, setOauthConfig] = useState({ client_id: "", client_secret: "" });
  const [oauthLoading, setOauthLoading] = useState(false);
  const [oauthStatus, setOauthStatus] = useState(null);

  useEffect(() => {
    if (!backendPort || !authToken) return;
    fetch(`http://127.0.0.1:${backendPort}/api/teams/me`, {
      headers: { Authorization: `Bearer ${authToken}` },
    })
      .then((r) => r.json())
      .then((d) => {
        if (d.team?.name) setTeamNameLocal(d.team.name);
        if (d.team?.github_client_id) {
          setOauthConfig((p) => ({ ...p, client_id: d.team.github_client_id }));
        }
      })
      .catch(() => {});
  }, [backendPort, authToken]);

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
    if (!oauthConfig.client_id || !oauthConfig.client_secret) return;
    setOauthLoading(true);
    setOauthStatus(null);
    try {
      const port = backendPort || 8000;
      const res = await fetch(`http://127.0.0.1:${port}/api/teams/me/github`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${authToken}` },
        body: JSON.stringify({
          client_id: oauthConfig.client_id,
          client_secret: oauthConfig.client_secret,
        }),
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
          <button
            onClick={saveTeamName}
            disabled={teamLoading || !teamName.trim()}
            className={`px-3 py-2 rounded-lg text-sm font-semibold transition-all ${
              teamLoading || !teamName.trim()
                ? "opacity-40 cursor-not-allowed bg-white/5"
                : "bg-blue-600 hover:bg-blue-500 text-white"
            }`}
          >
            {teamLoading ? <Loader2 size={14} className="animate-spin" /> : "저장"}
          </button>
        </div>
        {teamStatus === "ok" && <p className="text-[11px] text-emerald-400 flex items-center gap-1"><Check size={11} /> 팀 이름이 저장되었습니다</p>}
        {teamStatus === "error" && <p className="text-[11px] text-red-400 flex items-center gap-1"><X size={11} /> 저장 실패</p>}
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

      {/* GitHub OAuth App 설정 (관리자용) */}
      <div className="glass-card rounded-xl p-4 space-y-3">
        <label className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] font-medium">
          <Key size={12} />
          GitHub OAuth App 구성
        </label>
        <div className="space-y-2">
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
            placeholder="Client Secret"
            className={`w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:border-[var(--accent)] transition-colors ${
              isDarkMode ? "bg-black/20 border-[var(--border)] text-[var(--text-primary)]" : "bg-slate-50 border-slate-200 text-slate-900"
            }`}
          />
          <button
            onClick={saveOauthConfig}
            disabled={oauthLoading || !oauthConfig.client_id || !oauthConfig.client_secret}
            className={`w-full py-2 rounded-lg text-sm font-bold transition-all ${
              oauthLoading || !oauthConfig.client_id || !oauthConfig.client_secret
                ? "opacity-40 cursor-not-allowed bg-white/5"
                : "bg-blue-600 hover:bg-blue-500 text-white"
            }`}
          >
            {oauthLoading ? <Loader2 size={14} className="animate-spin mx-auto" /> : "인증 설정 저장"}
          </button>
          {oauthStatus === "ok" && <p className="text-[11px] text-emerald-400 flex items-center gap-1 mt-1"><Check size={11} /> 설정이 저장되었습니다</p>}
          {oauthStatus === "error" && <p className="text-[11px] text-red-400 flex items-center gap-1 mt-1"><X size={11} /> 저장 실패</p>}
          <p className="text-[10px] text-[var(--text-muted)] leading-relaxed">
            * 이 설정은 팀원 전체의 GitHub 로그인에 사용됩니다. .env 설정을 대체합니다.
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
