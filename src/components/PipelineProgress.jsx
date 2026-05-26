import React, { useRef, useEffect, useState, useMemo } from "react";
import useAppStore from "../store/useAppStore";
import {
  CheckCircle2, AlertCircle, ChevronDown, ChevronUp,
} from "lucide-react";

// ── 스텝 메타 ───────────────────────────────────────────
const STEP_META = {
  idea_chat:             { label: "아이디어 탐색", phase: "pm"   },
  requirement_analyzer:  { label: "요구사항 분석", phase: "pm"   },
  stack_planner:         { label: "기술 스택 전략",phase: "pm"   },
  sa_merge_project:      { label: "프로젝트 병합", phase: "sa"   },
  component_scheduler:   { label: "컴포넌트 설계", phase: "sa"   },
  sa_unified_modeler:    { label: "통합 모델링",   phase: "sa"   },
  sa_test_analysis:      { label: "테스트 전략",   phase: "sa"   },
  sa_project_structure:  { label: "프로젝트 구조", phase: "sa"   },
};

const PIPELINE_STEPS_BY_TYPE = {
  analysis:        ["requirement_analyzer","stack_planner"],
  analysis_create: ["requirement_analyzer","stack_planner",
                    "sa_merge_project","component_scheduler","sa_unified_modeler","sa_test_analysis","sa_project_structure"],
  analysis_reverse:["sa_merge_project","component_scheduler","sa_unified_modeler","sa_test_analysis","sa_project_structure"],
  analysis_update: ["requirement_analyzer","stack_planner",
                    "sa_merge_project","component_scheduler","sa_unified_modeler","sa_test_analysis","sa_project_structure"],
  idea_chat:       ["idea_chat"],
};

function useElapsed(running) {
  const [elapsed, setElapsed] = useState(0);
  const start = useRef(Date.now());
  useEffect(() => {
    if (!running) { setElapsed(0); start.current = Date.now(); return; }
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - start.current) / 1000)), 1000);
    return () => clearInterval(id);
  }, [running]);
  return elapsed;
}

function fmtElapsed(s) {
  const m = Math.floor(s / 60);
  return m > 0 ? `${m}분 ${s % 60}초` : `${s}초`;
}

// Gemini 스타일 스피너
function ThinkingSpinner() {
  return (
    <span className="inline-flex items-end gap-[3px] h-4 ml-1">
      {[0, 1, 2].map(i => (
        <span
          key={i}
          className="w-[3px] rounded-full bg-blue-400"
          style={{
            animation: `thinking-bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
            height: "10px",
          }}
        />
      ))}
    </span>
  );
}

export default function PipelineProgress() {
  const { pipelineNodes, thinkingLog, pipelineStatus, pipelineError, pipelineType, isDarkMode } = useAppStore();
  const bottomRef = useRef(null);
  const elapsed = useElapsed(pipelineStatus === "running");
  const [thinkingOpen, setThinkingOpen] = useState(true);

  const rawSteps = (PIPELINE_STEPS_BY_TYPE[pipelineType] || PIPELINE_STEPS_BY_TYPE.analysis_create).flat();

  const { totalCount, doneCount } = useMemo(() => {
    const total = rawSteps.length;
    const done = rawSteps.filter(k => pipelineNodes[k] === "done").length;
    return { totalCount: total, doneCount: done };
  }, [rawSteps, pipelineNodes]);

  const currentStep = rawSteps.find(k => pipelineNodes[k] === "running");
  const currentLabel = currentStep ? (STEP_META[currentStep]?.label ?? currentStep) : null;

  const isDone = pipelineStatus === "done";
  const isError = pipelineStatus === "error";
  const progressPct = totalCount ? Math.round((doneCount / totalCount) * 100) : 0;

  useEffect(() => {
    if (thinkingOpen) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [thinkingLog, thinkingOpen]);

  return (
    <>
      {/* keyframes injection */}
      <style>{`
        @keyframes thinking-bounce {
          0%, 80%, 100% { transform: scaleY(0.4); opacity: 0.4; }
          40% { transform: scaleY(1); opacity: 1; }
        }
      `}</style>

      <div className="h-full w-full flex flex-col overflow-hidden">
        {/* ── 진행바 (slim) ───────────────────────── */}
        <div className={`shrink-0 ${isDarkMode ? "bg-white/[0.02]" : "bg-white/60"}`}>
          <div className={`h-[2px] ${isDarkMode ? "bg-white/5" : "bg-slate-100"}`}>
            <div
              className={`h-full transition-all duration-700 ${
                isError ? "bg-red-500" : isDone ? "bg-emerald-500" : "bg-gradient-to-r from-blue-500 via-indigo-500 to-blue-400"
              }`}
              style={{ width: `${isDone ? 100 : progressPct}%` }}
            />
          </div>
        </div>

        {/* ── 고정 상단 영역 (헤더 + pill) ───────── */}
        <div className="shrink-0 px-6 pt-5 pb-4 space-y-4">
          {/* 현재 상태 헤더 */}
          <div className="flex items-center gap-3">
            {isDone ? (
              <CheckCircle2 size={18} className="text-emerald-400 shrink-0" />
            ) : isError ? (
              <AlertCircle size={18} className="text-red-400 shrink-0" />
            ) : (
              <span className="relative flex w-4 h-4 shrink-0">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-40" />
                <span className="relative inline-flex rounded-full w-4 h-4 bg-blue-500" />
              </span>
            )}
            <span className={`text-[15px] font-bold ${isDarkMode ? "text-white" : "text-slate-800"}`}>
              {isDone
                ? "분석 완료"
                : isError
                  ? "오류 발생"
                  : currentLabel
                    ? <>{currentLabel}<ThinkingSpinner /></>
                    : <>분석 준비 중<ThinkingSpinner /></>
              }
            </span>
            <span className={`ml-auto text-[12px] font-mono shrink-0 ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>
              {isDone ? `${fmtElapsed(elapsed)} 완료` : pipelineStatus === "running" ? fmtElapsed(elapsed) : ""}
              <span className={`ml-2 font-bold ${isDone ? "text-emerald-400" : "text-blue-400"}`}>
                {doneCount}/{totalCount}
              </span>
            </span>
          </div>

          {/* 스텝 pill 목록 */}
          <div className="flex flex-wrap gap-1.5">
            {rawSteps.map(key => {
              const status = pipelineNodes[key] || "pending";
              const label = STEP_META[key]?.label ?? key;
              return (
                <span
                  key={key}
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold transition-all duration-300 ${
                    status === "done"
                      ? isDarkMode
                        ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/20"
                        : "bg-emerald-50 text-emerald-600 border border-emerald-200"
                      : status === "running"
                        ? isDarkMode
                          ? "bg-blue-500/20 text-blue-300 border border-blue-400/30"
                          : "bg-blue-50 text-blue-600 border border-blue-200"
                        : isDarkMode
                          ? "bg-white/[0.04] text-slate-500 border border-white/5"
                          : "bg-slate-50 text-slate-400 border border-slate-100"
                  }`}
                >
                  {status === "done" && <CheckCircle2 size={10} />}
                  {status === "running" && (
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                  )}
                  {label}
                </span>
              );
            })}
          </div>

          {/* 오류 표시 */}
          {isError && pipelineError && (
            <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20">
              <p className="text-[12px] text-red-400 leading-relaxed">{pipelineError}</p>
            </div>
          )}
        </div>

        {/* ── 스크롤 가능한 추론 영역 ─────────────── */}
        <div className="flex-1 min-h-0 overflow-y-auto px-6 pb-5">
          {/* Thinking 섹션 (Gemini 스타일 접기/펼치기) */}
          {thinkingLog.length > 0 && (
            <div className={`rounded-2xl border overflow-hidden ${
              isDarkMode ? "border-white/8 bg-white/[0.025]" : "border-slate-200 bg-slate-50/60"
            }`}>
              {/* 헤더 토글 */}
              <button
                onClick={() => setThinkingOpen(v => !v)}
                className={`w-full flex items-center gap-2.5 px-4 py-3 text-left transition-colors ${
                  isDarkMode ? "hover:bg-white/[0.03]" : "hover:bg-slate-100/60"
                }`}
              >
                <span className={`text-[11px] font-black uppercase tracking-[0.18em] ${isDarkMode ? "text-slate-400" : "text-slate-500"}`}>
                  추론 과정
                </span>
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${
                  isDarkMode ? "bg-white/5 text-slate-500" : "bg-slate-200 text-slate-500"
                }`}>
                  {thinkingLog.length}
                </span>
                <span className="ml-auto">
                  {thinkingOpen
                    ? <ChevronUp size={13} className={isDarkMode ? "text-slate-500" : "text-slate-400"} />
                    : <ChevronDown size={13} className={isDarkMode ? "text-slate-500" : "text-slate-400"} />
                  }
                </span>
              </button>

              {/* 스트리밍 로그 */}
              {thinkingOpen && (
                <div className={`px-5 pb-5 pt-1 space-y-4 border-t ${isDarkMode ? "border-white/5" : "border-slate-200"}`}>
                  {thinkingLog.map((log, idx) => {
                    const text = log.text || log.thinking || "";
                    const isLatest = idx === thinkingLog.length - 1;
                    const label = STEP_META[log.node]?.label ?? log.node ?? "";
                    return (
                      <div key={idx} className="space-y-1">
                        {(idx === 0 || thinkingLog[idx - 1]?.node !== log.node) && label && (
                          <p className={`text-[10px] font-bold uppercase tracking-wider ${isDarkMode ? "text-slate-600" : "text-slate-400"}`}>
                            {label}
                          </p>
                        )}
                        <p className={`text-[13px] leading-[1.75] whitespace-pre-wrap ${
                          isDarkMode ? "text-slate-300" : "text-slate-600"
                        } ${isLatest && pipelineStatus === "running" ? "after:content-['▌'] after:animate-pulse after:text-blue-400" : ""}`}>
                          {text}
                        </p>
                      </div>
                    );
                  })}
                  <div ref={bottomRef} />
                </div>
              )}
            </div>
          )}

          {/* 로그 없고 실행 중일 때 대기 표시 */}
          {thinkingLog.length === 0 && pipelineStatus === "running" && (
            <div className={`flex items-center gap-3 px-4 py-3 rounded-2xl border ${
              isDarkMode ? "border-white/8 bg-white/[0.025]" : "border-slate-200 bg-slate-50/60"
            }`}>
              <ThinkingSpinner />
              <span className={`text-[13px] ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>
                첫 번째 노드 시작 대기 중...
              </span>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
