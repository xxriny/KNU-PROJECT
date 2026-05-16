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
  
  // First run setup state
  const [needsSetup, setNeedsSetup] = useState(false);
  const [setupConfig, setSetupConfig] = useState({ client_id: "", client_secret: "" });
  const [setupLoading, setSetupLoading] = useState(false);
  
  const pollRef = useRef(null);
  const expireRef = useRef(null);
  const pollIntervalRef = useRef(5000);

  const GH_ERRORS = {
    access_denied: "인증이 취소되었습니다. GitHub에서 승인을 거부했습니다.",
    expired_token: "인증 코드가 만료되었습니다. 다시 시도하세요.",
    incorrect_client_credentials: "OAuth 클라이언트 설정이 잘못되었습니다.",
  };

  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    role: "engineer",
    github_username: "",
    team_name: "",
  });

  const setField = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target.value }));

  // Cleanup on unmount
  useEffect(() => () => {
    clearInterval(pollRef.current);
    clearTimeout(expireRef.current);
  }, []);

  const stopPolling = (errMsg = null) => {
    clearInterval(pollRef.current);
    clearTimeout(expireRef.current);
    setGhFlow(null);
    if (errMsg) setGhError(errMsg);
  };

  const startGithubLogin = async () => {
    clearInterval(pollRef.current);
    clearTimeout(expireRef.current);
    setGhLoading(true); setGhError("");
    try {
      const data = await startGithubDeviceFlow();
      setGhFlow(data);
      window.open(data.verification_uri, "_blank");
      pollIntervalRef.current = (data.interval || 5) * 1000;

      const doPoll = async () => {
        try {
          const result = await pollGithubDeviceFlow(data.device_code);
          if (result.status === "ok") {
            stopPolling();
          } else if (result.status === "error") {
            stopPolling(GH_ERRORS[result.error] || result.error || "인증 실패");
          } else if (result.error === "slow_down") {
            clearInterval(pollRef.current);
            pollIntervalRef.current += 5000;
            pollRef.current = setInterval(doPoll, pollIntervalRef.current);
          }
        } catch (_) {}
      };

      pollRef.current = setInterval(doPoll, pollIntervalRef.current);

      expireRef.current = setTimeout(() => {
        stopPolling("인증 코드가 만료되었습니다. 다시 시도하세요.");
      }, (data.expires_in || 900) * 1000);
    } catch (err) {
      // 어떤 에러가 나더라도(404, 422, 500 등), 설정이 잘못되었을 가능성이 크므로
      // 사용자에게 직접 입력할 수 있는 폼을 보여줍니다.
      setNeedsSetup(true);
      setGhError(err.message);
    } finally {
      setGhLoading(false);
    }
  };

  const submitSetup = async () => {
    setSetupLoading(true); setGhError("");
    try {
      const port = useAppStore.getState().backendPort || 8000;
      const res = await fetch(`http://127.0.0.1:${port}/auth/setup-oauth`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(setupConfig),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "설정 실패");
      
      // 설정 성공 시 바로 로그인 플로우 시작
      setNeedsSetup(false);
      startGithubLogin();
    } catch (err) {
      setGhError(err.message);
    } finally {
      setSetupLoading(false);
    }
  };

  const cancelGithubLogin = () => stopPolling();

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
        ) : needsSetup ? (
          <div className={`mt-4 p-4 rounded-xl border space-y-3 ${isDarkMode ? "bg-white/5 border-white/10" : "bg-slate-50 border-slate-200"}`}>
            <p className={`text-xs font-bold ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>
              시스템 초기화: GitHub OAuth 구성
            </p>
            <input
              type="text"
              placeholder="Client ID"
              value={setupConfig.client_id}
              onChange={(e) => setSetupConfig(p => ({...p, client_id: e.target.value}))}
              className={`w-full rounded-lg px-3 py-2 text-xs border outline-none transition-colors ${input}`}
            />
            <input
              type="password"
              placeholder="Client Secret"
              value={setupConfig.client_secret}
              onChange={(e) => setSetupConfig(p => ({...p, client_secret: e.target.value}))}
              className={`w-full rounded-lg px-3 py-2 text-xs border outline-none transition-colors ${input}`}
            />
            <div className="flex gap-2">
              <button
                onClick={submitSetup}
                disabled={setupLoading || !setupConfig.client_id || !setupConfig.client_secret}
                className="flex-1 py-2 text-xs font-bold rounded-lg bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50 transition-colors"
              >
                {setupLoading ? "저장 중..." : "저장 후 로그인 계속"}
              </button>
              <button
                onClick={() => { setNeedsSetup(false); setGhError(""); }}
                className={`px-3 text-xs font-bold rounded-lg transition-colors ${isDarkMode ? "bg-white/5 hover:bg-white/10 text-slate-400" : "bg-slate-100 hover:bg-slate-200 text-slate-600"}`}
              >
                취소
              </button>
            </div>
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
        {ghError && !ghFlow && !needsSetup && (
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
