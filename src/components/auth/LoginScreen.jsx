import React, { useState, useEffect, useRef } from "react";
import useAppStore from "../../store/useAppStore";
import { LogIn, UserPlus, Eye, EyeOff, Loader2, Github, Copy, Check } from "lucide-react";

const ROLES = [
  { value: "pm", label: "PM (프로덕트 매니저)" },
  { value: "engineer", label: "Engineer (개발자)" },
  { value: "viewer", label: "Viewer (열람 전용)" },
];

export default function LoginScreen({ isFirstRun = false }) {
  const isDarkMode = useAppStore((s) => s.isDarkMode);
  const login = useAppStore((s) => s.login);
  const register = useAppStore((s) => s.register);
  const startGithubDeviceFlow = useAppStore((s) => s.startGithubDeviceFlow);
  const pollGithubDeviceFlow = useAppStore((s) => s.pollGithubDeviceFlow);

  const [mode, setMode] = useState(isFirstRun ? "register" : "login");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showPw, setShowPw] = useState(false);

  // GitHub Device Flow state
  const [ghFlow, setGhFlow] = useState(null); // { user_code, verification_uri, device_code, interval }
  const [ghLoading, setGhLoading] = useState(false);
  const [ghError, setGhError] = useState("");
  const [copied, setCopied] = useState(false);
  const pollRef = useRef(null);

  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    role: "engineer",
    github_username: "",
    team_name: "",
  });

  const setField = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target.value }));

  // Cleanup poll interval on unmount
  useEffect(() => () => clearInterval(pollRef.current), []);

  const startGithubLogin = async () => {
    setGhLoading(true); setGhError("");
    try {
      const data = await startGithubDeviceFlow();
      setGhFlow(data);
      window.open(data.verification_uri, "_blank");
      // Start polling
      const intervalMs = (data.interval || 5) * 1000;
      pollRef.current = setInterval(async () => {
        const result = await pollGithubDeviceFlow(data.device_code);
        if (result.status === "ok") {
          clearInterval(pollRef.current);
          setGhFlow(null);
        } else if (result.status === "error") {
          clearInterval(pollRef.current);
          setGhError(result.error || "인증 실패");
          setGhFlow(null);
        }
      }, intervalMs);
    } catch (err) {
      setGhError(err.message);
    } finally {
      setGhLoading(false);
    }
  };

  const cancelGithubLogin = () => {
    clearInterval(pollRef.current);
    setGhFlow(null); setGhError("");
  };

  const copyCode = () => {
    navigator.clipboard.writeText(ghFlow?.user_code || "");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "login") {
        await login(form.email, form.password);
      } else {
        await register({
          name: form.name,
          email: form.email,
          password: form.password,
          role: form.role,
          github_username: form.github_username || undefined,
          team_name: form.team_name || undefined,
        });
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const card = isDarkMode
    ? "bg-[#0F1219] border border-white/8 shadow-2xl"
    : "bg-white border border-slate-200 shadow-xl";
  const input = isDarkMode
    ? "bg-slate-900/60 border-white/8 text-white placeholder:text-slate-600 focus:border-blue-500/60"
    : "bg-slate-50 border-slate-200 text-slate-900 placeholder:text-slate-400 focus:border-blue-500";
  const label = isDarkMode ? "text-slate-400" : "text-slate-600";

  return (
    <div
      className="h-screen w-screen flex items-center justify-center"
      style={{ background: "var(--bg-root)" }}
    >
      <div className={`w-full max-w-sm rounded-2xl p-8 ${card}`}>
        {/* 헤더 */}
        <div className="mb-8 text-center">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-blue-600/10 mb-4">
            <span className="text-2xl font-black text-blue-500">N</span>
          </div>
          <h1 className={`text-2xl font-black tracking-tight ${isDarkMode ? "text-white" : "text-slate-900"}`}>
            NAVIGATOR
          </h1>
          <p className={`text-sm mt-1 ${label}`}>
            {mode === "login" ? "팀 계정으로 로그인" : "새 계정 만들기"}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* 회원가입 전용 필드 */}
          {mode === "register" && (
            <>
              <Field label="이름" value={form.name} onChange={setField("name")}
                placeholder="홍길동" required inputClass={input} labelClass={label} />
              <div>
                <label className={`block text-xs font-semibold mb-1.5 ${label}`}>역할</label>
                <select
                  value={form.role}
                  onChange={setField("role")}
                  className={`w-full rounded-xl px-3 py-2.5 text-sm border outline-none transition-colors ${input}`}
                >
                  {ROLES.map((r) => (
                    <option key={r.value} value={r.value}>{r.label}</option>
                  ))}
                </select>
              </div>
              <Field label="팀 이름 (선택)" value={form.team_name} onChange={setField("team_name")}
                placeholder="예: NAVIGATOR Team" inputClass={input} labelClass={label} />
              <Field label="GitHub 아이디 (선택)" value={form.github_username}
                onChange={setField("github_username")} placeholder="github-username"
                inputClass={input} labelClass={label} />
            </>
          )}

          {/* 공통 필드 */}
          <Field label="이메일" type="email" value={form.email} onChange={setField("email")}
            placeholder="you@example.com" required inputClass={input} labelClass={label} />

          <div>
            <label className={`block text-xs font-semibold mb-1.5 ${label}`}>
              비밀번호
            </label>
            <div className="relative">
              <input
                type={showPw ? "text" : "password"}
                value={form.password}
                onChange={setField("password")}
                placeholder="••••••••"
                required
                className={`w-full rounded-xl px-3 py-2.5 pr-10 text-sm border outline-none transition-colors ${input}`}
              />
              <button
                type="button"
                onClick={() => setShowPw((p) => !p)}
                className={`absolute right-3 top-1/2 -translate-y-1/2 ${label} hover:text-blue-400`}
              >
                {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          </div>

          {/* 에러 */}
          {error && (
            <p className="text-red-500 text-xs font-medium bg-red-500/10 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          {/* 제출 버튼 */}
          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-bold py-2.5 px-4 rounded-xl text-sm transition-colors mt-2"
          >
            {loading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : mode === "login" ? (
              <LogIn size={16} />
            ) : (
              <UserPlus size={16} />
            )}
            {mode === "login" ? "로그인" : "계정 만들기"}
          </button>
        </form>

        {/* GitHub OAuth 구분선 */}
        <div className="mt-5 flex items-center gap-3">
          <div className={`flex-1 h-px ${isDarkMode ? "bg-white/10" : "bg-slate-200"}`} />
          <span className={`text-xs font-medium ${label}`}>또는</span>
          <div className={`flex-1 h-px ${isDarkMode ? "bg-white/10" : "bg-slate-200"}`} />
        </div>

        {/* GitHub Device Flow */}
        {ghFlow ? (
          <div className={`mt-4 p-4 rounded-xl border space-y-3 ${isDarkMode ? "bg-white/5 border-white/10" : "bg-slate-50 border-slate-200"}`}>
            <p className={`text-xs font-bold ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>
              GitHub에서 아래 코드를 입력하세요
            </p>
            <div className="flex items-center gap-2">
              <span className={`flex-1 text-center text-2xl font-black tracking-[0.25em] py-3 rounded-xl ${isDarkMode ? "bg-black/30 text-white" : "bg-white border border-slate-200 text-slate-900"}`}>
                {ghFlow.user_code}
              </span>
              <button
                onClick={copyCode}
                className={`p-2.5 rounded-lg transition-colors ${isDarkMode ? "hover:bg-white/10 text-slate-400" : "hover:bg-slate-100 text-slate-500"}`}
                title="코드 복사"
              >
                {copied ? <Check size={16} className="text-emerald-400" /> : <Copy size={16} />}
              </button>
            </div>
            <p className="text-xs opacity-50 text-center">
              브라우저에서 자동으로 열립니다 · 승인 후 자동 로그인됩니다
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => window.open(ghFlow.verification_uri, "_blank")}
                className="flex-1 py-2 text-xs font-bold rounded-lg bg-slate-800 hover:bg-slate-700 text-white transition-colors"
              >
                GitHub 페이지 열기
              </button>
              <button
                onClick={cancelGithubLogin}
                className={`px-4 text-xs font-bold rounded-lg transition-colors ${isDarkMode ? "bg-white/5 hover:bg-white/10 text-slate-400" : "bg-slate-100 hover:bg-slate-200 text-slate-600"}`}
              >
                취소
              </button>
            </div>
            {ghError && <p className="text-xs text-red-400 text-center">{ghError}</p>}
          </div>
        ) : (
          <button
            type="button"
            onClick={startGithubLogin}
            disabled={ghLoading}
            className={`mt-3 w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl text-sm font-bold border transition-all ${
              isDarkMode
                ? "bg-white/5 hover:bg-white/10 border-white/10 text-slate-200"
                : "bg-white hover:bg-slate-50 border-slate-200 text-slate-800 shadow-sm"
            } disabled:opacity-50`}
          >
            {ghLoading ? <Loader2 size={16} className="animate-spin" /> : <Github size={16} />}
            GitHub로 로그인
          </button>
        )}
        {ghError && !ghFlow && (
          <p className="text-xs text-red-400 text-center mt-2">{ghError}</p>
        )}

        {/* 모드 전환 */}
        <div className="mt-5 text-center">
          <button
            onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}
            className={`text-xs font-medium hover:text-blue-400 transition-colors ${label}`}
          >
            {mode === "login"
              ? "계정이 없으신가요? 회원가입"
              : "이미 계정이 있으신가요? 로그인"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, placeholder, type = "text", required, inputClass, labelClass }) {
  return (
    <div>
      <label className={`block text-xs font-semibold mb-1.5 ${labelClass}`}>{label}</label>
      <input
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        required={required}
        className={`w-full rounded-xl px-3 py-2.5 text-sm border outline-none transition-colors ${inputClass}`}
      />
    </div>
  );
}
