import React from "react";
import { Bot, User } from "lucide-react";
import useAppStore from "../../store/useAppStore";

export default function ChatMessage({ message }) {
  const isUser = message.role === "user";
  const { isDarkMode } = useAppStore();

  const renderMarkdown = (text) => {
    if (!text) return null;
    const lines = text.split("\n");
    return lines.map((line, lineIdx) => {
      const isBulletList = line.trim().startsWith("- ") || line.trim().startsWith("* ");
      const isOrderedList = /^\d+\.\s/.test(line.trim());
      
      let content = line;
      if (isBulletList) {
        content = line.trim().replace(/^[-*]\s+/, "");
      } else if (isOrderedList) {
        content = line.trim().replace(/^\d+\.\s+/, "");
      }

      const parts = content.split(/(\*\*.*?\*\*|`.*?`)/g);
      const parsedLine = parts.map((part, partIdx) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return (
            <strong key={partIdx} className="font-extrabold text-blue-400">
              {part.slice(2, -2)}
            </strong>
          );
        }
        if (part.startsWith("`") && part.endsWith("`")) {
          return (
            <code
              key={partIdx}
              className="px-1.5 py-0.5 rounded bg-black/40 text-pink-400 font-mono text-[12px] border border-white/5"
            >
              {part.slice(1, -1)}
            </code>
          );
        }
        return part;
      });

      if (isBulletList) {
        return (
          <li key={lineIdx} className="ml-5 list-disc mb-1.5 pl-1 text-[13.5px]">
            {parsedLine}
          </li>
        );
      }
      if (isOrderedList) {
        const match = line.trim().match(/^(\d+)\.\s+/);
        const num = match ? match[1] : "1";
        return (
          <li key={lineIdx} className="ml-5 list-decimal mb-1.5 pl-1 text-[13.5px]" value={num}>
            {parsedLine}
          </li>
        );
      }

      if (!line.trim()) {
        return <div key={lineIdx} className="h-3" />;
      }

      return (
        <p key={lineIdx} className="mb-2 last:mb-0">
          {parsedLine}
        </p>
      );
    });
  };

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
        <div>{renderMarkdown(message.content)}</div>
      </div>
    </div>
  );
}
