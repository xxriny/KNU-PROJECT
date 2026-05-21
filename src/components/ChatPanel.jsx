import React from "react";
import useAppStore from "../store/useAppStore";
import useChat from "../hooks/useChat";
import { Bot, Loader2 } from "lucide-react";
import ScrollArea from "./ui/ScrollArea";
import ChatMessage from "./chat/ChatMessage";
import ChatInput from "./chat/ChatInput";

/**
 * ChatPanel — 우측 AI 채팅 패널
 */
export default function ChatPanel() {
  const { resultData, isDarkMode, pipelineType } = useAppStore();
  const {
    chatHistory,
    chatInput,
    setChatInput,
    handleSend,
    handleKeyDown,
    messagesEndRef,
    inputRef,
    isProcessing
  } = useChat();

  // 분석 진행 상황별 안내 문구
  // memo 반영 UPDATE / 일반 UPDATE / CREATE / REVERSE 모두 pipelineStatus="running"이 됨
  const processingMessage = (() => {
    if (pipelineType === "analysis_update") return "메모/요청을 반영해 분석을 업데이트 중입니다. 잠시만 기다려주세요.";
    if (pipelineType === "analysis_reverse") return "기존 코드베이스를 역공학 분석 중입니다. 잠시만 기다려주세요.";
    if (pipelineType === "analysis_create") return "신규 프로젝트를 분석 중입니다. 잠시만 기다려주세요.";
    return "현재 프로젝트 분석 중입니다. 잠시만 기다려주세요.";
  })();

  return (
    <div className="h-full min-h-0 flex flex-col min-w-0 overflow-hidden bg-transparent">
      {/* Messages Area */}
      <ScrollArea className="flex-1 px-3 py-3 space-y-1">
        {chatHistory.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center p-6 animate-fade-in">
            <div className="w-16 h-16 bg-blue-500/10 rounded-3xl flex items-center justify-center mb-6 shadow-glow">
              <Bot size={32} className="text-blue-500" />
            </div>
            <h3 className="text-lg font-black text-slate-400 mb-2 tracking-tight">AI Navigator</h3>
            <p className="text-[14px] text-slate-500 leading-relaxed whitespace-pre-wrap font-medium">
              {resultData
                ? "분석 결과를 바탕으로\n질문하거나 방향을 정리하세요"
                : "아이디어를 자유롭게\n이야기해 보세요"}
            </p>
          </div>
        ) : (
          <div className="space-y-4 pb-4">
            {chatHistory.map((msg, idx) => (
              <ChatMessage key={idx} message={msg} />
            ))}
          </div>
        )}
        <div ref={messagesEndRef} className="h-1" />
      </ScrollArea>

      {/* 분석 진행 중 안내 배너 */}
      {isProcessing && (
        <div
          className={`mx-4 mb-2 px-4 py-3 rounded-2xl flex items-center gap-3 border animate-fade-in ${
            isDarkMode
              ? "bg-blue-500/10 border-blue-500/30 text-blue-300"
              : "bg-blue-50 border-blue-200 text-blue-700"
          }`}
          role="status"
          aria-live="polite"
        >
          <Loader2 size={16} className="shrink-0 animate-spin text-blue-500" />
          <span className="text-[13px] font-medium leading-snug">
            {processingMessage}
          </span>
        </div>
      )}

      {/* Input Area */}
      <ChatInput
        value={chatInput}
        onChange={setChatInput}
        onSend={handleSend}
        onKeyDown={handleKeyDown}
        inputRef={inputRef}
        isProcessing={isProcessing}
      />
    </div>
  );
}
