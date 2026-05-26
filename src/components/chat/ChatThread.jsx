import React, { useEffect, useRef, useState } from "react";
import { CheckCircle2, Undo2, RotateCcw, MessageCircleQuestion, Zap, GitCompareArrows, Loader2 } from "lucide-react";
import useAppStore from "../../store/useAppStore";
import ScrollArea from "../ui/ScrollArea";
import ChatMessage from "./ChatMessage";
import PipelineProgress from "../PipelineProgress";

/**
 * ChatThread — chatHistory를 렌더하면서 system_marker(sync/rollback) 칩과
 * 마지막 assistant 응답 아래의 후속 질문 칩(suggested_followups)을 인라인 표시.
 * HomeScreen의 conversation 상태에서 사용.
 */
export default function ChatThread({ onSync }) {
  const chatHistory = useAppStore((s) => s.chatHistory);
  const restoreDesignSnapshot = useAppStore((s) => s.restoreDesignSnapshot);
  const designSnapshots = useAppStore((s) => s.designSnapshots);
  const isDarkMode = useAppStore((s) => s.isDarkMode);
  const lastFollowups = useAppStore((s) => s.lastFollowups);
  const pipelineStatus = useAppStore((s) => s.pipelineStatus);
  const sendIdeaChat = useAppStore((s) => s.sendIdeaChat);
  const addChatMessage = useAppStore((s) => s.addChatMessage);
  const apiKey = useAppStore((s) => s.apiKey);
  const model = useAppStore((s) => s.model);
  const resultData = useAppStore((s) => s.resultData);
  const extractFinalIdea = useAppStore((s) => s.extractFinalIdea);

  const [impactResult, setImpactResult] = useState(null);
  const [impactLoading, setImpactLoading] = useState(false);

  const bottomRef = useRef(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory, lastFollowups, pipelineStatus]);

  // 후속 질문 칩 클릭 → 즉시 사용자 메시지로 전송
  const handleFollowupClick = (text) => {
    if (pipelineStatus === "running") return;
    const t = (text || "").trim();
    if (!t) return;
    addChatMessage("user", t);
    sendIdeaChat(t, apiKey, model);
  };

  // 마지막 메시지가 assistant 이고, 채팅 진행 중이 아닐 때만 칩 노출
  const lastMsg = (chatHistory || [])[chatHistory.length - 1];
  const showFollowups =
    (lastFollowups || []).length > 0 &&
    lastMsg &&
    lastMsg.role === "assistant" &&
    pipelineStatus !== "running";

  // 결과 있고 idle일 때 액션 버튼 노출
  const showActionButtons =
    !!resultData &&
    pipelineStatus !== "running" &&
    lastMsg &&
    (lastMsg.role === "user" || lastMsg.role === "assistant");

  const handleImpactAnalysis = async () => {
    if (impactLoading) return;
    setImpactResult(null);
    setImpactLoading(true);
    try {
      const res = await extractFinalIdea();
      setImpactResult(res);
    } finally {
      setImpactLoading(false);
    }
  };

  return (
    <ScrollArea className="flex-1 px-4 pt-4">
      <div className="max-w-3xl mx-auto pb-4">
        {(chatHistory || []).map((msg, idx) => {
          if (msg && msg.role === "system_marker") {
            return (
              <SyncMarkerChip
                key={`marker-${idx}`}
                marker={msg}
                isDarkMode={isDarkMode}
                hasSnapshot={
                  typeof msg.snapshotIndex === "number" &&
                  msg.snapshotIndex >= 0 &&
                  (designSnapshots || [])[msg.snapshotIndex] != null
                }
                onRestore={() => restoreDesignSnapshot(msg.snapshotIndex)}
              />
            );
          }
          return <ChatMessage key={`msg-${idx}`} message={msg} />;
        })}

        {showFollowups && (
          <FollowupChips
            items={lastFollowups}
            isDarkMode={isDarkMode}
            onPick={handleFollowupClick}
          />
        )}

        {(pipelineStatus === "running" || pipelineStatus === "error") && (
          <div className="w-full h-[320px] rounded-2xl overflow-hidden border shadow-lg mt-4 mb-4" style={{ borderColor: isDarkMode ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)" }}>
             <PipelineProgress />
          </div>
        )}

        {/* 업데이트 / 영향도 분석 액션 버튼 */}
        {showActionButtons && (
          <div className="mt-4 ml-11 flex flex-wrap gap-2 animate-fade-in">
            <button
              onClick={onSync}
              className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-[12px] font-bold border transition-all hover:scale-[1.02] ${
                isDarkMode
                  ? "bg-blue-500/15 border-blue-500/30 text-blue-300 hover:bg-blue-500/25"
                  : "bg-blue-50 border-blue-200 text-blue-700 hover:bg-blue-100"
              }`}
            >
              <Zap size={13} />
              설계서 업데이트
            </button>
            <button
              onClick={handleImpactAnalysis}
              disabled={impactLoading}
              className={`inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-[12px] font-bold border transition-all hover:scale-[1.02] disabled:opacity-60 ${
                isDarkMode
                  ? "bg-white/[0.04] border-white/10 text-slate-300 hover:bg-white/[0.08]"
                  : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
              }`}
            >
              {impactLoading ? <Loader2 size={13} className="animate-spin" /> : <GitCompareArrows size={13} />}
              영향도 분석
            </button>
          </div>
        )}

        {/* 영향도 분석 결과 인라인 */}
        {impactResult && (
          <div className={`mt-3 ml-11 rounded-2xl border p-4 animate-fade-in ${
            isDarkMode ? "bg-white/[0.03] border-white/8" : "bg-slate-50 border-slate-200"
          }`}>
            <p className={`text-[10px] font-black uppercase tracking-[0.18em] mb-3 ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>
              영향도 분석
            </p>
            {impactResult.status === "error" ? (
              <div>
                <p className="text-[11px] font-bold text-red-400 mb-1">오류 발생</p>
                <p className="text-[12px] text-red-400 whitespace-pre-wrap">{impactResult.error || "알 수 없는 오류"}</p>
              </div>
            ) : (
              <>
                <p className={`text-[13px] leading-relaxed whitespace-pre-wrap ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>
                  {impactResult.summary_markdown || "변경사항 없음"}
                </p>
                {(impactResult.dropped_points || []).length > 0 && (
                  <div className="mt-3">
                    <p className={`text-[10px] font-bold mb-1.5 ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>취소된 항목</p>
                    <ul className="space-y-1">
                      {impactResult.dropped_points.map((pt, i) => (
                        <li key={i} className={`text-[12px] line-through ${isDarkMode ? "text-slate-600" : "text-slate-400"}`}>{pt}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        <div ref={bottomRef} className="h-1" />
      </div>
    </ScrollArea>
  );
}

function FollowupChips({ items, isDarkMode, onPick }) {
  return (
    <div className="mt-3 ml-11 flex flex-col gap-2 animate-fade-in">
      <div className="flex items-center gap-1.5">
        <MessageCircleQuestion size={12} className={isDarkMode ? "text-slate-500" : "text-slate-400"} />
        <span
          className={`text-[10px] font-bold uppercase tracking-[0.2em] ${
            isDarkMode ? "text-slate-600" : "text-slate-400"
          }`}
        >
          이어갈 질문
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        {items.map((text, idx) => (
          <button
            key={idx}
            onClick={() => onPick(text)}
            title="클릭하면 바로 전송됩니다"
            className={`px-3 py-1.5 rounded-full text-[12px] font-medium border transition-all hover:scale-[1.02] text-left ${
              isDarkMode
                ? "bg-white/[0.04] border-white/10 text-slate-300 hover:text-white hover:border-blue-400/40 hover:bg-blue-500/10"
                : "bg-white border-slate-200 text-slate-700 hover:text-blue-700 hover:border-blue-300 hover:bg-blue-50"
            }`}
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}

function SyncMarkerChip({ marker, isDarkMode, hasSnapshot, onRestore }) {
  const isRollback = marker.kind === "rollback";
  const time = (() => {
    try {
      const d = new Date(marker.appliedAt);
      return d.toLocaleTimeString("ko", { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  })();

  if (isRollback) {
    return (
      <div className="my-6 flex items-center gap-3 animate-fade-in">
        <div className={`flex-1 h-px ${isDarkMode ? "bg-amber-500/20" : "bg-amber-200"}`} />
        <div
          className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-[11px] font-bold ${
            isDarkMode
              ? "bg-amber-500/10 border-amber-500/30 text-amber-300"
              : "bg-amber-50 border-amber-200 text-amber-700"
          }`}
        >
          <RotateCcw size={12} />
          <span>
            {marker.fromVersion} → {marker.toVersion} 롤백
          </span>
          <span className="opacity-60">· {time}</span>
        </div>
        <div className={`flex-1 h-px ${isDarkMode ? "bg-amber-500/20" : "bg-amber-200"}`} />
      </div>
    );
  }

  return (
    <div className="my-6 flex items-center gap-3 animate-fade-in">
      <div className={`flex-1 h-px ${isDarkMode ? "bg-emerald-500/20" : "bg-emerald-200"}`} />
      <div
        className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-[11px] font-bold ${
          isDarkMode
            ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
            : "bg-emerald-50 border-emerald-200 text-emerald-700"
        }`}
      >
        <CheckCircle2 size={12} />
        <span>{marker.version} 설계서 업데이트 완료</span>
        <span className="opacity-60">· {time}</span>
        {hasSnapshot && (
          <button
            onClick={onRestore}
            title="이전 버전으로 되돌리기"
            className={`ml-1 flex items-center gap-1 px-2 py-0.5 rounded-full transition-colors ${
              isDarkMode
                ? "bg-white/5 hover:bg-white/10 text-slate-300"
                : "bg-white/80 hover:bg-white text-slate-600 border border-slate-200"
            }`}
          >
            <Undo2 size={10} />
            <span>되돌리기</span>
          </button>
        )}
      </div>
      <div className={`flex-1 h-px ${isDarkMode ? "bg-emerald-500/20" : "bg-emerald-200"}`} />
    </div>
  );
}
