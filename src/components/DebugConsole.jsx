import React, { useState } from "react";
import useAppStore from "../store/useAppStore";
import { X, Bug, Trash2, AlertCircle, ChevronDown, ChevronRight, Copy } from "lucide-react";
import Card from "./ui/Card";
import Button from "./ui/Button";
import Badge from "./ui/Badge";
import ScrollArea from "./ui/ScrollArea";

export default function DebugConsole({ isOpen, onClose }) {
  const { debugLogs, clearDebugLogs, isDarkMode, addNotification } = useAppStore();
  const [expandedIdx, setExpandedIdx] = useState(null);

  if (!isOpen) return null;

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(JSON.stringify(text, null, 2));
    addNotification("원본 데이터가 클립보드에 복사되었습니다.", "success");
  };

  return (
    <Card 
      variant="solid" 
      noPadding 
      className="fixed bottom-14 right-4 w-96 max-h-[500px] flex flex-col shadow-2xl z-[9999] animate-fade-in animate-slide-up"
    >
      {/* Header */}
      <div className={`px-4 py-3 border-b flex items-center justify-between shrink-0 ${
        isDarkMode ? "bg-slate-800/50 border-slate-700" : "bg-slate-50 border-slate-200"
      }`}>
        <div className="flex items-center gap-2">
          <Bug size={16} className="text-blue-500" />
          <span className={`text-sm font-bold ${isDarkMode ? "text-slate-200" : "text-slate-700"}`}>
            Debug Console
          </span>
          <Badge variant="default" className="ml-1">{debugLogs.length}</Badge>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" onClick={clearDebugLogs} title="Clear all logs" className="h-8 w-8 !p-0">
            <Trash2 size={14} className="text-red-400" />
          </Button>
          <Button variant="ghost" size="sm" onClick={onClose} className="h-8 w-8 !p-0">
            <X size={16} />
          </Button>
        </div>
      </div>

      {/* Log List */}
      <ScrollArea className="flex-1 p-2 space-y-2">
        {debugLogs.length === 0 ? (
          <div className="h-40 flex flex-col items-center justify-center text-slate-500 space-y-2">
            <AlertCircle size={24} className="opacity-20" />
            <p className="text-sm">No issues detected</p>
          </div>
        ) : (
          debugLogs.map((log, idx) => (
            <Card 
              key={idx}
              variant={isDarkMode ? "solid" : "glass"}
              noPadding
              className={`border transition-all overflow-hidden ${isDarkMode ? "border-slate-800" : "border-slate-100"}`}
            >
              <div 
                className="p-3 cursor-pointer flex items-center gap-2"
                onClick={() => setExpandedIdx(expandedIdx === idx ? null : idx)}
              >
                {expandedIdx === idx ? <ChevronDown size={14} className="text-slate-500" /> : <ChevronRight size={14} className="text-slate-500" />}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-0.5">
                    <Badge variant={log.level === "error" ? "error" : "warning"}>{log.level}</Badge>
                    <span className="text-[10px] text-slate-500 font-medium">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className={`text-[13px] font-semibold truncate ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>
                    {log.message}
                  </p>
                </div>
              </div>

              {expandedIdx === idx && (
                <div className={`px-3 pb-3 border-t ${isDarkMode ? "border-slate-800" : "border-slate-100"}`}>
                  <div className="mt-2 flex items-center justify-between mb-2">
                    <span className="text-[11px] text-slate-500 font-bold uppercase tracking-tight">Raw Data</span>
                    <Button variant="outline" size="sm" onClick={() => copyToClipboard(log.rawData)} className="h-6 py-0 px-2 text-[10px]">
                      <Copy size={10} className="mr-1" /> Copy
                    </Button>
                  </div>
                  <pre className={`text-[11px] font-mono p-3 rounded-xl max-h-40 overflow-auto custom-scrollbar ${
                    isDarkMode ? "bg-black/40 text-blue-300" : "bg-slate-900 text-blue-400"
                  }`}>
                    {JSON.stringify(log.rawData, null, 2)}
                  </pre>
                </div>
              )}
            </Card>
          ))
        )}
      </ScrollArea>
    </Card>
  );
}
