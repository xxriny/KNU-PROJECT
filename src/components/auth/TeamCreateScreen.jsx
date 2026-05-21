/**
 * TeamCreateScreen — 로그인 후 팀이 없는 사용자를 위한 팀 생성 화면
 */
import React, { useState } from "react";
import useAppStore from "../../store/useAppStore";
import { Users, Loader2, ArrowRight } from "lucide-react";

export default function TeamCreateScreen() {
  const isDarkMode = useAppStore((s) => s.isDarkMode);
  const createTeam = useAppStore((s) => s.createTeam);
  const currentUser = useAppStore((s) => s.currentUser);

  const [teamName, setTeamName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!teamName.trim()) return;
    setLoading(true);
    setError("");
    try {
      await createTeam(teamName.trim());
    } catch (err) {
      setError(err.message || "팀 생성에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const bg = isDarkMode ? "#0D1117" : "#F8FAFC";
  const cardBg = isDarkMode ? "#161B22" : "#FFFFFF";
  const border = isDarkMode ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)";
  const textPrimary = isDarkMode ? "#E6EDF3" : "#1E293B";
  const textMuted = isDarkMode ? "#8B949E" : "#64748B";
  const inputBg = isDarkMode ? "#0D1117" : "#F1F5F9";

  return (
    <div
      className="h-screen w-screen flex items-center justify-center"
      style={{ background: bg }}
    >
      <div
        className="w-full max-w-md rounded-2xl p-8 flex flex-col gap-6"
        style={{ background: cardBg, border: `1px solid ${border}`, boxShadow: "0 20px 60px rgba(0,0,0,0.25)" }}
      >
        {/* 헤더 */}
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg">
            <Users size={26} className="text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold" style={{ color: textPrimary }}>
              팀을 만들어주세요
            </h1>
            <p className="text-sm mt-1" style={{ color: textMuted }}>
              {currentUser?.name ? `${currentUser.name}님, ` : ""}
              팀 이름을 정하면 바로 시작할 수 있습니다.
            </p>
          </div>
        </div>

        {/* 폼 */}
        <form onSubmit={handleCreate} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-semibold" style={{ color: textMuted }}>
              팀 이름
            </label>
            <input
              type="text"
              value={teamName}
              onChange={(e) => setTeamName(e.target.value)}
              placeholder="예: NAVIGATOR Dev Team"
              autoFocus
              maxLength={80}
              className="w-full px-4 py-3 rounded-xl text-sm outline-none transition-all"
              style={{
                background: inputBg,
                border: `1px solid ${border}`,
                color: textPrimary,
              }}
            />
          </div>

          {error && (
            <p className="text-xs text-red-400 px-1">{error}</p>
          )}

          <button
            type="submit"
            disabled={!teamName.trim() || loading}
            className="w-full flex items-center justify-center gap-2 py-3 rounded-xl font-semibold text-sm text-white transition-all"
            style={{
              background: teamName.trim() && !loading
                ? "linear-gradient(135deg, #2563EB, #4F46E5)"
                : "rgba(99,102,241,0.3)",
              cursor: teamName.trim() && !loading ? "pointer" : "not-allowed",
            }}
          >
            {loading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <>
                팀 생성하기
                <ArrowRight size={16} />
              </>
            )}
          </button>
        </form>

        {/* 안내 */}
        <p className="text-[11px] text-center" style={{ color: textMuted }}>
          팀을 생성하면 자동으로 PM 역할이 부여됩니다.
          <br />
          설정에서 팀원을 초대하고 역할을 관리할 수 있습니다.
        </p>
      </div>
    </div>
  );
}
