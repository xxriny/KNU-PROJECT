import React, { useState, useEffect, useRef } from "react";
import useAppStore from "../../store/useAppStore";
import {
  LogIn, UserPlus, Eye, EyeOff, Loader2, Github,
  AlertCircle, Settings, ExternalLink, ChevronUp,
} from "lucide-react";

const ROLES = [
  { value: "pm", label: "PM (프로덕트 매니저)" },
  { value: "engineer", label: "Engineer (개발자)" },
  { value: "viewer", label: "Viewer (열람 전용)" },
];

// Device Flow 상태: idle | starting | waiting
const DEVICE_IDLE = "idle";
const DEVICE_STARTING = "starting";
const DEVICE_WAITING = "waiting";

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

  // Device Flow 상태
  const [deviceState, setDeviceState] = useState(DEVICE_IDLE);
  const [userCode, setUserCode] = useState("");
  const [verificationUri, setVerificationUri] = useState("https://github.com/login/device");
  const [ghError, setGhError] = useState("");

  // 고급 설정 (기존 OAuth App 직접 입력)
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [setupConfig, setSetupConfig] = useState({ client_id: "", client_secret: "" });
  const [setupLoading, setSetupLoading] = useState(false);

  const pollRef = useRef(null);

  const [form, setForm] = useState({
    name: "", email: "", password: "", role: "engineer",
    github_username: "", team_name: "",
  });
  const setField = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target.value }));

  useEffect(() => () => clearInterval(pollRef.current), []);

  const stopPolling = () => {
    clearTimeout(pollRef.current);
    pollRef.current = null;
  };

  const startDeviceFlow = async () => {
    setDeviceState(DEVICE_STARTING);
    setGhError("");
    try {
      const data = await startGithubDeviceFlow();
      setUserCode(data.user_code || "");
      setVerificationUri(data.verification_uri || "https://github.com/login/device");
      const initialInterval = Math.max(data.interval || 5, 5);
      setDeviceState(DEVICE_WAITING);

      // 브라우저 자동 오픈
      const uri = data.verification_uri || "https://github.com/login/device";
      if (window.electronAPI?.openGithubAuth) {
        window.electronAPI.openGithubAuth(uri);
      } else {
        window.open(uri, "_blank");
      }

      // setTimeout 기반 폴링 (slow_down 시 interval 동적 조정)
      const schedulePoll = (intervalSec, deviceCode) => {
        pollRef.current = setTimeout(async () => {
          if (!pollRef.current && pollRef.current !== 0) return; // stopped
          try {
            const result = await pollGithubDeviceFlow(deviceCode);
            if (result.status === "ok") {
              pollRef.current = null;
              if (window.electronAPI?.reloadWindow) {
                await window.electronAPI.reloadWindow();
              } else {
                window.location.reload();
              }
            } else if (result.status === "error") {
              pollRef.current = null;
              setDeviceState(DEVICE_IDLE);
              setGhError(result.error || "GitHub 인증 실패");
            } else {
              // pending (authorization_pending or slow_down)
              const nextInterval = result.interval
                ? Math.max(result.interval, intervalSec)
                : intervalSec;
              schedulePoll(nextInterval, deviceCode);
            }
          } catch (err) {
            pollRef.current = null;
            setDeviceState(DEVICE_IDLE);
            setGhError(err.message || "네트워크 오류가 발생했습니다.");
          }
        }, intervalSec * 1000);
      };

      schedulePoll(initialInterval, data.device_code);

    } catch (err) {
      setDeviceState(DEVICE_IDLE);
      if (err.message === "needs_oauth_setup") {
        setShowAdvanced(true);
        setGhError("GitHub OAuth App Client ID가 설정되지 않았습니다. 고급 설정에서 입력해주세요.");
      } else {
        setGhError(err.message || "GitHub 인증 시작 실패");
      }
    }
  };

  const openBrowser = () => {
    if (window.electronAPI?.openGithubAuth) {
      window.electronAPI.openGithubAuth(verificationUri);
    } else {
      window.open(verificationUri, "_blank");
    }
  };

  const cancelDeviceFlow = () => {
    stopPolling();
    setDeviceState(DEVICE_IDLE);
    setGhError("");
    setUserCode("");
  };

  const submitAdvancedSetup = async () => {
    setSetupLoading(true);
    setGhError("");
    try {
      const port = useAppStore.getState().backendPort || 8000;
      const res = await fetch(`http://127.0.0.1:${port}/auth/setup-oauth`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(setupConfig),
      });
      const data = await res.json();
      if (res.status === 403) {
        setGhError("OAuth 설정은 관리자 설정 패널에서 변경하세요.");
        return;
      }
      if (!res.ok) throw new Error(data.detail || "설정 실패");
      setShowAdvanced(false);
      startDeviceFlow();
    } catch (err) {
      setGhError(err.message);
    } finally {
      setSetupLoading(false);
    }
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
          name: form.name, email: form.email, password: form.password,
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
    ? "bg-[#0d1117] border border-white/10 shadow-2xl shadow-black/50"
    : "bg-white border border-slate-200 shadow-xl";
  const input = isDarkMode
    ? "bg-slate-800/60 border-white/10 text-white placeholder:text-slate-500 focus:border-blue-500/70 focus:bg-slate-800"
    : "bg-slate-50 border-slate-200 text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:bg-white";
  const label = isDarkMode ? "text-slate-400" : "text-slate-500";
  const divider = isDarkMode ? "bg-white/10" : "bg-slate-200";
  const panelBg = isDarkMode ? "bg-white/5 border-white/10" : "bg-slate-50 border-slate-200";
  const cancelBtn = isDarkMode
    ? "bg-white/5 hover:bg-white/10 text-slate-400"
    : "bg-slate-100 hover:bg-slate-200 text-slate-600";

  return (
    <div className="h-screen w-screen flex items-center justify-center p-4" style={{ background: "var(--bg-root)" }}>
      <div className={`w-full max-w-sm rounded-2xl p-7 max-h-[95vh] overflow-y-auto custom-scrollbar ${card}`}>

        {/* Header */}
        <div className="mb-7 text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-blue-600/15 mb-3">
            <span className="text-xl font-black text-blue-500">N</span>
          </div>
          <h1 className={`text-xl font-black tracking-tight ${isDarkMode ? "text-white" : "text-slate-900"}`}>
            NAVIGATOR
          </h1>
          <p className={`text-xs mt-1 ${label}`}>
            {mode === "login" ? "팀 계정으로 로그인" : "새 계정 만들기"}
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-3.5">
          {mode === "register" && (
            <>
              <Field label="이름" value={form.name} onChange={setField("name")}
                placeholder="홍길동" required inputClass={input} labelClass={label} />
              <div>
                <label className={`block text-xs font-semibold mb-1.5 ${label}`}>역할</label>
                <select value={form.role} onChange={setField("role")}
                  className={`w-full rounded-xl px-3 py-2.5 text-sm border outline-none transition-colors ${input}`}>
                  {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
              </div>
              <Field label="팀 이름 (선택)" value={form.team_name} onChange={setField("team_name")}
                placeholder="예: NAVIGATOR Team" inputClass={input} labelClass={label} />
              <Field label="GitHub 아이디 (선택)" value={form.github_username}
                onChange={setField("github_username")} placeholder="github-username"
                inputClass={input} labelClass={label} />
            </>
          )}

          <Field label="이메일" type="email" value={form.email} onChange={setField("email")}
            placeholder="you@example.com" required inputClass={input} labelClass={label} />

          <div>
            <label className={`block text-xs font-semibold mb-1.5 ${label}`}>비밀번호</label>
            <div className="relative">
              <input type={showPw ? "text" : "password"} value={form.password}
                onChange={setField("password")} placeholder="••••••••" required
                className={`w-full rounded-xl px-3 py-2.5 pr-10 text-sm border outline-none transition-colors ${input}`} />
              <button type="button" onClick={() => setShowPw((p) => !p)}
                className={`absolute right-3 top-1/2 -translate-y-1/2 ${label} hover:text-blue-400 transition-colors`}>
                {showPw ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>

          {error && (
            <div className="flex items-start gap-2 text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2.5">
              <AlertCircle size={13} className="mt-0.5 shrink-0" />
              <p className="text-xs font-medium">{error}</p>
            </div>
          )}

          <button type="submit" disabled={loading}
            className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 active:bg-blue-700 disabled:opacity-50 text-white font-bold py-2.5 px-4 rounded-xl text-sm transition-colors">
            {loading ? <Loader2 size={15} className="animate-spin" /> : mode === "login" ? <LogIn size={15} /> : <UserPlus size={15} />}
            {mode === "login" ? "로그인" : "계정 만들기"}
          </button>
        </form>

        {/* Divider */}
        <div className="my-5 flex items-center gap-3">
          <div className={`flex-1 h-px ${divider}`} />
          <span className={`text-xs font-medium ${label}`}>또는</span>
          <div className={`flex-1 h-px ${divider}`} />
        </div>

        {/* GitHub Device Flow */}
        {deviceState === DEVICE_WAITING ? (
          <div className={`rounded-xl border p-4 space-y-3 ${panelBg}`}>
            <p className={`text-xs font-bold ${isDarkMode ? "text-slate-200" : "text-slate-700"}`}>
              브라우저에서 아래 코드를 입력하세요
            </p>

            {/* User Code — 크게 표시 */}
            <div className={`rounded-lg py-3 text-center ${isDarkMode ? "bg-white/5" : "bg-white border border-slate-200"}`}>
              <span className={`font-mono text-2xl font-black tracking-[0.25em] select-all ${isDarkMode ? "text-white" : "text-slate-900"}`}>
                {userCode}
              </span>
              <p className={`text-xs mt-1 ${label}`}>github.com/login/device</p>
            </div>

            <button onClick={openBrowser}
              className="w-full flex items-center justify-center gap-2 py-2.5 text-xs font-bold rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors">
              <ExternalLink size={13} />
              GitHub에서 인증하기
            </button>

            <div className="flex items-center gap-2">
              <Loader2 size={12} className="animate-spin text-blue-400 shrink-0" />
              <p className={`text-xs ${label}`}>코드 입력 후 Authorize하면 자동으로 로그인됩니다</p>
            </div>

            {ghError && (
              <div className="flex items-start gap-2 text-red-400">
                <AlertCircle size={12} className="mt-0.5 shrink-0" />
                <p className="text-xs">{ghError}</p>
              </div>
            )}

            <button onClick={cancelDeviceFlow}
              className={`w-full py-2 text-xs font-bold rounded-lg transition-colors ${cancelBtn}`}>
              취소
            </button>
          </div>
        ) : (
          <>
            <div className="flex gap-2">
              <button type="button" onClick={startDeviceFlow}
                disabled={deviceState === DEVICE_STARTING}
                className={`flex-1 flex items-center justify-center gap-2.5 py-2.5 px-4 rounded-xl text-sm font-bold border transition-all disabled:opacity-50 ${
                  isDarkMode
                    ? "bg-white/5 hover:bg-white/10 active:bg-white/15 border-white/10 text-slate-200"
                    : "bg-white hover:bg-slate-50 active:bg-slate-100 border-slate-200 text-slate-800 shadow-sm"
                }`}>
                {deviceState === DEVICE_STARTING
                  ? <Loader2 size={15} className="animate-spin" />
                  : <Github size={15} />}
                GitHub로 로그인
              </button>
              <button
                type="button"
                onClick={() => setShowAdvanced((v) => !v)}
                className={`px-3.5 rounded-xl border transition-all ${
                  isDarkMode
                    ? "bg-white/5 hover:bg-white/10 border-white/10 text-slate-400 hover:text-white"
                    : "bg-white hover:bg-slate-50 border-slate-200 text-slate-500 hover:text-slate-800 shadow-sm"
                }`}
                title="고급 설정"
              >
                {showAdvanced ? <ChevronUp size={15} /> : <Settings size={15} />}
              </button>
            </div>

            {ghError && (
              <div className="flex items-start gap-2 mt-2.5 text-red-400">
                <AlertCircle size={12} className="mt-0.5 shrink-0" />
                <p className="text-xs">{ghError}</p>
              </div>
            )}

            {/* 고급 설정: 커스텀 OAuth App */}
            {showAdvanced && (
              <div className={`mt-3 rounded-xl border p-4 space-y-3 ${panelBg}`}>
                <div className="flex items-center gap-2">
                  <Settings size={12} className={label} />
                  <p className={`text-xs font-bold ${isDarkMode ? "text-slate-200" : "text-slate-700"}`}>
                    고급: 커스텀 GitHub OAuth App
                  </p>
                </div>
                <p className={`text-xs ${label}`}>
                  팀 전용 GitHub OAuth App을 사용하려면 Client ID와 Secret을 입력하세요.
                  일반 사용자는 위의 "GitHub로 로그인" 버튼만 사용하면 됩니다.
                </p>
                <div className="space-y-2">
                  <div>
                    <label className={`block text-xs font-semibold mb-1 ${label}`}>Client ID</label>
                    <input type="text" placeholder="Iv23li..."
                      value={setupConfig.client_id}
                      onChange={(e) => setSetupConfig((p) => ({ ...p, client_id: e.target.value }))}
                      className={`w-full rounded-lg px-3 py-2 text-xs border outline-none transition-colors ${input}`} />
                  </div>
                  <div>
                    <label className={`block text-xs font-semibold mb-1 ${label}`}>Client Secret</label>
                    <input type="password" placeholder="••••••••••••••••••••"
                      value={setupConfig.client_secret}
                      onChange={(e) => setSetupConfig((p) => ({ ...p, client_secret: e.target.value }))}
                      className={`w-full rounded-lg px-3 py-2 text-xs border outline-none transition-colors ${input}`} />
                  </div>
                </div>
                <div className="flex gap-2">
                  <button onClick={submitAdvancedSetup}
                    disabled={setupLoading || !setupConfig.client_id || !setupConfig.client_secret}
                    className="flex-1 py-2 text-xs font-bold rounded-lg bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50 transition-colors">
                    {setupLoading ? <Loader2 size={12} className="animate-spin mx-auto" /> : "저장 후 로그인"}
                  </button>
                  <button onClick={() => { setShowAdvanced(false); setGhError(""); }}
                    className={`px-4 text-xs font-bold rounded-lg transition-colors ${cancelBtn}`}>
                    닫기
                  </button>
                </div>
              </div>
            )}
          </>
        )}

        {/* Mode switch */}
        <div className="mt-6 text-center">
          <button onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}
            className={`text-xs transition-colors ${label} hover:text-blue-400`}>
            {mode === "login"
              ? <>계정이 없으신가요? <span className="font-bold text-blue-500">회원가입</span></>
              : <>이미 계정이 있으신가요? <span className="font-bold text-blue-500">로그인</span></>}
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
      <input type={type} value={value} onChange={onChange} placeholder={placeholder} required={required}
        className={`w-full rounded-xl px-3 py-2.5 text-sm border outline-none transition-colors ${inputClass}`} />
    </div>
  );
}
