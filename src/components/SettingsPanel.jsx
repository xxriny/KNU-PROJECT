/**
 * SettingsPanel — 설정 패널 (분리된 독립 컴포넌트)
 */
import React, { useState } from "react";
import useAppStore from "../store/useAppStore";
import { Key, Cpu, Sun, Moon, Github, Check, X, Loader2 } from "lucide-react";

export default function SettingsPanel() {
  const {
    apiKey, setApiKey,
    model, setModel,
    availableModels,
    backendHasKey,
    isDarkMode, toggleDarkMode,
    githubToken, githubOwner, githubRepo,
    setGithubSettings,
    backendPort,
  } = useAppStore();

  const [ghToken, setGhToken] = useState(githubToken);
  const [ghOwner, setGhOwner] = useState(githubOwner);
  const [ghRepo, setGhRepo] = useState(githubRepo);
  const [ghStatus, setGhStatus] = useState(null); // null | "loading" | "ok" | "error"
  const [ghMessage, setGhMessage] = useState("");

  const saveGithub = async () => {
    if (!ghToken.trim() || !ghOwner.trim() || !ghRepo.trim()) {
      setGhStatus("error");
      setGhMessage("토큰, 소유자, 레포지토리를 모두 입력하세요.");
      return;
    }
    setGhStatus("loading");
    try {
      const port = backendPort || 8000;
      const res = await fetch(`http://127.0.0.1:${port}/api/github/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: ghToken, owner: ghOwner, repo: ghRepo }),
      });
      const json = await res.json();
      if (json.status === "ok") {
        setGithubSettings(ghToken, ghOwner, ghRepo);
        setGhStatus("ok");
        setGhMessage(`연결 성공: ${json.repo} (${json.user})`);
      } else {
        setGhStatus("error");
        setGhMessage(json.error || "연결 실패");
      }
    } catch (e) {
      setGhStatus("error");
      setGhMessage("서버 연결 실패: " + e.message);
    }
  };

  return (
    <div className="p-5 space-y-5 max-w-md mx-auto mt-4">
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

      {/* GitHub Integration */}
      <div className="glass-card rounded-xl p-4 space-y-3">
        <label className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)] font-medium">
          <Github size={12} />
          GitHub 통합
          {githubToken && githubRepo && (
            <span className="ml-auto text-xs text-emerald-400 font-semibold flex items-center gap-1">
              <Check size={10} /> 연결됨
            </span>
          )}
        </label>

        <input
          type="password"
          value={ghToken}
          onChange={(e) => { setGhToken(e.target.value); setGhStatus(null); }}
          placeholder="GitHub Personal Access Token"
          className={`w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:border-[var(--accent)] transition-colors ${
            isDarkMode
              ? "bg-black/20 border-[var(--border)] text-[var(--text-primary)]"
              : "bg-slate-100/50 border-slate-200 text-slate-900"
          } placeholder-[var(--text-muted)]`}
        />

        <div className="flex gap-2">
          <input
            type="text"
            value={ghOwner}
            onChange={(e) => { setGhOwner(e.target.value); setGhStatus(null); }}
            placeholder="소유자 (owner)"
            className={`flex-1 px-3 py-2 text-sm border rounded-lg focus:outline-none focus:border-[var(--accent)] transition-colors ${
              isDarkMode
                ? "bg-black/20 border-[var(--border)] text-[var(--text-primary)]"
                : "bg-slate-100/50 border-slate-200 text-slate-900"
            } placeholder-[var(--text-muted)]`}
          />
          <input
            type="text"
            value={ghRepo}
            onChange={(e) => { setGhRepo(e.target.value); setGhStatus(null); }}
            placeholder="레포지토리 (repo)"
            className={`flex-1 px-3 py-2 text-sm border rounded-lg focus:outline-none focus:border-[var(--accent)] transition-colors ${
              isDarkMode
                ? "bg-black/20 border-[var(--border)] text-[var(--text-primary)]"
                : "bg-slate-100/50 border-slate-200 text-slate-900"
            } placeholder-[var(--text-muted)]`}
          />
        </div>

        <button
          onClick={saveGithub}
          disabled={ghStatus === "loading"}
          className={`w-full flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-semibold transition-all ${
            ghStatus === "loading"
              ? "opacity-50 cursor-not-allowed bg-white/5"
              : "bg-slate-800 hover:bg-slate-700 text-white dark:bg-white/10 dark:hover:bg-white/20"
          }`}
        >
          {ghStatus === "loading" ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Github size={14} />
          )}
          {ghStatus === "loading" ? "연결 확인 중..." : "저장 및 연결 확인"}
        </button>

        {ghStatus === "ok" && (
          <p className="text-xs text-emerald-400 flex items-center gap-1">
            <Check size={12} /> {ghMessage}
          </p>
        )}
        {ghStatus === "error" && (
          <p className="text-xs text-red-400 flex items-center gap-1">
            <X size={12} /> {ghMessage}
          </p>
        )}
        <p className="text-[11px] text-[var(--text-muted)]">
          GitHub Issues 퍼블리시 및 커밋 분석에 사용됩니다 (read/write 권한 필요).
        </p>
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
