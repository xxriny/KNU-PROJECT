/**
 * ChatPanel — 우측 패널
 * AI와의 채팅 인터페이스
 */

import React, { useRef, useEffect, useState } from "react";
import useAppStore from "../store/useAppStore";
import { Send, MessageSquare, Trash2, Bot, User } from "lucide-react";

export default function ChatPanel() {
  const {
    chatHistory,
    chatInput,
    setChatInput,
    startRevision,
    sendIdeaChat,
    addChatMessage,
    clearChat,
    resultData,
    pipelineStatus,
    apiKey,
    model,
    isDarkMode,
  } = useAppStore();

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // 새 메시지 시 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 150) + 'px';
    }
  }, [chatInput]);

  const handleSend = () => {
    const text = chatInput.trim();
    if (!text) return;

    addChatMessage("user", text);
    setChatInput("");
    sendIdeaChat(text, apiKey, model);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={`h-full min-h-0 flex flex-col min-w-0 overflow-hidden text-[16px] bg-transparent transition-colors duration-300`}>


      {/* ── 메시지 영역 ───────────────────── */}
      <div className={`flex-1 min-h-0 px-3 py-3 space-y-3 ${chatHistory.length === 0 ? "overflow-hidden" : "overflow-y-auto custom-scrollbar"}`}>
        {chatHistory.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Bot size={40} className="text-slate-600 mb-4" />
            <p className="text-[15px] text-slate-500 leading-relaxed whitespace-pre-wrap">
              {resultData
                ? "분석 결과를 바탕으로\n질문하거나 방향을 정리하세요"
                : "아이디어를 자유롭게\n이야기해 보세요"}
            </p>
          </div>
        ) : (
          chatHistory.map((msg, idx) => (
            <ChatMessage key={idx} message={msg} />
          ))
        )}
        <div ref={messagesEndRef} className="h-0" />
      </div>

      {/* ── 입력 영역 (진정한 Pill 스타일 적용 - 명도 상향) ─────────────────────── */}
      <div className="px-4 pb-6 pt-0">
        <div className={`w-full relative rounded-full shadow-2xl flex items-end border border-white/10 ${isDarkMode ? "bg-[#2D333B] shadow-[0_4px_20px_rgba(0,0,0,0.4)]" : "bg-white border-slate-200 shadow-lg"
          } p-1.5 pl-6`}>
          <div className="flex-1 mb-1">
            <textarea
              ref={inputRef}
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              placeholder="메시지를 입력하세요..."
              disabled={pipelineStatus === "running"}
              className="w-full bg-transparent border-none focus:outline-none focus:ring-0 text-[14px] py-2 resize-none scrollbar-hide placeholder:text-slate-400 disabled:opacity-50 text-slate-100 leading-snug"
            />
          </div>

          <div className="flex items-center shrink-0 ml-1">
            <button
              onClick={handleSend}
              disabled={!chatInput.trim() || pipelineStatus === "running"}
              className={`w-9 h-9 flex items-center justify-center rounded-full transition-all ${chatInput.trim() && pipelineStatus !== "running"
                  ? "bg-blue-600 text-white hover:bg-blue-500 shadow-md active:scale-90"
                  : "bg-white/10 text-slate-500 cursor-not-allowed"
                }`}
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ChatMessage({ message }) {
  const isUser = message.role === "user";
  const { isDarkMode } = useAppStore();

  return (
    <div className={`flex gap-3 mt-4 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${isUser ? "bg-blue-600" : (isDarkMode ? "bg-slate-700" : "bg-slate-200")
          }`}
      >
        {isUser ? (
          <User size={16} className="text-white" />
        ) : (
          <Bot size={16} className={isDarkMode ? "text-blue-300" : "text-blue-600"} />
        )}
      </div>
      <div
        className={`max-w-[85%] px-4 py-3 rounded-2xl text-[15px] leading-relaxed shadow-sm ${isUser
            ? isDarkMode
              ? "bg-blue-600/30 text-white border border-blue-500/20 rounded-tr-sm"
              : "bg-blue-50 text-blue-900 border border-blue-100 rounded-tr-sm"
            : isDarkMode
              ? "bg-white/5 text-slate-100 border border-white/10 rounded-tl-sm backdrop-blur-md"
              : "bg-slate-100 text-slate-800 rounded-tl-sm"
          }`}
      >
        <div className="whitespace-pre-wrap">{message.content}</div>
      </div>
    </div>
  );
}
