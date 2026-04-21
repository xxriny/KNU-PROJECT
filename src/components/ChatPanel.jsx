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
  const [chatMode, setChatMode] = useState("chat");

  // 새 메시지 시 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  useEffect(() => {
    if (!resultData) {
      setChatMode("chat");
    }
  }, [resultData]);

  const handleSend = () => {
    const text = chatInput.trim();
    if (!text) return;

    addChatMessage("user", text);
    setChatInput("");

    if (resultData && chatMode === "apply") {
      startRevision(text, apiKey, model);
    } else {
      sendIdeaChat(text, apiKey, model);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={`h-full min-h-0 flex flex-col min-w-0 overflow-hidden text-[15px] bg-transparent transition-colors duration-300`}>
      {/* ── 헤더 ──────────────────────────── */}
      <div className={`flex items-center justify-between px-4 py-3 border-b ${isDarkMode ? "border-slate-700/50" : "border-slate-200 bg-slate-50"}`}>
        <div className="flex items-center gap-2">
          <MessageSquare size={14} className="text-blue-400" />
          <span className="text-[15px] font-medium text-slate-300">AI 채팅</span>
        </div>
        <div className="flex items-center gap-2">
          {resultData && (
            <div className="flex items-center rounded-md border border-slate-700 bg-slate-800/70 p-0.5">
              <button
                onClick={() => setChatMode("chat")}
                className={`px-2 py-1 text-[12px] rounded ${
                  chatMode === "chat"
                    ? "bg-blue-600/20 text-blue-300"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                채팅
              </button>
              <button
                onClick={() => setChatMode("apply")}
                className={`px-2 py-1 text-[12px] rounded ${
                  chatMode === "apply"
                    ? "bg-amber-600/20 text-amber-300"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                적용
              </button>
            </div>
          )}
          {chatHistory.length > 0 && (
            <button
              onClick={clearChat}
              className="p-1 text-slate-500 hover:text-red-400 transition-colors"
              title="대화 초기화"
            >
              <Trash2 size={13} />
            </button>
          )}
        </div>
      </div>

      {/* ── 메시지 영역 ───────────────────── */}
      <div className={`flex-1 min-h-0 px-3 py-3 space-y-3 ${chatHistory.length === 0 ? "overflow-hidden" : "overflow-y-auto"}`}>
        {chatHistory.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Bot size={32} className="text-slate-600 mb-3" />
            <p className="text-[14px] text-slate-500 leading-relaxed">
              {resultData
                ? chatMode === "apply"
                  ? "적용 모드입니다\n명시적 수정 요청만 반영합니다"
                  : "분석 결과를 바탕으로\n질문하거나 방향을 정리하세요"
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

      {/* ── 입력 영역 ─────────────────────── */}
      <div className="p-3 border-t border-slate-700/50">
        <div className="relative">
          <textarea
            ref={inputRef}
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              resultData && chatMode === "apply"
                ? "반영할 수정 요청을 입력하세요..."
                : "메시지를 입력하세요..."
            }
            rows={2}
            disabled={pipelineStatus === "running"}
            className={`w-full px-3 py-2 pr-10 text-[15px] border rounded-lg resize-none focus:outline-none focus:border-blue-500 disabled:opacity-50 transition-colors ${
              isDarkMode 
                ? "bg-slate-800 border-slate-700 text-slate-300 placeholder-slate-600" 
                : "bg-slate-50 border-slate-200 text-slate-900 placeholder-slate-400"
            }`}
          />
          <button
            onClick={handleSend}
            disabled={!chatInput.trim() || pipelineStatus === "running"}
            className="absolute right-2 bottom-2 p-1.5 rounded-md bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <Send size={12} />
          </button>
        </div>
      </div>
    </div>
  );
}

function ChatMessage({ message }) {
  const isUser = message.role === "user";
  const { isDarkMode } = useAppStore();

  return (
    <div className={`flex gap-2 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className={`flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center ${
          isUser ? "bg-blue-600" : (isDarkMode ? "bg-slate-700" : "bg-slate-200")
        }`}
      >
        {isUser ? (
          <User size={12} className="text-white" />
        ) : (
          <Bot size={12} className={isDarkMode ? "text-blue-300" : "text-blue-600"} />
        )}
      </div>
      <div
        className={`max-w-[85%] px-3 py-2 rounded-lg text-[14px] leading-relaxed ${
          isUser
            ? isDarkMode 
                ? "bg-blue-600/20 text-blue-100 rounded-tr-sm" 
                : "bg-blue-50 text-blue-900 border border-blue-100 rounded-tr-sm"
            : isDarkMode
                ? "bg-slate-800 text-slate-300 rounded-tl-sm"
                : "bg-slate-100 text-slate-800 rounded-tl-sm"
        }`}
      >
        <div className="whitespace-pre-wrap">{message.content}</div>
      </div>
    </div>
  );
}
