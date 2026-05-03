import React from "react";
import { Send } from "lucide-react";
import useAppStore from "../../store/useAppStore";

export default function ChatInput({ 
  value, 
  onChange, 
  onSend, 
  onKeyDown, 
  inputRef, 
  isProcessing 
}) {
  const { isDarkMode } = useAppStore();

  return (
    <div className="px-4 pb-6 pt-0 shrink-0">
      <div className={`
        w-full relative rounded-3xl shadow-2xl flex items-end border transition-all p-1.5 pl-6
        ${isDarkMode 
          ? "bg-slate-800 border-white/5 shadow-[0_10px_40px_rgba(0,0,0,0.5)]" 
          : "bg-white border-slate-200 shadow-[0_10px_30px_rgba(0,0,0,0.1)]"
        }
      `}>
        <div className="flex-1 mb-1">
          <textarea
            ref={inputRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder="메시지를 입력하세요..."
            disabled={isProcessing}
            className={`
              w-full bg-transparent border-none focus:outline-none focus:ring-0 text-[14px] py-2 resize-none scrollbar-hide placeholder:text-slate-500 disabled:opacity-50 leading-snug
              ${isDarkMode ? "text-slate-100" : "text-slate-800"}
            `}
          />
        </div>

        <div className="flex items-center shrink-0 ml-1">
          <button
            onClick={onSend}
            disabled={!value.trim() || isProcessing}
            className={`
              w-9 h-9 flex items-center justify-center rounded-full transition-all duration-300
              ${value.trim() && !isProcessing
                ? "bg-blue-600 text-white hover:bg-blue-500 shadow-lg active:scale-90"
                : "bg-white/5 text-slate-500 cursor-not-allowed grayscale"
              }
            `}
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
