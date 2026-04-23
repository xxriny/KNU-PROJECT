/**
 * ResultViewer — 파이프라인 산출물 뷰어 (라우터)
 * tabId에 따라 개별 탭 컴포넌트를 렌더링한다.
 */

import React, { useState, useEffect, useRef } from "react";
import useAppStore from "../store/useAppStore";
import { MessageSquarePlus, Bot, X } from "lucide-react";
import OverviewTab from "./resultViewer/OverviewTab";
import RTMTab from "./resultViewer/RTMTab";
import StackTab from "./resultViewer/StackTab";
import SAAnalysisTab from "./resultViewer/SAAnalysisTab";
import SAComponentsTab from "./resultViewer/SAComponentsTab";
import SAApiTab from "./resultViewer/SAApiTab";
import SADatabaseTab from "./resultViewer/SADatabaseTab";
import MemoManager from "./resultViewer/MemoManager";

const TAB_COMPONENTS = {
  overview: OverviewTab,
  rtm: RTMTab,
  stack: StackTab,
  sa_overview: SAAnalysisTab,
  sa_components: SAComponentsTab,
  sa_api: SAApiTab,
  sa_db: SADatabaseTab,
  memo: MemoManager,
};

export default function ResultViewer({ tabId = "overview" }) {
  const TabComponent = TAB_COMPONENTS[tabId] || OverviewTab;
  const { isDarkMode, addComment } = useAppStore();
  
  const [popover, setPopover] = useState({ visible: false, x: 0, y: 0, selectedText: "" });
  const [commentInput, setCommentInput] = useState("");
  const contentRef = useRef(null);

  useEffect(() => {
    const handleMouseUp = (e) => {
      // Prevent closing when clicking inside the popover
      if (e.target.closest('.comment-popover')) return;

      const selection = window.getSelection();
      const text = selection.toString().trim();

      // Only trigger if text is selected inside the content area
      if (text.length > 0 && contentRef.current?.contains(selection.anchorNode)) {
        const range = selection.getRangeAt(0);
        const rect = range.getBoundingClientRect();
        
        // Find container relative position
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
    addComment({ text: commentInput, selectedText: popover.selectedText, section: tabId });
    setCommentInput("");
    setPopover({ visible: false, x: 0, y: 0, selectedText: "" });
    window.getSelection()?.removeAllRanges();
  };

  return (
    <div className="relative h-full" ref={contentRef}>
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
            placeholder="이 부분에 대한 피드백을 남겨주세요..."
            value={commentInput}
            onChange={(e) => setCommentInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleAddComment();
              }
            }}
          />
          <div className="flex justify-between items-center mt-1">
            <button onClick={() => setPopover({ ...popover, visible: false })} className="text-xs font-bold text-slate-400 hover:text-red-400">취소</button>
            <button onClick={handleAddComment} className="flex items-center gap-1 bg-blue-500 hover:bg-blue-600 text-white text-xs font-bold py-1 px-3 rounded-md transition-colors">
              <MessageSquarePlus size={12} /> 댓글 달기
            </button>
          </div>
        </div>
      )}
      {/* Main Content Area */}
      <div className="flex h-full overflow-hidden">
        {/* Right: Document Viewer */}
        <div className="flex-1 h-full overflow-y-auto doc-font-up selectable relative">
          <TabComponent />
        </div>
      </div>
    </div>
  );
}
