import React, { useRef } from "react";
import useAppStore from "../store/useAppStore";
import useCommentPopover from "../hooks/useCommentPopover";
import { MessageSquarePlus, X, Loader2 } from "lucide-react";
import OverviewTab from "./resultViewer/OverviewTab";
import RTMTab from "./resultViewer/RTMTab";
import StackTab from "./resultViewer/StackTab";
import SAAnalysisTab from "./resultViewer/SAAnalysisTab";
import SAComponentsTab from "./resultViewer/SAComponentsTab";
import SAApiTab from "./resultViewer/SAApiTab";
import SADatabaseTab from "./resultViewer/SADatabaseTab";
import MemoManager from "./resultViewer/MemoManager";
import Card from "./ui/Card";
import Button from "./ui/Button";
import Skeleton from "./ui/Skeleton";

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
  const isDarkMode = useAppStore((state) => state.isDarkMode);
  const pipelineStatus = useAppStore((state) => state.pipelineStatus);
  const resultData = useAppStore((state) => state.resultData);
  
  const TabComponent = TAB_COMPONENTS[tabId] || OverviewTab;
  const contentRef = useRef(null);

  const {
    popover,
    commentInput,
    setCommentInput,
    handleAddComment,
    closePopover
  } = useCommentPopover(contentRef, tabId);

  // 로딩 상태 처리
  const isLoading = pipelineStatus === "running" && !resultData;

  return (
    <div className="relative h-full overflow-hidden" ref={contentRef}>
      {/* Comment Popover (Modernized) */}
      {popover.visible && (
        <div 
          className="comment-popover absolute z-[100] animate-fade-in animate-slide-up"
          style={{ 
            left: popover.x, 
            top: popover.y,
            transform: "translateX(-50%) translateY(10px)"
          }}
        >
          <Card variant="solid" className="w-[320px] p-4 shadow-2xl border-blue-500/30 ring-4 ring-blue-500/5">
            <div className="flex justify-between items-start mb-3">
              <span className="text-[10px] font-black uppercase tracking-widest text-blue-500">Add Feedback</span>
              <button onClick={closePopover} className="text-slate-500 hover:text-red-500 transition-colors">
                <X size={14} />
              </button>
            </div>
            
            <div className={`text-[11px] font-medium p-2 rounded mb-3 line-clamp-2 italic border-l-2 border-blue-500/30 ${isDarkMode ? "bg-white/5 text-slate-400" : "bg-slate-50 text-slate-500"}`}>
              "{popover.selectedText}"
            </div>

            <textarea
              autoFocus
              className={`w-full text-[13px] font-medium rounded-lg p-3 outline-none resize-none h-24 mb-3 transition-all border ${
                isDarkMode 
                  ? "bg-slate-900/50 border-white/5 focus:border-blue-500/50 text-white" 
                  : "bg-slate-50 border-slate-200 focus:border-blue-500/50 text-slate-900"
              }`}
              placeholder="피드백이나 수정 제안을 입력하세요..."
              value={commentInput}
              onChange={(e) => setCommentInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleAddComment();
                }
              }}
            />

            <div className="flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={closePopover}>취소</Button>
              <Button variant="primary" size="sm" onClick={handleAddComment} Icon={MessageSquarePlus}>저장</Button>
            </div>
          </Card>
        </div>
      )}

      {/* Main Content Area */}
      <div className="h-full overflow-hidden flex flex-col">
        {isLoading ? (
          <div className="flex-1 p-8 space-y-8 animate-fade-in">
            <Skeleton className="h-12 w-3/4" />
            <div className="grid grid-cols-2 gap-4">
              <Skeleton className="h-32" />
              <Skeleton className="h-32" />
            </div>
            <Skeleton className="h-64" />
          </div>
        ) : (
          <div className="flex-1 h-full overflow-y-auto custom-scrollbar doc-font-up selectable">
            <TabComponent />
          </div>
        )}
      </div>
    </div>
  );
}
