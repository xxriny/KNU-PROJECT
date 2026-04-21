import React, { useState, useEffect, useRef } from "react";
import useAppStore from "../store/useAppStore";
import { Sparkles, Layers, ScanSearch, Send, Paperclip, ChevronRight } from "lucide-react";

const MODES = [
  {
    key: "create",
    label: "신규 기획",
    desc: "아이디어를 구조화된 요구사항으로 변환",
    icon: Sparkles,
    color: "from-blue-500 to-cyan-500",
    shadowColor: "rgba(59, 130, 246, 0.4)",
  },
  {
    key: "update",
    label: "기능 확장",
    desc: "기존 프로젝트에 새 기능 요구사항 추가",
    icon: Layers,
    color: "from-emerald-500 to-teal-500",
    shadowColor: "rgba(16, 185, 129, 0.4)",
  },
  {
    key: "reverse",
    label: "역공학",
    desc: "기존 시스템에서 RTM을 역추출",
    icon: ScanSearch,
    color: "from-purple-500 to-pink-500",
    shadowColor: "rgba(168, 85, 247, 0.4)",
  },
];



export default function HomeScreen() {
  const {
    startAnalysis,
    apiKey,
    model,
    selectedMode,
    setSelectedMode,
    projectFolder,
    selectAndScanFolder,
    isDarkMode,
  } = useAppStore();

  const [inputText, setInputText] = useState("");
  const [contextText, setContextText] = useState("");
  const [showContext, setShowContext] = useState(false);
  const textareaRef = useRef(null);

  const isReverseMode = selectedMode === "reverse";
  const trimmedInput = inputText.trim();
  const canSubmit = isReverseMode ? Boolean(projectFolder) : Boolean(trimmedInput);

  const handleSubmit = () => {
    if (isReverseMode && !projectFolder) return;
    if (!isReverseMode && !trimmedInput) return;
    startAnalysis(trimmedInput, contextText.trim(), apiKey, model, selectedMode);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (canSubmit) handleSubmit();
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 150) + 'px';
    }
  }, [inputText]);

  return (
    <div
      className={`h-full w-full flex flex-col items-center relative overflow-hidden ${isDarkMode ? "bg-transparent text-slate-200" : "bg-transparent text-slate-800"
        }`}
    >
      {/* ── 배경 장식 (Subdued) ─────────────────── */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div
          className="absolute -top-[10%] -left-[5%] w-[50%] h-[50%] bg-blue-500/10 blur-[120px] rounded-full"
        />
      </div>

      <div className="w-full max-w-5xl flex flex-col items-center flex-1 relative z-10 px-8 h-full">
        {/* ── 상단/중앙 콘텐츠 (타이틀 및 카드) ────────────────── */}
        <div className="flex-1 flex flex-col items-center justify-center w-full min-h-0 py-10">
          <div
            className="text-center mb-16 shrink-0"
          >
            <h1 className="text-5xl font-black mb-3 tracking-widest drop-shadow-sm">
              <span className="text-gradient">NAVIGATOR</span>
            </h1>
            <p className={`text-[17px] font-medium opacity-50 ${isDarkMode ? "text-slate-400" : "text-slate-600"}`}>
              아이디어를 구조화된 요구사항 명세서로 변환합니다
            </p>
          </div>

          {/* ── 모드 선택 (Grid) ───────────────── */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-4xl">
            {MODES.map((mode, idx) => (
              <div
                key={mode.key}
                onClick={() => setSelectedMode(mode.key)}
                className={`group flex flex-col items-center text-center p-6 rounded-3xl border cursor-pointer transition-colors duration-300 relative overflow-hidden ${selectedMode === mode.key
                    ? "glass-card border-[var(--accent)] shadow-2xl scale-[1.05] bg-[var(--accent)]/5"
                    : `glass-card border-white/5 hover:border-white/10 ${isDarkMode ? "bg-white/5" : "bg-slate-50 border-slate-100"}`
                  }`}
              >
                <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${mode.color} flex items-center justify-center mb-4 shadow-lg group-hover:scale-110 transition-transform`}>
                  <mode.icon className="text-white" size={28} />
                </div>
                <h3 className="text-lg font-bold mb-2">
                  {mode.label}
                </h3>
                <p className={`text-[13px] leading-relaxed opacity-50`}>
                  {mode.desc}
                </p>

                {selectedMode === mode.key && (
                  <div
                    className="absolute inset-0 border-2 border-[var(--accent)]/40 rounded-3xl pointer-events-none"
                  />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* ── 입력 영역 (Bottom Docked - Absolute 모드로 변경하여 레이아웃 고정) ─────────────────────── */}
        <div className="absolute bottom-12 w-full max-w-4xl px-8 z-50">
          <div
            className="flex flex-col gap-4"
          >
              {isReverseMode && !projectFolder && (
                <div
                  className="w-full overflow-hidden rounded-2xl border border-amber-500/20 bg-amber-500/5 px-6 py-3 text-[14px] text-amber-200/80 flex items-center justify-between backdrop-blur-md mb-4"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                    <span>분석할 프로젝트 폴더를 먼저 선택해 주세요.</span>
                  </div>
                  <button
                    onClick={selectAndScanFolder}
                    className="px-4 py-1.5 rounded-xl bg-amber-500/20 border border-amber-500/40 text-amber-200 font-bold text-xs hover:bg-amber-500/30 transition-all active:scale-95"
                  >
                    폴더 선택
                  </button>
                </div>
              )}

            <div className={`w-full relative rounded-full p-2 px-6 shadow-2xl flex items-center border border-white/5 ${isDarkMode ? "bg-[#161b22]/90 backdrop-blur-2xl" : "bg-white/90 backdrop-blur-xl border-slate-200"
              }`}>
              <div className="flex-1">
                <textarea
                  ref={textareaRef}
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={1}
                  placeholder="아이디어를 입력하세요..."
                  className="w-full bg-transparent border-none focus:ring-0 text-[16px] py-3 resize-none scrollbar-hide placeholder:text-slate-500"
                />
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => setShowContext(!showContext)}
                  className={`p-2 rounded-full transition-all ${showContext ? "bg-[var(--accent)] text-white shadow-lg" : "text-slate-500 hover:bg-white/10"
                    }`}
                  title="컨텍스트 추가"
                >
                  <Paperclip size={20} />
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={!selectedMode || !canSubmit}
                  className={`w-11 h-11 flex items-center justify-center rounded-full transition-all ${canSubmit
                      ? "bg-blue-600 text-white hover:bg-blue-500 shadow-lg"
                      : "bg-white/5 text-slate-700 cursor-not-allowed"
                    }`}
                >
                  <Send size={20} />
                </button>
              </div>
            </div>

            <footer className="w-full px-6 flex items-center justify-between text-[11px] font-medium text-slate-600/50 uppercase tracking-widest opacity-60">
              <div className="flex items-center gap-4">
                <span>NAVIGATOR PM PIPELINE</span>
                <div className="w-1 h-1 rounded-full bg-slate-800" />
                <span>STABLE RELEASE</span>
              </div>
              <span>PROMPT + ENTER TO PROCESS</span>
            </footer>
          </div>
        </div>
      </div>
    </div>
  );
}
