/**
 * HomeScreen — 파이프라인 미실행 시 표시되는 홈 화면
 * 모드 선택 카드 (신규 기획 / 기능 확장 / 역공학) + 입력 영역
 */

import React, { useState } from "react";
import useAppStore from "../store/useAppStore";
import { Sparkles, Layers, ScanSearch, Send, Paperclip } from "lucide-react";

const MODES = [
  {
    key: "create",
    label: "신규 기획",
    desc: "아이디어를 구조화된 요구사항으로 변환",
    icon: Sparkles,
    color: "from-blue-500 to-cyan-500",
    borderColor: "border-blue-500",
  },
  {
    key: "update",
    label: "기능 확장",
    desc: "기존 프로젝트에 새 기능 요구사항 추가",
    icon: Layers,
    color: "from-emerald-500 to-teal-500",
    borderColor: "border-emerald-500",
  },
  {
    key: "reverse",
    label: "역공학",
    desc: "기존 시스템에서 RTM을 역추출",
    icon: ScanSearch,
    color: "from-purple-500 to-pink-500",
    borderColor: "border-purple-500",
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
  } = useAppStore();
  const [inputText, setInputText] = useState("");
  const [contextText, setContextText] = useState("");
  const [showContext, setShowContext] = useState(false);

  const isReverseMode = selectedMode === "reverse";
  const trimmedInput = inputText.trim();
  const canSubmit = isReverseMode ? Boolean(projectFolder) : Boolean(trimmedInput);

  const handleSubmit = () => {
    if (isReverseMode) {
      if (!projectFolder) return;
      startAnalysis(trimmedInput, contextText.trim(), apiKey, model, selectedMode);
      return;
    }

    if (!trimmedInput) return;
    startAnalysis(trimmedInput, contextText.trim(), apiKey, model, selectedMode);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="h-full flex flex-col items-center justify-center bg-slate-950 px-8">
      {/* ── 타이틀 ────────────────────────── */}
      <div className="text-center mb-8">
        <h1 className="text-2xl font-bold text-slate-200 mb-2">
          PM Agent Pipeline
        </h1>
        <p className="text-sm text-slate-500">
          아이디어를 구조화된 요구사항 명세서로 변환합니다
        </p>
      </div>

      {/* ── 모드 카드 ─────────────────────── */}
      <div className="flex gap-4 mb-8">
        {MODES.map((mode) => {
          const Icon = mode.icon;
          const isSelected = selectedMode === mode.key;
          return (
            <button
              key={mode.key}
              onClick={() => setSelectedMode(mode.key)}
              className={`relative w-48 p-4 rounded-xl border-2 transition-all duration-200 text-left ${
                isSelected
                  ? `${mode.borderColor} bg-slate-800/80 shadow-lg scale-[1.02]`
                  : "border-slate-700/50 bg-slate-900/50 hover:border-slate-600 hover:bg-slate-800/50"
              }`}
            >
              <div
                className={`w-10 h-10 rounded-lg bg-gradient-to-br ${mode.color} flex items-center justify-center mb-3`}
              >
                <Icon size={20} className="text-white" />
              </div>
              <h3 className="text-sm font-semibold text-slate-200 mb-1">
                {mode.label}
              </h3>
              <p className="text-[12px] text-slate-500 leading-relaxed">
                {mode.desc}
              </p>
              {isSelected && (
                <div
                  className={`absolute top-2 right-2 w-2 h-2 rounded-full bg-gradient-to-br ${mode.color}`}
                />
              )}
            </button>
          );
        })}
      </div>

      {/* ── 입력 영역 ─────────────────────── */}
      <div className="w-full max-w-2xl">
        {isReverseMode && !projectFolder && (
          <div className="mb-3 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[12px] text-amber-200">
            먼저 폴더를 선택하세요.
            <button
              onClick={selectAndScanFolder}
              className="ml-2 inline-flex rounded-md border border-amber-400/40 px-2 py-0.5 text-[12px] text-amber-100 hover:bg-amber-400/10 transition-colors"
            >
              폴더 선택
            </button>
          </div>
        )}

        {/* 컨텍스트 토글 */}
        {showContext && (
          <div className="mb-2">
            <textarea
              value={contextText}
              onChange={(e) => setContextText(e.target.value)}
              placeholder="기존 프로젝트 컨텍스트 (코드, 문서 등)를 붙여넣으세요..."
              className="w-full h-24 px-4 py-3 text-sm bg-slate-900 border border-slate-700 rounded-lg text-slate-300 placeholder-slate-600 resize-none focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>
        )}

        <div className="relative flex items-end gap-2">
          <div className="flex-1 relative">
            <textarea
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                selectedMode
                  ? isReverseMode
                    ? `[${MODES.find((m) => m.key === selectedMode)?.label}] 선택사항: 분석 힌트를 입력하세요...`
                    : `[${MODES.find((m) => m.key === selectedMode)?.label}] 아이디어를 입력하세요...`
                  : "모드를 선택하고 아이디어를 입력하세요..."
              }
              rows={2}
              className="w-full px-4 py-3 pr-24 text-sm bg-slate-900 border border-slate-700 rounded-xl text-slate-300 placeholder-slate-600 resize-none focus:outline-none focus:border-blue-500 transition-colors"
            />
            <div className="absolute right-2 bottom-2 flex items-center gap-1">
              <button
                onClick={() => setShowContext(!showContext)}
                className={`p-1.5 rounded-lg transition-colors ${
                  showContext
                    ? "text-blue-400 bg-blue-500/10"
                    : "text-slate-500 hover:text-slate-300"
                }`}
                title="프로젝트 컨텍스트 첨부"
              >
                <Paperclip size={14} />
              </button>
              <button
                onClick={handleSubmit}
                disabled={!selectedMode || !canSubmit}
                className="p-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                <Send size={14} />
              </button>
            </div>
          </div>
        </div>

        <p className="text-[12px] text-slate-600 mt-2 text-center">
          모드 선택 후 Enter로 전송 | Shift+Enter로 줄바꿈
        </p>
      </div>
    </div>
  );
}
