import React, { useState, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import useAppStore from "../../store/useAppStore";
import { serverRequest } from "../../api/serverClient";
import { Plus, FolderPlus, Clock3, Edit3, Trash2, RefreshCw, Sparkles, Moon, Sun, MoreHorizontal, X, Inbox } from "lucide-react";

export default function LeftSidebar() {
  const {
    sessions,
    currentSessionId,
    loadSession,
    deleteSession,
    updateSessionName,
    restoreSessionFromRag,
    isDarkMode,
    toggleDarkMode,
    currentUser,
    startNewProject,
    chatHistory
  } = useAppStore();

  const teamId = currentUser?.team_id || null;
  const teamName = currentUser?.team_name || "팀 없음";
  const userRole = currentUser?.role === "pm" ? "Project Manager" : "팀원";

  // Filter sessions by active team
  const visibleSessions = teamId
    ? sessions.filter((s) => !s.team_id || s.team_id === teamId)
    : sessions;

  const [editingSession, setEditingSession] = useState(null);
  const [editValue, setEditValue] = useState("");
  const [confirmReset, setConfirmReset] = useState(false);
  const [activeDropdown, setActiveDropdown] = useState(null);
  const [dropdownPos, setDropdownPos] = useState({ top: 0, left: 0 });
  const [showInbox, setShowInbox] = useState(false);
  const [inboxMessages, setInboxMessages] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);

  const authToken = useAppStore((s) => s.authToken);

  const fetchInbox = useCallback(async () => {
    if (!authToken) return;
    try {
      const data = await serverRequest("/messages/inbox", {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      const msgs = data.messages || [];
      setInboxMessages(msgs);
      setUnreadCount(msgs.filter((m) => !m.is_read).length);
    } catch (_) {}
  }, [authToken]);

  const markRead = useCallback(async (id) => {
    if (!authToken) return;
    try {
      await serverRequest(`/messages/${id}/read`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${authToken}` },
      });
      setInboxMessages((prev) => prev.map((m) => m.id === id ? { ...m, is_read: true } : m));
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch (_) {}
  }, [authToken]);

  useEffect(() => {
    fetchInbox();
    const timer = setInterval(fetchInbox, 30000);
    return () => clearInterval(timer);
  }, [fetchInbox]);

  useEffect(() => {
    const handleClickOutside = () => setActiveDropdown(null);
    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, []);

  const hasWork = (chatHistory || []).length > 0;

  const handleNewProjectClick = () => {
    if (!hasWork) {
      startNewProject();
      return;
    }
    setConfirmReset(true);
  };

  const handleConfirmReset = () => {
    setConfirmReset(false);
    startNewProject();
  };

  const handleStartEdit = (e, session) => {
    e.stopPropagation();
    setEditingSession(session);
    setEditValue(session.name);
  };

  const handleSaveEdit = () => {
    if (editValue.trim() && editingSession) {
      updateSessionName(editingSession.id, editValue.trim());
    }
    setEditingSession(null);
  };

  return (
    <div
      className={`w-60 h-full flex flex-col shrink-0 border-r transition-all duration-300 relative z-10 ${
        isDarkMode
          ? "bg-[#0b0e14]/90 border-white/[0.05] text-slate-200"
          : "bg-slate-50/90 border-slate-200 text-slate-800"
      }`}
    >
      {/* Top Header Team Name */}
      <div className={`h-14 flex items-center px-5 border-b shrink-0 ${
        isDarkMode ? "border-white/[0.05]" : "border-slate-200"
      }`}>
        <div className="flex items-center gap-3 w-full">
          {/* Elegant geometric avatar representing the workspace/team */}
          <div className="w-8 h-8 rounded-xl flex items-center justify-center font-display font-black text-xs text-white shadow-[0_2px_8px_rgba(99,102,241,0.3)] bg-gradient-to-tr from-blue-500 via-indigo-500 to-purple-600 shrink-0 select-none">
            {teamName.charAt(0).toUpperCase()}
          </div>
          <div className="flex flex-col min-w-0">
            <span className={`text-[13px] font-bold tracking-tight truncate leading-none mb-1 ${isDarkMode ? "text-slate-100" : "text-slate-900"}`}>
              {teamName}
            </span>
            <span className={`text-[9px] font-semibold tracking-wider uppercase leading-none opacity-50 ${isDarkMode ? "text-indigo-400" : "text-indigo-600"}`}>
              Active Workspace
            </span>
          </div>
        </div>
      </div>

      {/* Sessions Title */}
      <div className="px-5 py-2 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-1.5 opacity-60">
          <Clock3 size={12} />
          <span className="text-[10px] font-black uppercase tracking-[0.15em]">대화 기록</span>
        </div>
        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-md ${
          isDarkMode ? "bg-white/5 text-slate-400" : "bg-slate-100 text-slate-500"
        }`}>
          {visibleSessions.length}
        </span>
      </div>

      {/* Session History List */}
      <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar px-3 py-1 space-y-1">
        {visibleSessions.length === 0 ? (
          <div className={`px-4 py-8 text-center text-xs italic ${
            isDarkMode ? "text-slate-600" : "text-slate-400"
          }`}>
            저장된 세션이 없습니다
          </div>
        ) : (
          visibleSessions.map((session) => {
            const isActive = currentSessionId === session.id;

            return (
              <div
                key={session.id}
                onClick={() => loadSession(session.id)}
                className={`group rounded-xl p-2.5 transition-all relative border cursor-pointer ${
                  isActive
                    ? isDarkMode
                      ? "bg-white/[0.04] border-white/10 shadow-sm"
                      : "bg-white border-slate-200 shadow-sm"
                    : "border-transparent hover:bg-white/[0.02] hover:scale-[1.01]"
                }`}
              >
                <div className="flex items-center gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 justify-between">
                      <p className={`text-[13px] font-bold truncate pr-4 ${
                        isActive 
                          ? isDarkMode ? "text-blue-400" : "text-blue-600" 
                          : isDarkMode ? "text-slate-300" : "text-slate-700"
                      }`}>
                        {session.name}
                      </p>
                    </div>
                    <p className={`text-[9px] mt-0.5 ${
                      isDarkMode ? "text-slate-600" : "text-slate-400"
                    }`}>
                      {new Date(session.createdAt).toLocaleDateString("ko", {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit"
                      })}
                    </p>
                  </div>

                  {/* Actions on Hover */}
                  <div className="flex items-center absolute right-2 top-1/2 -translate-y-1/2">
                    <div className="relative">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            if (activeDropdown === session.id) {
                              setActiveDropdown(null);
                            } else {
                              const rect = e.currentTarget.getBoundingClientRect();
                              setDropdownPos({
                                top: rect.top,
                                left: rect.right + 8
                              });
                              setActiveDropdown(session.id);
                            }
                          }}
                          className={`p-1 rounded-md transition-colors opacity-0 group-hover:opacity-100 ${
                            isDarkMode ? "hover:bg-white/5 text-slate-400 hover:text-white" : "hover:bg-slate-100 text-slate-500 hover:text-slate-900"
                          } ${activeDropdown === session.id ? "!opacity-100" : ""}`}
                        >
                          <MoreHorizontal size={14} />
                        </button>
                        
                        {activeDropdown === session.id && createPortal(
                          <div 
                            className={`fixed w-32 py-1 rounded-xl shadow-[0_4px_24px_rgba(0,0,0,0.2)] border z-[9999] animate-fade-in ${
                              isDarkMode ? "bg-[#1c212c] border-white/10" : "bg-white border-slate-200"
                            }`}
                            style={{ top: dropdownPos.top, left: dropdownPos.left }}
                            onClick={(e) => e.stopPropagation()}
                          >
                            <button
                              onClick={(e) => {
                                handleStartEdit(e, session);
                                setActiveDropdown(null);
                              }}
                              className={`w-full text-left px-3 py-2 text-xs flex items-center gap-2 transition-colors ${
                                isDarkMode ? "hover:bg-white/5 text-slate-300" : "hover:bg-slate-50 text-slate-700"
                              }`}
                            >
                              <Edit3 size={13} className="opacity-70" />
                              <span>이름 바꾸기</span>
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                deleteSession(session.id);
                                setActiveDropdown(null);
                              }}
                              className={`w-full text-left px-3 py-2 text-xs flex items-center gap-2 transition-colors ${
                                isDarkMode ? "hover:bg-red-500/10 text-red-400" : "hover:bg-red-50 text-red-500"
                              }`}
                            >
                              <Trash2 size={13} className="opacity-70" />
                              <span>삭제</span>
                            </button>
                          </div>,
                          document.body
                        )}
                      </div>
                    </div>
                </div>
              </div>
            );
          })
        )}
      </div>
      {/* Bottom Actions */}
      <div className={`p-4 border-t shrink-0 flex flex-col gap-2 ${
        isDarkMode ? "border-white/[0.05]" : "border-slate-200"
      }`}>
        {/* 수신함 버튼 */}
        <button
          onClick={() => { setShowInbox((v) => !v); fetchInbox(); }}
          className={`w-full flex items-center gap-2 px-3 py-2 rounded-xl text-[12px] font-semibold transition-all relative ${
            showInbox
              ? isDarkMode ? "bg-white/10 text-slate-200" : "bg-slate-100 text-slate-800"
              : isDarkMode ? "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200" : "text-slate-500 hover:bg-slate-100 hover:text-slate-700"
          }`}
        >
          <Inbox size={14} />
          <span>수신함</span>
          {unreadCount > 0 && (
            <span className="ml-auto min-w-[18px] h-[18px] flex items-center justify-center rounded-full bg-blue-500 text-white text-[10px] font-black px-1">
              {unreadCount > 99 ? "99+" : unreadCount}
            </span>
          )}
        </button>
        <button
          onClick={handleNewProjectClick}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-[13px] font-bold transition-all bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white shadow-lg shadow-blue-500/20 active:scale-[0.98]"
        >
          <Plus size={15} strokeWidth={2.5} />
          <span>신규 분석 시작</span>
        </button>
      </div>

      {/* 수신함 패널 (인라인 슬라이드) */}
      {showInbox && (
        <div className={`absolute bottom-[108px] left-0 w-full border-t z-20 max-h-[55vh] overflow-y-auto ${
          isDarkMode ? "bg-[#0b0e14]/95 border-white/[0.05]" : "bg-slate-50/95 border-slate-200"
        }`}>
          <div className={`px-4 py-2.5 flex items-center justify-between border-b ${
            isDarkMode ? "border-white/[0.05]" : "border-slate-200"
          }`}>
            <span className={`text-[11px] font-black uppercase tracking-widest ${isDarkMode ? "text-slate-400" : "text-slate-500"}`}>
              수신함
            </span>
            <button onClick={() => setShowInbox(false)} className="text-slate-500 hover:text-slate-300">
              <X size={13} />
            </button>
          </div>
          {inboxMessages.length === 0 ? (
            <p className={`text-center py-6 text-[12px] ${isDarkMode ? "text-slate-600" : "text-slate-400"}`}>
              받은 쪽지가 없습니다.
            </p>
          ) : (
            inboxMessages.map((msg) => (
              <div
                key={msg.id}
                onClick={() => !msg.is_read && markRead(msg.id)}
                className={`px-4 py-3 border-b cursor-pointer transition-colors ${
                  isDarkMode ? "border-white/[0.04]" : "border-slate-100"
                } ${
                  msg.is_read
                    ? isDarkMode ? "opacity-50" : "opacity-60"
                    : isDarkMode ? "hover:bg-white/[0.03]" : "hover:bg-slate-100"
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  {!msg.is_read && <span className="w-1.5 h-1.5 rounded-full bg-blue-400 shrink-0" />}
                  <span className={`text-[11px] font-bold ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>
                    {msg.sender_name}
                  </span>
                  <span className={`text-[10px] ml-auto ${isDarkMode ? "text-slate-600" : "text-slate-400"}`}>
                    {msg.created_at ? new Date(msg.created_at).toLocaleDateString("ko", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : ""}
                  </span>
                </div>
                {msg.context_question && (
                  <p className={`text-[10px] mb-1 px-2 py-1 rounded-md ${isDarkMode ? "bg-white/[0.04] text-slate-500" : "bg-slate-100 text-slate-500"}`}>
                    ↳ {msg.context_question}
                  </p>
                )}
                <p className={`text-[12px] leading-relaxed ${isDarkMode ? "text-slate-400" : "text-slate-600"}`}>
                  {msg.content}
                </p>
              </div>
            ))
          )}
        </div>
      )}

      {/* Reset Confirmation Modal */}
      {confirmReset && createPortal(
        <div
          className="fixed inset-0 z-[9999] flex items-center justify-center animate-fade-in"
          style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(6px)" }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setConfirmReset(false);
          }}
        >
          <div
            className={`w-[360px] rounded-2xl shadow-2xl p-5 border animate-scale-in ${
              isDarkMode
                ? "bg-[#141822] border-white/10 text-slate-200"
                : "bg-white border-slate-200 text-slate-800"
            }`}
          >
            <h3 className="text-sm font-black mb-2 flex items-center gap-2">
              <Sparkles size={16} className="text-blue-500" />
              <span>새 프로젝트 시작</span>
            </h3>
            <p className="text-[12px] leading-relaxed opacity-80 mb-4">
              진행 중인 모든 대화와 스냅샷이 초기화됩니다. 이 대화는 <strong>대화 기록</strong>에서 다시 불러올 수 있습니다. 계속할까요?
            </p>
            <div className="flex justify-end gap-2 text-xs">
              <button
                onClick={() => setConfirmReset(false)}
                className={`px-3 py-1.5 rounded-xl font-semibold transition-colors ${
                  isDarkMode ? "bg-white/5 hover:bg-white/10" : "bg-slate-100 hover:bg-slate-200"
                }`}
              >
                취소
              </button>
              <button
                onClick={handleConfirmReset}
                className="px-3 py-1.5 rounded-xl font-semibold bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/20"
              >
                새 대화 시작
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* Rename Modal */}
      {editingSession && createPortal(
        <div
          className="fixed inset-0 z-[9999] flex items-center justify-center animate-fade-in"
          style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(6px)" }}
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setEditingSession(null);
          }}
        >
          <div
            className={`w-[400px] rounded-2xl shadow-2xl p-6 border animate-scale-in ${
              isDarkMode
                ? "bg-[#1c212c] border-white/10 text-slate-200"
                : "bg-white border-slate-200 text-slate-800"
            }`}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold">스레드 제목 편집</h3>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setEditingSession(null);
                }}
                className={`p-1 rounded-md transition-colors ${
                  isDarkMode ? "hover:bg-white/10 text-slate-400" : "hover:bg-slate-100 text-slate-500"
                }`}
              >
                <X size={16} />
              </button>
            </div>
            
            <input
              autoFocus
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleSaveEdit();
                if (e.key === "Escape") setEditingSession(null);
              }}
              className={`w-full border rounded-xl px-4 py-3 text-[14px] outline-none transition-colors mb-6 ${
                isDarkMode 
                  ? "bg-[#141822] border-white/10 focus:border-blue-500 text-white" 
                  : "bg-slate-50 border-slate-200 focus:border-blue-500 text-slate-900"
              }`}
            />
            
            <div className="flex justify-end gap-2 text-sm">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleSaveEdit();
                }}
                className={`px-5 py-2 rounded-xl font-bold transition-colors ${
                  isDarkMode 
                    ? "bg-slate-200 hover:bg-white text-slate-900" 
                    : "bg-slate-800 hover:bg-slate-900 text-white"
                }`}
              >
                저장
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
