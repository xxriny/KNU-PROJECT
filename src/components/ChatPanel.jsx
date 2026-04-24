import React from "react";
import useAppStore from "../store/useAppStore";
import useChat from "../hooks/useChat";
import { Bot } from "lucide-react";
import ScrollArea from "./ui/ScrollArea";
import ChatMessage from "./chat/ChatMessage";
import ChatInput from "./chat/ChatInput";

/**
 * ChatPanel — 우측 AI 채팅 패널
 */
export default function ChatPanel() {
  const { resultData } = useAppStore();
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
