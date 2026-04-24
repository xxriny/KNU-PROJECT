import { useState, useEffect } from "react";
import useAppStore from "../store/useAppStore";

export default function useCommentPopover(contentRef, tabId) {
  const { addComment } = useAppStore();
  const [popover, setPopover] = useState({ visible: false, x: 0, y: 0, selectedText: "" });
  const [commentInput, setCommentInput] = useState("");

  useEffect(() => {
    const handleMouseUp = (e) => {
      // popover 내부 클릭(textarea 클릭, 버튼 클릭 등) 시 닫히지 않도록 방지
      if (e.target.closest('.comment-popover')) return;

      const selection = window.getSelection();
      const text = selection.toString().trim();

      // 지정된 영역 내부에서 텍스트가 선택되었을 때만 트리거
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
        // 텍스트가 없거나 영역 밖 클릭 시 닫기 (단, 입력 중인 내용이 없을 때만)
        setPopover(prev => prev.visible ? { ...prev, visible: false } : prev);
      }
    };

    document.addEventListener("mouseup", handleMouseUp);
    return () => document.removeEventListener("mouseup", handleMouseUp);
  }, [contentRef, tabId]);

  const handleAddComment = () => {
    if (!commentInput.trim()) return;
    addComment({ text: commentInput, selectedText: popover.selectedText, section: tabId });
    setCommentInput("");
    setPopover({ visible: false, x: 0, y: 0, selectedText: "" });
    window.getSelection()?.removeAllRanges();
  };

  const closePopover = () => setPopover({ ...popover, visible: false });

  return {
    popover,
    commentInput,
    setCommentInput,
    handleAddComment,
    closePopover
  };
}
