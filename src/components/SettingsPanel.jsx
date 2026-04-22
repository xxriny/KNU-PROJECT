/**
 * SettingsPanel — 설정 패널 (분리된 독립 컴포넌트)
 */
import React from "react";
import useAppStore from "../store/useAppStore";
import { Key, Cpu, Sun, Moon } from "lucide-react";

export default function SettingsPanel() {
  const {
    apiKey, setApiKey,
    model, setModel,
    availableModels,
    backendHasKey,
    isDarkMode, toggleDarkMode,
  } = useAppStore();

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
