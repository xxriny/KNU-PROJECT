import { useRef, useEffect } from "react";
import useAppStore from "../store/useAppStore";

export default function useChat() {
  const chatHistory = useAppStore((state) => state.chatHistory);
  const chatInput = useAppStore((state) => state.chatInput);
  const setChatInput = useAppStore((state) => state.setChatInput);
  const sendIdeaChat = useAppStore((state) => state.sendIdeaChat);
  const addChatMessage = useAppStore((state) => state.addChatMessage);
  const pipelineStatus = useAppStore((state) => state.pipelineStatus);
  const apiKey = useAppStore((state) => state.apiKey);
  const model = useAppStore((state) => state.model);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // 새 메시지가 올 때마다 하단으로 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  // 입력창 높이 자동 조절
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 150) + 'px';
    }
  }, [chatInput]);

  const handleSend = () => {
    const text = chatInput.trim();
    if (!text || pipelineStatus === "running") return;

    addChatMessage("user", text);
    setChatInput("");
    sendIdeaChat(text, apiKey, model);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return {
    chatHistory,
    chatInput,
    setChatInput,
    handleSend,
    handleKeyDown,
    messagesEndRef,
    inputRef,
    isProcessing: pipelineStatus === "running"
  };
}
