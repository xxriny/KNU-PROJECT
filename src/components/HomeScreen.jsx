import React, { useState, useEffect, useMemo, useRef } from "react";
import useAppStore from "../store/useAppStore";
import {
  Send, Loader2, Rocket, AlertTriangle, Sparkles, Layers, ScanSearch, Github,
} from "lucide-react";
import ChatThread from "./chat/ChatThread";
import SyncConfirmModal from "./SyncConfirmModal";

// 정확히 3개로 고정 — 시각적 부담을 줄이고 미니멀하게 유도
const EXAMPLE_PILLS = [
  "쇼핑몰에 포인트 결제 시스템 추가",
  "기존 결제 모듈에 환불 흐름 보완",
  "내 GitHub 레포에서 RTM 역추출",
];

const MODE_LABEL = {
  create:  { label: "신규 기획",  Icon: Sparkles,   placeholder: "구체화하고 싶은 아이디어를 입력하세요..." },
  update:  { label: "기능 확장",  Icon: Layers,     placeholder: "추가하거나 변경하고 싶은 기능을 입력하세요..." },
  reverse: { label: "재분석",    Icon: ScanSearch, placeholder: "(선택사항) 분석 시 참고할 컨텍스트가 있으면 입력하세요..." },
};

export default function HomeScreen() {
  const runSyncUpdate = useAppStore((s) => s.runSyncUpdate);
  const sendIdeaChat = useAppStore((s) => s.sendIdeaChat);
  const addChatMessage = useAppStore((s) => s.addChatMessage);
  const createSession = useAppStore((s) => s.createSession);
  const currentSessionId = useAppStore((s) => s.currentSessionId);
  const apiKey = useAppStore((s) => s.apiKey);
  const model = useAppStore((s) => s.model);
  const selectedMode = useAppStore((s) => s.selectedMode);
  const projectFolder = useAppStore((s) => s.projectFolder);
  const isDarkMode = useAppStore((s) => s.isDarkMode);
  const chatHistory = useAppStore((s) => s.chatHistory);
  const chatInput = useAppStore((s) => s.chatInput);
  const setChatInput = useAppStore((s) => s.setChatInput);
  const pipelineStatus = useAppStore((s) => s.pipelineStatus);
  const pipelineType = useAppStore((s) => s.pipelineType);
  const userComments = useAppStore((s) => s.userComments);
  const lastIdeaReady = useAppStore((s) => s.lastIdeaReady);
  const lastIdeaSummary = useAppStore((s) => s.lastIdeaSummary);
  const currentUser = useAppStore((s) => s.currentUser);
  const addNotification = useAppStore((s) => s.addNotification);
  const resultData = useAppStore((s) => s.resultData);
  const designSnapshotCounter = useAppStore((s) => s.designSnapshotCounter);

  const [projectTitle, setProjectTitle] = useState("새 프로젝트");
  const [syncModalOpen, setSyncModalOpen] = useState(false);
  const textareaRef = useRef(null);

  // hasStarted: 실제 대화(user/assistant)가 있으면 conversation 모드
  const hasStarted = (chatHistory || []).some(
    (m) => m && (m.role === "user" || m.role === "assistant")
  );

  const isPm = currentUser?.role === "pm";
  const isReverseMode = selectedMode === "reverse";
  const trimmedInput = (chatInput || "").trim();
  const isProcessing = pipelineStatus === "running";
  const activeMemoCount = (userComments || []).filter((m) => !m.applied).length;
  const modeMeta = MODE_LABEL[selectedMode] || MODE_LABEL.create;

  // CREATE 모드에서 한 번이라도 Sync 완료(설계서 픽스)되면 GitHub Export 버튼 노출
  const hasSyncedAtLeastOnce = (chatHistory || []).some(
    (m) => m && m.role === "system_marker" && m.kind === "sync"
  );
  const showExportBanner = selectedMode === "create" && hasSyncedAtLeastOnce && hasStarted;

  const handleGithubExport = () => {
    addNotification?.(
      "GitHub Export는 다음 업데이트에서 제공될 예정입니다. (빈 레포 선택 → 스펙 + 스켈레톤 초기 커밋)",
      "info",
      4000
    );
  };

  const canSendInitial = isPm && !!trimmedInput && (!isReverseMode || !!projectFolder);
  const canSendFollowUp = isPm && !!trimmedInput && !isProcessing;
  const canSend = hasStarted ? canSendFollowUp : canSendInitial;

  // 모든 전송 → idea_chat (가벼운 대화). 무거운 PM/SA 빌드는 🚀 Sync 버튼에서만 가동.
  // 첫 발화일 때만 세션을 생성해 메모/스냅샷이 현재 프로젝트에 귀속되도록 한다.
  const handleSend = () => {
    if (!canSend) return;
    const text = trimmedInput;
    if (!hasStarted && !currentSessionId) {
      createSession(projectTitle);
    }
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

  // 🚀 Sync 미리보기 — pipelineSlice.runSyncUpdate와 동일한 규칙으로 계산.
  //    (계산 비용이 가벼워 매 렌더 시 useMemo로만 처리)
  const syncPreview = useMemo(() => {
    const isFirstBuild = !resultData;
    const lastSyncIdx = (() => {
      for (let i = (chatHistory || []).length - 1; i >= 0; i--) {
        const m = chatHistory[i];
        if (m && m.role === "system_marker" && m.kind === "sync") return i;
      }
      return -1;
    })();
    const chatDiff = (chatHistory || [])
      .slice(lastSyncIdx + 1)
      .filter((m) => m && (m.role === "user" || m.role === "assistant"));
    const activeMemos = (userComments || []).filter((c) => !c.applied);
    const targetVersion = isFirstBuild
      ? "v1.0"
      : `v1.${(designSnapshotCounter || 0) + 1}`;
    return { isFirstBuild, chatDiff, activeMemos, targetVersion };
  }, [resultData, chatHistory, userComments, designSnapshotCounter]);

  const handleSync = () => {
    if (isProcessing) return;
    setSyncModalOpen(true);
  };

  // 모달에서 사용자가 검토·편집한 '정제된 요구사항 마크다운'을 받아 그대로 파이프라인에 전달.
  // 빈 문자열이면 runSyncUpdate가 fallback으로 날것 합성을 사용한다.
  const handleSyncConfirm = (finalIdea) => {
    setSyncModalOpen(false);
    runSyncUpdate({ ideaOverride: finalIdea || "" });
  };

  const handleSyncCancel = () => setSyncModalOpen(false);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 150) + "px";
    }
  }, [chatInput]);

  return (
    <div
      className={`h-full w-full flex flex-col relative overflow-hidden ${
        isDarkMode ? "bg-transparent text-slate-200" : "bg-transparent text-slate-800"
      }`}
    >
      {/* 배경 글로우 */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-[10%] -left-[5%] w-[50%] h-[50%] bg-blue-500/10 blur-[120px] rounded-full" />
      </div>

      {hasStarted ? (
        /* ────────────────── Conversation 모드 ────────────────── */
        <div className="flex-1 min-h-0 flex flex-col relative z-10 animate-fade-in">
          {showExportBanner && (
            <div className="px-6 pt-3 shrink-0">
              <div
                className={`max-w-3xl mx-auto flex items-center gap-3 px-4 py-2.5 rounded-2xl border ${
                  isDarkMode
                    ? "bg-gradient-to-r from-emerald-500/10 to-blue-500/10 border-emerald-500/20"
                    : "bg-gradient-to-r from-emerald-50 to-blue-50 border-emerald-200"
                }`}
              >
                <Github size={16} className={isDarkMode ? "text-emerald-300" : "text-emerald-700"} />
                <span className={`text-[12px] font-medium flex-1 ${isDarkMode ? "text-slate-200" : "text-slate-700"}`}>
                  설계서가 픽스되었습니다. 빈 GitHub 레포에 첫 커밋으로 내보낼 수 있습니다.
                </span>
                <button
                  onClick={handleGithubExport}
                  className="px-3 py-1.5 rounded-lg text-[12px] font-bold bg-gradient-to-r from-emerald-600 to-blue-600 hover:from-emerald-500 hover:to-blue-500 text-white shadow-md shadow-emerald-500/20 transition-all"
                >
                  🐙 GitHub에 내보내기
                </button>
              </div>
            </div>
          )}
          <ChatThread />
        </div>
      ) : (
        /* ────────────────── Welcome 모드 ────────────────── */
        <div className="flex-1 min-h-0 flex flex-col items-center justify-center px-8 relative z-10 animate-fade-in">
          <div className="text-center mb-10 max-w-2xl">
            <h1 className="text-5xl font-black mb-3 tracking-widest drop-shadow-sm">
              <span className="text-gradient">NAVIGATOR</span>
            </h1>
            <p
              className={`text-[17px] font-medium opacity-50 ${
                isDarkMode ? "text-slate-400" : "text-slate-600"
              }`}
            >
              아이디어를 구조화된 요구사항 명세서로 변환합니다
            </p>

            {/* 프로젝트 제목 — 인라인 칩 */}
            <div className="mt-6 flex items-center justify-center gap-2">
              <span
                className={`text-[10px] font-black uppercase tracking-[0.25em] ${
                  isDarkMode ? "text-slate-600" : "text-slate-400"
                }`}
              >
                프로젝트
              </span>
              <input
                value={projectTitle}
                onChange={(e) => setProjectTitle(e.target.value)}
                className={`text-sm font-bold px-3 py-1 rounded-full border outline-none transition-colors text-center w-[200px] ${
                  isDarkMode
                    ? "bg-white/5 border-white/10 text-slate-200 focus:border-blue-400/40"
                    : "bg-white border-slate-200 text-slate-700 focus:border-blue-400"
                }`}
                placeholder="프로젝트 제목"
              />
            </div>
          </div>
        </div>
      )}

      {/* ────────────────── 하단 도크 (Input + 🚀 Sync) ────────────────── */}
      <div
        className={`shrink-0 px-6 pb-6 relative z-20 ${
          hasStarted ? "pt-2" : "pt-0 pb-12"
        }`}
      >
        <div className="max-w-3xl mx-auto">
          {/* PM 권한 가드 */}
          {!isPm && (
            <div className="mb-3 w-full text-center py-2 px-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 text-[12px] font-medium">
              LLM 분석은 PM 권한이 필요합니다. 팀 PM에게 권한을 요청하세요.
            </div>
          )}

          {/* reverse 모드 + 레포 미설정 inline 경고 */}
          {!hasStarted && isReverseMode && !projectFolder && (
            <div className="mb-3 w-full text-center py-2 px-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400 text-[12px] font-medium flex items-center justify-center gap-2">
              <AlertTriangle size={13} />
              재분석 모드는 GitHub 레포지토리가 설정되어 있어야 합니다.
            </div>
          )}

          {/* 분석 진행 중 배너 */}
          {isProcessing && hasStarted && (
            <div
              className={`mb-3 px-4 py-2.5 rounded-2xl flex items-center gap-3 border animate-fade-in ${
                isDarkMode
                  ? "bg-blue-500/10 border-blue-500/30 text-blue-300"
                  : "bg-blue-50 border-blue-200 text-blue-700"
              }`}
            >
              <Loader2 size={14} className="shrink-0 animate-spin text-blue-500" />
              <span className="text-[12px] font-medium">
                {pipelineType === "analysis_update"
                  ? "메모/대화를 반영해 설계서를 업데이트 중입니다..."
                  : "분석을 진행 중입니다..."}
              </span>
            </div>
          )}

          {/* 입력 pill */}
          <div
            className={`w-full relative rounded-3xl shadow-2xl border ${
              isDarkMode
                ? "bg-[#161b22]/90 backdrop-blur-2xl border-white/5"
                : "bg-white/95 backdrop-blur-xl border-slate-200"
            } ${!isPm ? "opacity-50 pointer-events-none" : ""}`}
          >
            <div className="flex items-end p-3 pl-5 gap-2">
              <div className="flex-1 min-w-0">
                <textarea
                  ref={textareaRef}
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={1}
                  placeholder={hasStarted ? "메시지를 입력하세요..." : modeMeta.placeholder}
                  disabled={isProcessing}
                  className="w-full bg-transparent border-none focus:outline-none focus:ring-0 text-[15px] py-2 resize-none scrollbar-hide placeholder:text-slate-500"
                />
              </div>

              <div className="flex items-center gap-1.5 shrink-0">
                {/* 🚀 Sync 버튼 — conversation 모드에서만 노출 */}
                {hasStarted && (
                  <SyncButton
                    onClick={handleSync}
                    glow={lastIdeaReady}
                    activeMemoCount={activeMemoCount}
                    isProcessing={isProcessing}
                    isDarkMode={isDarkMode}
                    tooltip={lastIdeaSummary}
                  />
                )}

                {/* Send 버튼 */}
                <button
                  onClick={handleSend}
                  disabled={!canSend}
                  title="메시지 보내기"
                  className={`w-11 h-11 flex items-center justify-center rounded-2xl transition-all ${
                    canSend
                      ? "bg-blue-600 text-white hover:bg-blue-500 shadow-lg shadow-blue-500/20"
                      : isDarkMode
                        ? "bg-white/5 text-slate-700 cursor-not-allowed"
                        : "bg-slate-100 text-slate-400 cursor-not-allowed"
                  }`}
                >
                  <Send size={18} />
                </button>
              </div>
            </div>
          </div>

          {/* Welcome 모드에서만: 예시 알약 + 푸터 */}
          {!hasStarted && (
            <>
              <div className="mt-4 flex items-center justify-center gap-3">
                {EXAMPLE_PILLS.map((pill) => (
                  <button
                    key={pill}
                    onClick={() => setChatInput(pill)}
                    className={`px-3 py-1.5 rounded-full text-[12px] font-medium border transition-all hover:scale-[1.02] ${
                      isDarkMode
                        ? "bg-white/[0.03] border-white/10 text-slate-400 hover:text-slate-200 hover:border-white/20"
                        : "bg-white/80 border-slate-200 text-slate-600 hover:text-slate-900 hover:border-slate-300"
                    }`}
                  >
                    💊 {pill}
                  </button>
                ))}
              </div>

              <footer className="mt-6 px-2 flex items-center justify-between text-[10px] font-medium text-slate-600/50 uppercase tracking-widest opacity-60">
                <div className="flex items-center gap-3">
                  <span>NAVIGATOR PM PIPELINE</span>
                  <div className="w-1 h-1 rounded-full bg-slate-600/50" />
                  <span className="flex items-center gap-1.5">
                    <modeMeta.Icon size={11} />
                    {modeMeta.label}
                  </span>
                </div>
                <span>PROMPT + ENTER TO PROCESS</span>
              </footer>
            </>
          )}
        </div>
      </div>

      {/* 🚀 Sync 확인 모달 — 수락 시에만 실제 파이프라인 가동 */}
      <SyncConfirmModal
        open={syncModalOpen}
        isDarkMode={isDarkMode}
        isFirstBuild={syncPreview.isFirstBuild}
        targetVersion={syncPreview.targetVersion}
        chatDiff={syncPreview.chatDiff}
        activeMemos={syncPreview.activeMemos}
        onCancel={handleSyncCancel}
        onConfirm={handleSyncConfirm}
      />
    </div>
  );
}

/** 🚀 Sync 버튼 — idea_ready 글로우 + 활성 메모 카운트 배지 */
function SyncButton({ onClick, glow, activeMemoCount, isProcessing, isDarkMode, tooltip }) {
  const title = (() => {
    const lines = ["🚀 현재 대화 + 활성 메모로 설계서 업데이트"];
    if (activeMemoCount > 0) lines.push(`📋 메모 ${activeMemoCount}건 함께 반영`);
    if (tooltip) lines.push(`💡 ${tooltip}`);
    return lines.join("\n");
  })();

  return (
    <button
      onClick={onClick}
      disabled={isProcessing}
      title={title}
      className={`relative w-11 h-11 flex items-center justify-center rounded-2xl transition-all ${
        glow
          ? "bg-gradient-to-br from-emerald-500 to-teal-600 text-white animate-pulse shadow-[0_0_24px_rgba(52,211,153,0.5)] ring-2 ring-emerald-400/60"
          : isDarkMode
            ? "bg-white/[0.06] hover:bg-white/[0.1] text-slate-300 hover:text-white"
            : "bg-slate-100 hover:bg-slate-200 text-slate-600 hover:text-slate-900"
      } ${isProcessing ? "opacity-40 cursor-not-allowed" : ""}`}
    >
      <Rocket size={18} />
      {activeMemoCount > 0 && (
        <span
          className={`absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 flex items-center justify-center rounded-full text-[10px] font-black ${
            isDarkMode
              ? "bg-blue-500 text-white border border-[#0F1219]"
              : "bg-blue-500 text-white border border-white"
          }`}
        >
          {activeMemoCount}
        </span>
      )}
    </button>
  );
}
