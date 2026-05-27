import React, { useState, useEffect } from "react";
import { X, Send, User } from "lucide-react";
import useAppStore from "../../store/useAppStore";
import { serverRequest, SERVER_URL } from "../../api/serverClient";

const DOMAIN_ROLES = {
  backend:  ["backend", "software_engineer"],
  frontend: ["frontend", "software_engineer"],
  devops:   ["devops", "software_engineer"],
  pm:       ["pm"],
  general:  ["pm", "backend", "frontend", "devops", "software_engineer"],
};

const DOMAIN_LABEL = {
  backend:  "Backend",
  frontend: "Frontend",
  devops:   "DevOps",
  pm:       "PM",
  general:  "전체",
};

export default function ContactModal({ followup, onClose, isDarkMode }) {
  const { question, domain } = followup;
  const authToken = useAppStore((s) => s.authToken);
  const currentUser = useAppStore((s) => s.currentUser);

  const [members, setMembers] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!authToken || !currentUser?.team_id) return;
    serverRequest(`/auth/teams/${currentUser.team_id}/members`, {
      headers: { Authorization: `Bearer ${authToken}` },
    })
      .then((data) => {
        const compatRoles = DOMAIN_ROLES[domain] || DOMAIN_ROLES.general;
        const filtered = (data.members || []).filter(
          (m) => m.id !== currentUser.id && compatRoles.includes(m.role)
        );
        setMembers(filtered);
        if (filtered.length === 1) setSelectedId(filtered[0].id);
      })
      .catch(() => {});
  }, [authToken, currentUser, domain]);

  const handleSend = async () => {
    if (!selectedId || !message.trim()) return;
    setSending(true);
    setError("");
    try {
      await serverRequest("/messages", {
        method: "POST",
        headers: { Authorization: `Bearer ${authToken}` },
        body: JSON.stringify({
          receiver_id: selectedId,
          content: message.trim(),
          context_question: question,
          context_domain: domain,
        }),
      });
      setSent(true);
      setTimeout(onClose, 1500);
    } catch (e) {
      setError(e.message || "전송 중 오류가 발생했습니다.");
    } finally {
      setSending(false);
    }
  };

  const base = isDarkMode
    ? "bg-[#1c2128] border-white/[0.08] text-slate-100"
    : "bg-white border-slate-200 text-slate-900";
  const inputCls = isDarkMode
    ? "bg-white/[0.04] border-white/[0.08] text-slate-100 placeholder:text-slate-500 focus:border-blue-500/60"
    : "bg-slate-50 border-slate-200 text-slate-900 placeholder:text-slate-400 focus:border-blue-400";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className={`relative w-[480px] rounded-2xl border shadow-2xl p-6 ${base}`}>
        {/* 닫기 */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-200 transition-colors"
        >
          <X size={18} />
        </button>

        {/* 헤더 */}
        <div className="mb-5">
          <p className={`text-xs font-bold uppercase tracking-widest mb-1 ${isDarkMode ? "text-blue-400" : "text-blue-600"}`}>
            담당자에게 연락 · {DOMAIN_LABEL[domain] || domain}
          </p>
          <h2 className="text-[15px] font-semibold leading-snug">
            {question}
          </h2>
        </div>

        {sent ? (
          <div className="py-8 text-center">
            <div className="text-2xl mb-2">✓</div>
            <p className={`text-sm font-medium ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>쪽지를 보냈습니다.</p>
          </div>
        ) : (
          <>
            {/* 수신자 선택 */}
            <div className="mb-4">
              <label className={`block text-xs font-semibold mb-2 ${isDarkMode ? "text-slate-400" : "text-slate-600"}`}>
                수신자
              </label>
              {members.length === 0 ? (
                <p className={`text-xs ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>
                  해당 도메인 담당자가 없습니다. (팀에 {DOMAIN_LABEL[domain]} 역할 멤버를 초대하세요)
                </p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {members.map((m) => (
                    <button
                      key={m.id}
                      onClick={() => setSelectedId(m.id)}
                      className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-sm font-medium transition-all ${
                        selectedId === m.id
                          ? "border-blue-500 bg-blue-500/10 text-blue-400"
                          : isDarkMode
                            ? "border-white/[0.08] hover:border-white/20 text-slate-300"
                            : "border-slate-200 hover:border-slate-300 text-slate-700"
                      }`}
                    >
                      <User size={13} />
                      <span>{m.name || m.email}</span>
                      <span className={`text-[10px] uppercase tracking-wide ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>
                        {m.role}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* 메시지 */}
            <div className="mb-4">
              <label className={`block text-xs font-semibold mb-2 ${isDarkMode ? "text-slate-400" : "text-slate-600"}`}>
                메시지
              </label>
              <textarea
                rows={4}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="추가 내용을 입력하세요..."
                className={`w-full rounded-xl border px-3.5 py-2.5 text-sm resize-none focus:outline-none transition-colors ${inputCls}`}
              />
            </div>

            {error && (
              <p className="text-xs text-red-400 mb-3">{error}</p>
            )}

            <button
              onClick={handleSend}
              disabled={!selectedId || !message.trim() || sending}
              className={`w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-bold transition-all ${
                !selectedId || !message.trim() || sending
                  ? "opacity-40 cursor-not-allowed bg-blue-600/40 text-white"
                  : "bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/20"
              }`}
            >
              <Send size={14} />
              {sending ? "전송 중..." : "쪽지 보내기"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
