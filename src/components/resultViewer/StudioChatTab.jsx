import React from "react";
import ChatPanel from "../ChatPanel";
import useAppStore from "../../store/useAppStore";
import { MessageSquare, X } from "lucide-react";

export default function FullChatTab() {
  const { activateOutputTab, isDarkMode } = useAppStore();

  const containerStyle = isDarkMode ? "h-full flex flex-col bg-slate-900" : "h-full flex flex-col bg-white";
  const headerStyle = isDarkMode 
    ? "shrink-0 p-4 border-b flex items-center justify-between border-white/5 bg-white/5" 
    : "shrink-0 p-4 border-b flex items-center justify-between border-slate-200 bg-slate-50";
  const titleStyle = isDarkMode ? "text-sm font-black flex items-center gap-2 text-slate-200" : "text-sm font-black flex items-center gap-2 text-slate-800";

  return (
    <div className={containerStyle}>
      <div className={headerStyle}>
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold opacity-50 uppercase tracking-tighter text-slate-500">Studio &gt;</span>
          <span className={titleStyle}>
            <MessageSquare size={14} className="text-purple-400" />
            AI Assistant Chat
          </span>
        </div>
        <button 
          onClick={() => activateOutputTab("overview")}
          className="p-1.5 rounded-lg hover:bg-white/10 transition-colors opacity-50 hover:opacity-100"
        >
          <X size={18} />
        </button>
      </div>

      <div className="flex-1 min-h-0 max-w-4xl mx-auto w-full border-x border-white/5 shadow-2xl bg-black/5">
        <ChatPanel isFullView={true} />
      </div>
    </div>
  );
}
