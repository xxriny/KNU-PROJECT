import React, { useState } from "react";
import useAppStore from "../../store/useAppStore";
import { serverRequest } from "../../api/serverClient";
import { Users, Loader2, ArrowRight } from "lucide-react";

export default function TeamCreateScreen({ onClose } = {}) {
  const isDarkMode = useAppStore((s) => s.isDarkMode);
  const createTeam = useAppStore((s) => s.createTeam);
  const currentUser = useAppStore((s) => s.currentUser);

  const [mode, setMode] = useState("create"); // "create" | "join"
  const [teamName, setTeamName] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [focused, setFocused] = useState(false);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!teamName.trim()) return;
    setLoading(true);
    setError("");
    try {
      await createTeam(teamName.trim());
      onClose?.();
    } catch (err) {
      setError(err.message || "팀 생성에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const handleJoin = async (e) => {
    e.preventDefault();
    if (!inviteCode.trim()) return;
    setLoading(true);
    setError("");
    try {
      const token = useAppStore.getState().authToken;

      let code = inviteCode.trim();
      try {
        const url = new URL(code);
        code = url.searchParams.get("invite") || code;
      } catch (_) {}

      await serverRequest(`/auth/invites/${code}/join`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });

      await useAppStore.getState().checkAuthStatus();
      await useAppStore.getState().loadMyTeams();
      onClose?.();
    } catch (err) {
      setError(err.message || "오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const bg        = isDarkMode ? "#0D1117" : "#F1F5F9";
  const cardBg    = isDarkMode ? "#161B22" : "#FFFFFF";
  const border    = isDarkMode ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.07)";
  const textPri   = isDarkMode ? "#E6EDF3" : "#1E293B";
  const textMuted = isDarkMode ? "#8B949E" : "#64748B";
  const inputBg   = isDarkMode ? "#0D1117" : "#F8FAFC";
  const inputBorder = isDarkMode ? "rgba(255,255,255,0.1)" : "#E2E8F0";

  return (
    <div className={onClose ? "" : "h-screen w-screen flex items-center justify-center p-4"}
      style={onClose ? {} : { background: bg }}>
      <div className="w-full max-w-[380px]"
        style={{
          background: cardBg,
          border: `1px solid ${border}`,
          borderRadius: "20px",
          boxShadow: isDarkMode
            ? "0 24px 64px rgba(0,0,0,0.5)"
            : "0 8px 32px rgba(0,0,0,0.10)",
        }}>

        {/* 헤더 */}
        <div className="flex flex-col items-center pt-8 pb-6 px-7">
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center mb-3"
            style={{ background: "linear-gradient(135deg, #2563EB, #4F46E5)" }}>
            <Users size={22} className="text-white" />
          </div>
          <h1 className="text-[17px] font-black tracking-tight" style={{ color: textPri }}>
            {mode === "create" ? "팀을 만들어주세요" : "팀에 참여하세요"}
          </h1>
          <p className="text-xs mt-1 text-center" style={{ color: textMuted }}>
            {currentUser?.name ? `${currentUser.name}님, ` : ""}
            {mode === "create" 
              ? "팀 이름을 정하면 바로 시작할 수 있습니다." 
              : "초대 링크나 코드를 입력하면 합류할 수 있습니다."}
          </p>
        </div>

        {/* 탭 */}
        <div className="px-7 pb-4">
          <div className="flex rounded-xl p-1" style={{ background: "rgba(128,128,128,0.1)" }}>
            <button
              type="button"
              onClick={() => { setMode("create"); setError(""); }}
              className="flex-1 py-1.5 text-xs font-bold rounded-lg transition-all"
              style={{
                background: mode === "create" ? (isDarkMode ? "#1F2937" : "#FFFFFF") : "transparent",
                color: mode === "create" ? (isDarkMode ? "#60A5FA" : "#2563EB") : textMuted,
                boxShadow: mode === "create" ? "0 2px 4px rgba(0,0,0,0.05)" : "none"
              }}
            >
              새 팀 만들기
            </button>
            <button
              type="button"
              onClick={() => { setMode("join"); setError(""); }}
              className="flex-1 py-1.5 text-xs font-bold rounded-lg transition-all"
              style={{
                background: mode === "join" ? (isDarkMode ? "#1F2937" : "#FFFFFF") : "transparent",
                color: mode === "join" ? (isDarkMode ? "#60A5FA" : "#2563EB") : textMuted,
                boxShadow: mode === "join" ? "0 2px 4px rgba(0,0,0,0.05)" : "none"
              }}
            >
              초대로 참여
            </button>
          </div>
        </div>

        {/* 폼 */}
        <form onSubmit={mode === "create" ? handleCreate : handleJoin} className="px-7 pb-7 flex flex-col gap-3">
          {mode === "create" ? (
            <div>
              <label className="block text-[11px] font-semibold mb-1.5"
                style={{ color: textMuted }}>
                팀 이름
              </label>
              <input
                type="text"
                value={teamName}
                onChange={(e) => setTeamName(e.target.value)}
                placeholder="예: NAVIGATOR Dev Team"
                autoFocus
                maxLength={80}
                onFocus={() => setFocused(true)}
                onBlur={() => setFocused(false)}
                className="w-full rounded-xl px-3 py-2.5 text-sm outline-none transition-all"
                style={{
                  background: inputBg,
                  border: `1px solid ${focused ? "#3B82F6" : inputBorder}`,
                  color: textPri,
                  boxShadow: focused ? "0 0 0 3px rgba(59,130,246,0.13)" : "none",
                }}
              />
            </div>
          ) : (
            <div>
              <label className="block text-[11px] font-semibold mb-1.5"
                style={{ color: textMuted }}>
                초대 링크 또는 코드
              </label>
              <input
                type="text"
                value={inviteCode}
                onChange={(e) => setInviteCode(e.target.value)}
                placeholder="코드 또는 URL 붙여넣기"
                autoFocus
                onFocus={() => setFocused(true)}
                onBlur={() => setFocused(false)}
                className="w-full rounded-xl px-3 py-2.5 text-sm outline-none transition-all font-mono"
                style={{
                  background: inputBg,
                  border: `1px solid ${focused ? "#3B82F6" : inputBorder}`,
                  color: textPri,
                  boxShadow: focused ? "0 0 0 3px rgba(59,130,246,0.13)" : "none",
                }}
              />
            </div>
          )}

          {error && (
            <div className="flex items-start gap-2 rounded-xl px-3 py-2.5"
              style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)" }}>
              <p className="text-[11px] font-medium text-red-400">{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={(mode === "create" ? !teamName.trim() : !inviteCode.trim()) || loading}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-bold text-white transition-all disabled:opacity-40"
            style={{ background: "linear-gradient(135deg, #2563EB, #4F46E5)" }}>
            {loading
              ? <Loader2 size={15} className="animate-spin" />
              : <>{mode === "create" ? "팀 생성하기" : "합류하기"} <ArrowRight size={14} /></>}
          </button>

          {mode === "create" && (
            <p className="text-[11px] text-center" style={{ color: textMuted }}>
              팀 생성 시 자동으로 <span className="font-semibold">PM 역할</span>이 부여됩니다.
            </p>
          )}
        </form>
      </div>
    </div>
  );
}
