import React, { useState, useEffect, useRef } from "react";
import useAppStore from "../../store/useAppStore";
import { Section, StatusBadge, EmptyState } from "./SharedComponents";
import { AlertTriangle, CheckCircle, Info, FileText, MessageSquarePlus, X } from "lucide-react";

function SAAnalysisTab() {
  const { sa_output, isDarkMode, addComment } = useAppStore();
  const [popover, setPopover] = useState({ visible: false, x: 0, y: 0, selectedText: "" });
  const [commentInput, setCommentInput] = useState("");
  const contentRef = useRef(null);

  useEffect(() => {
    const handleMouseUp = (e) => {
      if (e.target.closest('.comment-popover')) return;
      const selection = window.getSelection();
      const text = selection.toString().trim();
      if (text.length > 0 && contentRef.current?.contains(selection.anchorNode)) {
        const range = selection.getRangeAt(0);
        const rect = range.getBoundingClientRect();
        const containerRect = contentRef.current.getBoundingClientRect();
        setPopover({
          visible: true,
          x: rect.left - containerRect.left + (rect.width / 2),
          y: rect.bottom - containerRect.top + 10,
          selectedText: text,
        });
      } else {
        setPopover({ visible: false, x: 0, y: 0, selectedText: "" });
      }
    };
    document.addEventListener("mouseup", handleMouseUp);
    return () => document.removeEventListener("mouseup", handleMouseUp);
  }, []);

  const handleAddComment = () => {
    if (!commentInput.trim()) return;
    addComment({ text: commentInput, selectedText: popover.selectedText, section: "SA QA Report" });
    setCommentInput("");
    setPopover({ visible: false, x: 0, y: 0, selectedText: "" });
    window.getSelection()?.removeAllRanges();
  };

  if (!sa_output) {
    return <EmptyState text="SA 분석 데이터가 없습니다." />;
  }

  const { status, gaps, thinking, metadata } = sa_output;

  return (
    <div ref={contentRef} className="relative p-4 space-y-6 selectable">
      {popover.visible && (
        <div 
          className="comment-popover absolute z-50 p-3 rounded-xl shadow-2xl border flex flex-col gap-2 transform -translate-x-1/2"
          style={{ 
            left: popover.x, 
            top: popover.y,
            backgroundColor: isDarkMode ? "#1e293b" : "#ffffff",
            borderColor: isDarkMode ? "#334155" : "#e2e8f0",
            width: "300px"
          }}
        >
          <div className="text-xs font-bold text-slate-400 mb-1 line-clamp-2 italic">
            "{popover.selectedText}"
          </div>
          <textarea
            autoFocus
            className={`w-full text-sm rounded-md p-2 outline-none resize-none h-20 ${isDarkMode ? "bg-slate-900/50 text-white placeholder-slate-500" : "bg-slate-50 text-slate-900 placeholder-slate-400"}`}
            placeholder="설계 결함에 대한 의견을 남겨주세요..."
            value={commentInput}
            onChange={(e) => setCommentInput(e.target.value)}
          />
          <div className="flex justify-between items-center mt-1">
            <button onClick={() => setPopover({ ...popover, visible: false })} className="text-xs font-bold text-slate-400 hover:text-red-400">취소</button>
            <button onClick={handleAddComment} className="flex items-center gap-1 bg-blue-500 hover:bg-blue-600 text-white text-xs font-bold py-1 px-3 rounded-md transition-colors">
              <MessageSquarePlus size={12} /> 댓글 달기
            </button>
          </div>
        </div>
      )}

      <div className={`flex items-center justify-between p-4 rounded-xl border ${
        isDarkMode 
          ? "bg-slate-800/40 border-slate-700/50" 
          : "bg-white border-slate-200 shadow-sm"
      }`}>
        <div>
          <h2 className={`text-xl font-bold flex items-center gap-2 ${isDarkMode ? "text-slate-100" : "text-slate-900"}`}>
            <FileText className="text-blue-500" size={20} />
            Architecture QA Analysis
          </h2>
          <p className={`text-sm mt-1 ${isDarkMode ? "text-slate-400" : "text-slate-500"}`}>
            Bundle ID: <span className={`font-mono font-bold ${isDarkMode ? "text-blue-300/80" : "text-blue-700"}`}>{metadata?.bundle_id || "N/A"}</span>
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <span className={`text-xs uppercase tracking-widest font-semibold ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>Integrity Status</span>
          <StatusBadge status={status || "WARNING"} />
        </div>
      </div>

      <Section title="사고 과정 (Thinking Process)" icon={<Info size={14} />}>
        <div className={`border p-4 rounded-lg ${
          isDarkMode 
            ? "bg-slate-900/50 border-slate-800 text-slate-300" 
            : "bg-slate-50 border-slate-200 text-slate-700 shadow-inner"
        }`}>
          <p className="text-[14px] leading-relaxed whitespace-pre-wrap italic">
            "{thinking || "분석 내용이 없습니다."}"
          </p>
        </div>
      </Section>

      <Section title="결함 리포트 (Gap Analysis)" icon={<AlertTriangle size={14} />}>
        {gaps && gaps.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {gaps.map((gap, idx) => (
              <div key={idx} className={`flex items-start gap-3 p-3 border rounded-lg ${
                isDarkMode 
                  ? "bg-red-900/10 border-red-900/30 text-red-200/90" 
                  : "bg-red-50 border-red-200 text-red-800 shadow-sm"
              }`}>
                <AlertTriangle className={`${isDarkMode ? "text-red-400" : "text-red-500"} mt-0.5 shrink-0`} size={16} />
                <span className="text-[14px] leading-snug">{gap}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className={`flex items-center gap-3 p-4 border rounded-lg ${
            isDarkMode 
              ? "bg-emerald-900/10 border-emerald-900/30 text-emerald-200/80" 
              : "bg-emerald-50 border-emerald-200 text-emerald-800 shadow-sm"
          }`}>
            <CheckCircle className={isDarkMode ? "text-emerald-400" : "text-emerald-500"} size={18} />
            <span className="text-[14px] font-medium">발견된 설계 결함이 없습니다. 아키텍처가 정합성을 유지하고 있습니다.</span>
          </div>
        )}
      </Section>
    </div>
  );
}

export default SAAnalysisTab;
