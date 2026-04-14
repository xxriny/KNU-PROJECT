import React, { useState } from "react";
import useAppStore from "../store/useAppStore";
import { X, Bug, Trash2, AlertCircle, ChevronDown, ChevronRight, Copy } from "lucide-react";

export default function DebugConsole({ isOpen, onClose }) {
  const { debugLogs, clearDebugLogs, isDarkMode } = useAppStore();
  const [expandedIdx, setExpandedIdx] = useState(null);

  if (!isOpen) return null;

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(JSON.stringify(text, null, 2));
    alert("Raw data copied to clipboard!");
  };

  return (
    <div className={`fixed bottom-12 right-4 w-96 max-h-[500px] flex flex-col rounded-xl border shadow-2xl z-[9999] transition-all overflow-hidden ${
      isDarkMode ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"
    }`}>
      {/* Header */}
      <div className={`px-4 py-3 border-b flex items-center justify-between ${
        isDarkMode ? "bg-slate-800/50 border-slate-700" : "bg-slate-50 border-slate-200"
      }`}>
        <div className="flex items-center gap-2">
          <Bug size={16} className="text-blue-500" />
          <span className={`text-sm font-bold ${isDarkMode ? "text-slate-200" : "text-slate-700"}`}>
            Debug Console
          </span>
          <span className="ml-1 text-[11px] bg-slate-500/20 text-slate-500 px-1.5 rounded-full">
            {debugLogs.length}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button 
            onClick={clearDebugLogs}
            className={`p-1.5 rounded-md hover:bg-red-500/10 hover:text-red-500 transition-colors ${
              isDarkMode ? "text-slate-500" : "text-slate-400"
            }`}
            title="Clear all logs"
          >
            <Trash2 size={14} />
          </button>
          <button 
            onClick={onClose}
            className={`p-1.5 rounded-md transition-colors ${
              isDarkMode ? "text-slate-500 hover:bg-slate-700" : "text-slate-400 hover:bg-slate-200"
            }`}
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Log List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {debugLogs.length === 0 ? (
          <div className="h-40 flex flex-col items-center justify-center text-slate-500 space-y-2">
            <AlertCircle size={24} className="opacity-20" />
            <p className="text-sm">No issues detected</p>
          </div>
        ) : (
          debugLogs.map((log, idx) => (
            <div 
              key={idx}
              className={`rounded-lg border transition-all overflow-hidden ${
                isDarkMode ? "border-slate-800 bg-slate-800/30" : "border-slate-100 bg-slate-50/50"
              }`}
            >
              <div 
                className="p-3 cursor-pointer flex items-center gap-2"
                onClick={() => setExpandedIdx(expandedIdx === idx ? null : idx)}
              >
                {expandedIdx === idx ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-mono font-bold text-red-500 uppercase tracking-tighter">
                      {log.level}
                    </span>
                    <span className="text-[10px] text-slate-500">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className={`text-[13px] font-medium truncate ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>
                    {log.message}
                  </p>
                </div>
              </div>

              {expandedIdx === idx && (
                <div className={`px-3 pb-3 border-t ${isDarkMode ? "border-slate-800" : "border-slate-100"}`}>
                  <div className="mt-2 flex items-center justify-between mb-1">
                    <span className="text-[11px] text-slate-500 font-medium">Raw Data:</span>
                    <button 
                      onClick={() => copyToClipboard(log.rawData)}
                      className="flex items-center gap-1 text-[10px] bg-blue-500/10 text-blue-500 px-1.5 py-0.5 rounded hover:bg-blue-500/20"
                    >
                      <Copy size={10} /> Copy
                    </button>
                  </div>
                  <pre className={`text-[11px] font-mono p-2 rounded max-h-40 overflow-auto ${
                    isDarkMode ? "bg-black/40 text-blue-300" : "bg-white text-blue-600 border"
                  }`}>
                    {JSON.stringify(log.rawData, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
