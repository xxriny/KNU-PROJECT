import React, { useEffect, useRef, useState } from "react";
import {
  CheckCircle2, Undo2, RotateCcw, MessageCircleQuestion,
  Zap, GitCompareArrows, Loader2, RefreshCw, AlertTriangle, X,
} from "lucide-react";
import useAppStore from "../../store/useAppStore";
import ScrollArea from "../ui/ScrollArea";
import ChatMessage from "./ChatMessage";
import PipelineProgress from "../PipelineProgress";

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

  const handleFollowupClick = (text) => {
    if (pipelineStatus === "running") return;
    const t = (text || "").trim();
    if (!t) return;
    addChatMessage("user", t);
    sendIdeaChat(t, apiKey, model);
  };

  const lastMsg = (chatHistory || [])[chatHistory.length - 1];
  const showFollowups =
    (lastFollowups || []).length > 0 &&
    lastMsg?.role === "assistant" &&
    pipelineStatus !== "running";

  // 마지막 sync 마커 이후 새 대화가 있고, 마지막 메시지가 assistant일 때만 노출
  const lastSyncIdx = (() => {
    for (let i = (chatHistory || []).length - 1; i >= 0; i--) {
      if (chatHistory[i]?.role === "system_marker" && chatHistory[i]?.kind === "sync") return i;
    }
    return -1;
  })();
  const newMsgCount = (chatHistory || [])
    .slice(lastSyncIdx + 1)
    .filter((m) => m?.role === "user" || m?.role === "assistant")
    .length;

  const showActionButtons =
    !!resultData &&
    pipelineStatus !== "running" &&
    newMsgCount > 0 &&
    lastMsg?.role === "assistant";

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
      <div className="max-w-5xl mx-auto pb-4">
        {(chatHistory || []).map((msg, idx) => {
          if (msg?.role === "system_marker") {
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
          <div
            className="w-full h-[320px] rounded-2xl overflow-hidden border shadow-lg mt-4 mb-4"
            style={{ borderColor: isDarkMode ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.1)" }}
          >
            <PipelineProgress />
          </div>
        )}

        {/* 액션 버튼 툴바 */}
        {showActionButtons && (
          <div className="mt-5 ml-11 animate-fade-in">
            <div className={`inline-flex items-center gap-1 p-1 rounded-2xl border ${
              isDarkMode ? "bg-white/[0.03] border-white/[0.07]" : "bg-slate-50 border-slate-200"
            }`}>
              <ActionButton
                icon={<Zap size={12} />}
                label="설계서 업데이트"
                onClick={onSync}
                variant="primary"
                isDarkMode={isDarkMode}
              />
              <div className={`w-px h-4 ${isDarkMode ? "bg-white/10" : "bg-slate-200"}`} />
              <ActionButton
                icon={impactLoading
                  ? <Loader2 size={12} className="animate-spin" />
                  : <GitCompareArrows size={12} />
                }
                label="영향도 분석"
                onClick={handleImpactAnalysis}
                disabled={impactLoading}
                variant="ghost"
                isDarkMode={isDarkMode}
              />
            </div>
          </div>
        )}

        {/* 영향도 분석 결과 카드 */}
        {(impactLoading || impactResult) && (
          <ImpactCard
            result={impactResult}
            loading={impactLoading}
            isDarkMode={isDarkMode}
            onRetry={handleImpactAnalysis}
            onDismiss={() => setImpactResult(null)}
          />
        )}

        <div ref={bottomRef} className="h-1" />
      </div>
    </ScrollArea>
  );
}

/* ── ActionButton ─────────────────────────────── */
function ActionButton({ icon, label, onClick, disabled, variant, isDarkMode }) {
  const base = "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[12px] font-semibold transition-all disabled:opacity-40";
  const styles = {
    primary: isDarkMode
      ? `${base} text-blue-300 hover:bg-blue-500/20 hover:text-blue-200`
      : `${base} text-blue-600 hover:bg-blue-100 hover:text-blue-700`,
    ghost: isDarkMode
      ? `${base} text-slate-400 hover:bg-white/[0.06] hover:text-slate-200`
      : `${base} text-slate-500 hover:bg-slate-100 hover:text-slate-700`,
  };
  return (
    <button onClick={onClick} disabled={disabled} className={styles[variant]}>
      {icon}
      {label}
    </button>
  );
}

/* ── ImpactCard ───────────────────────────────── */
function ImpactCard({ result, loading, isDarkMode, onRetry, onDismiss }) {
  return (
    <div className={`mt-3 ml-11 rounded-2xl border overflow-hidden animate-fade-in ${
      isDarkMode
        ? "bg-[#0d1117] border-white/[0.08]"
        : "bg-white border-slate-200 shadow-sm"
    }`}>
      {/* 헤더 */}
      <div className={`flex items-center justify-between px-4 py-2.5 border-b ${
        isDarkMode ? "border-white/[0.06] bg-white/[0.02]" : "border-slate-100 bg-slate-50/60"
      }`}>
        <div className="flex items-center gap-2">
          <div className={`w-5 h-5 rounded-md flex items-center justify-center ${
            isDarkMode ? "bg-violet-500/20" : "bg-violet-100"
          }`}>
            <GitCompareArrows size={11} className={isDarkMode ? "text-violet-400" : "text-violet-600"} />
          </div>
          <span className={`text-[11px] font-bold tracking-wide ${
            isDarkMode ? "text-slate-300" : "text-slate-700"
          }`}>
            영향도 분석
          </span>
          {loading && (
            <span className={`text-[10px] font-medium ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>
              · 분석 중...
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {!loading && result?.status === "ok" && (
            <button
              onClick={onRetry}
              title="다시 분석"
              className={`p-1 rounded-lg transition-colors ${
                isDarkMode
                  ? "text-slate-500 hover:text-slate-300 hover:bg-white/[0.06]"
                  : "text-slate-400 hover:text-slate-600 hover:bg-slate-100"
              }`}
            >
              <RefreshCw size={11} />
            </button>
          )}
          <button
            onClick={onDismiss}
            title="닫기"
            className={`p-1 rounded-lg transition-colors ${
              isDarkMode
                ? "text-slate-500 hover:text-slate-300 hover:bg-white/[0.06]"
                : "text-slate-400 hover:text-slate-600 hover:bg-slate-100"
            }`}
          >
            <X size={11} />
          </button>
        </div>
      </div>

      {/* 본문 */}
      <div className="px-4 py-3">
        {loading ? (
          <LoadingSkeleton isDarkMode={isDarkMode} />
        ) : result?.status === "error" ? (
          <ErrorBody error={result.error} isDarkMode={isDarkMode} onRetry={onRetry} />
        ) : (
          <ResultBody result={result} isDarkMode={isDarkMode} />
        )}
      </div>
    </div>
  );
}

function LoadingSkeleton({ isDarkMode }) {
  const bar = (w) => (
    <div
      className={`h-3 rounded-full animate-pulse ${isDarkMode ? "bg-white/[0.06]" : "bg-slate-200"}`}
      style={{ width: w }}
    />
  );
  return (
    <div className="space-y-2.5 py-1">
      {bar("85%")}
      {bar("70%")}
      {bar("78%")}
    </div>
  );
}

function ErrorBody({ error, isDarkMode, onRetry }) {
  return (
    <div className={`flex items-start gap-2.5 rounded-xl p-3 ${
      isDarkMode ? "bg-red-500/10 border border-red-500/20" : "bg-red-50 border border-red-200"
    }`}>
      <AlertTriangle size={14} className="mt-0.5 shrink-0 text-red-400" />
      <div className="flex-1 min-w-0">
        <p className={`text-[12px] font-semibold mb-0.5 ${isDarkMode ? "text-red-300" : "text-red-700"}`}>
          분석 실패
        </p>
        <p className={`text-[11px] leading-relaxed ${isDarkMode ? "text-red-400/80" : "text-red-600"}`}>
          {error || "알 수 없는 오류가 발생했습니다."}
        </p>
        <button
          onClick={onRetry}
          className={`mt-2 text-[11px] font-bold underline underline-offset-2 ${
            isDarkMode ? "text-red-300" : "text-red-700"
          }`}
        >
          다시 시도
        </button>
      </div>
    </div>
  );
}

function ResultBody({ result, isDarkMode }) {
  const items = parseMarkdownList(result?.summary_markdown || "");
  const dropped = result?.dropped_points || [];

  if (!items.length && !dropped.length) {
    return (
      <p className={`text-[13px] py-1 ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>
        변경사항 없음
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {items.length > 0 && (
        <ul className="space-y-2">
          {items.map((item, i) => (
            <li key={i} className="flex items-start gap-2.5">
              <span className={`mt-[5px] w-1.5 h-1.5 rounded-full shrink-0 ${
                isDarkMode ? "bg-violet-400" : "bg-violet-500"
              }`} />
              <span className={`text-[13px] leading-relaxed ${
                isDarkMode ? "text-slate-200" : "text-slate-700"
              }`}>
                {item.indent && (
                  <span className={`mr-1 text-[11px] ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>
                    ↳
                  </span>
                )}
                {item.text}
              </span>
            </li>
          ))}
        </ul>
      )}

      {dropped.length > 0 && (
        <div className={`rounded-xl p-3 border ${
          isDarkMode ? "bg-white/[0.02] border-white/[0.05]" : "bg-slate-50 border-slate-100"
        }`}>
          <p className={`text-[10px] font-black uppercase tracking-[0.18em] mb-2 ${
            isDarkMode ? "text-slate-500" : "text-slate-400"
          }`}>
            제외된 항목
          </p>
          <ul className="space-y-1">
            {dropped.map((pt, i) => (
              <li key={i} className={`text-[12px] line-through ${
                isDarkMode ? "text-slate-600" : "text-slate-400"
              }`}>
                {pt}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/** "- foo", "1. foo", "  - bar" 형태를 파싱해서 { text, indent } 배열로 반환 */
function parseMarkdownList(md) {
  const items = [];
  for (const raw of (md || "").split("\n")) {
    const line = raw.trimEnd();
    if (!line.trim()) continue;
    // 섹션 헤더(## …)는 그대로 텍스트로 추가
    const headerMatch = line.match(/^#{1,3}\s+(.+)/);
    if (headerMatch) {
      items.push({ text: headerMatch[1], indent: false, header: true });
      continue;
    }
    const bulletMatch = line.match(/^(\s*)[-*]\s+(.+)/);
    if (bulletMatch) {
      items.push({ text: bulletMatch[2], indent: bulletMatch[1].length > 0 });
      continue;
    }
    const numMatch = line.match(/^(\s*)\d+\.\s+(.+)/);
    if (numMatch) {
      items.push({ text: numMatch[2], indent: numMatch[1].length > 0 });
      continue;
    }
    // 일반 텍스트 줄
    if (line.trim()) items.push({ text: line.trim(), indent: false });
  }
  return items;
}

/* ── FollowupChips ────────────────────────────── */
function FollowupChips({ items, isDarkMode, onPick }) {
  return (
    <div className="mt-8 ml-11 animate-fade-in">
      {/* 타이틀 */}
      <div className="flex items-center gap-2 mb-3">
        <span className={`text-[14px] font-extrabold tracking-tight ${
          isDarkMode ? "text-slate-300" : "text-slate-800"
        }`}>
          후속 조치
        </span>
      </div>

      {/* 세로 리스트 */}
      <div className={`flex flex-col border-t ${
        isDarkMode ? "border-white/[0.06]" : "border-slate-100"
      }`}>
        {items.map((text, idx) => (
          <button
            key={idx}
            onClick={() => onPick(text)}
            className={`w-full flex items-start gap-3 py-3.5 text-left border-b transition-all duration-150 group ${
              isDarkMode
                ? "border-white/[0.06] hover:bg-white/[0.02] text-slate-300"
                : "border-slate-100 hover:bg-slate-50 text-slate-700"
            }`}
          >
            {/* 파란색 ↳ 화살표 */}
            <span className={`text-[15px] leading-none shrink-0 font-bold ${
              isDarkMode ? "text-blue-400 group-hover:text-blue-300" : "text-blue-600 group-hover:text-blue-500"
            }`}>
              ↳
            </span>
            <span className={`text-[13px] font-medium leading-relaxed transition-colors ${
              isDarkMode 
                ? "text-slate-300 group-hover:text-white" 
                : "text-slate-700 group-hover:text-blue-600"
            }`}>
              {text}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

/* ── SyncMarkerChip ───────────────────────────── */
function SyncMarkerChip({ marker, isDarkMode, hasSnapshot, onRestore }) {
  const isRollback = marker.kind === "rollback";
  const time = (() => {
    try {
      return new Date(marker.appliedAt).toLocaleTimeString("ko", { hour: "2-digit", minute: "2-digit" });
    } catch { return ""; }
  })();

  if (isRollback) {
    return (
      <div className="my-6 flex items-center gap-3 animate-fade-in">
        <div className={`flex-1 h-px ${isDarkMode ? "bg-amber-500/20" : "bg-amber-200"}`} />
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-[11px] font-bold ${
          isDarkMode
            ? "bg-amber-500/10 border-amber-500/30 text-amber-300"
            : "bg-amber-50 border-amber-200 text-amber-700"
        }`}>
          <RotateCcw size={12} />
          <span>{marker.fromVersion} → {marker.toVersion} 롤백</span>
          <span className="opacity-60">· {time}</span>
        </div>
        <div className={`flex-1 h-px ${isDarkMode ? "bg-amber-500/20" : "bg-amber-200"}`} />
      </div>
    );
  }

  return (
    <div className="my-6 flex items-center gap-3 animate-fade-in">
      <div className={`flex-1 h-px ${isDarkMode ? "bg-emerald-500/20" : "bg-emerald-200"}`} />
      <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-[11px] font-bold ${
        isDarkMode
          ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
          : "bg-emerald-50 border-emerald-200 text-emerald-700"
      }`}>
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
