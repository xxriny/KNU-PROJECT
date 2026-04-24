import React from "react";
import { Bot, User } from "lucide-react";
import useAppStore from "../../store/useAppStore";

export default function ChatMessage({ message }) {
  const isUser = message.role === "user";
  const { isDarkMode } = useAppStore();

  return (
    <div className={`flex gap-3 mt-4 animate-fade-in animate-slide-up ${isUser ? "flex-row-reverse" : ""}`}>
      {/* Icon Area */}
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center shadow-sm ${
          isUser ? "bg-blue-600" : (isDarkMode ? "bg-slate-700" : "bg-slate-200")
        }`}
      >
        {isUser ? (
          <User size={16} className="text-white" />
        ) : (
          <Bot size={16} className={isDarkMode ? "text-blue-300" : "text-blue-600"} />
        )}
      </div>

      {/* Bubble Area */}
      <div
        className={`max-w-[85%] px-4 py-3 rounded-2xl text-[14px] leading-relaxed shadow-sm transition-all ${
          isUser
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
