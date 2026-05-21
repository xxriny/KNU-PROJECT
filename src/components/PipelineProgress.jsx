import React, { useRef, useEffect, useState, useMemo } from "react";
import useAppStore from "../store/useAppStore";
import {
  Loader2, CheckCircle2, AlertCircle, Brain,
  Zap, GitBranch, Clock, Activity,
} from "lucide-react";

// ── 스텝 메타 ───────────────────────────────────────────
const STEP_META = {
  code_chunker:          { label: "코드 청킹",     phase: "scan", color: "slate" },
  code_embedding:        { label: "코드 임베딩",   phase: "scan", color: "slate" },
  idea_chat:             { label: "아이디어 탐색", phase: "pm",   color: "purple" },
  requirement_analyzer:  { label: "요구사항 분석", phase: "pm",   color: "cyan"   },
  stack_planner:         { label: "기술 스택 전략",phase: "pm",   color: "cyan"   },
  stack_crawling:        { label: "지식 탐색",     phase: "pm",   color: "amber"  },
  guardian:              { label: "정합성 검증",   phase: "pm",   color: "green"  },
  sa_merge_project:      { label: "프로젝트 병합", phase: "sa",   color: "teal"   },
  component_scheduler:   { label: "컴포넌트 설계", phase: "sa",   color: "teal"   },
  sa_unified_modeler:    { label: "통합 모델링",   phase: "sa",   color: "teal"   },
  sa_test_analysis:      { label: "테스트 전략",   phase: "sa",   color: "blue",  parallel: true },
  sa_project_structure:  { label: "프로젝트 구조", phase: "sa",   color: "violet",parallel: true },
};

const NODE_COLORS = {
  purple: { bg: "bg-purple-500/15", text: "text-purple-400", border: "border-purple-500/30", dot: "bg-purple-400" },
  cyan:   { bg: "bg-cyan-500/15",   text: "text-cyan-400",   border: "border-cyan-500/30",   dot: "bg-cyan-400"   },
  amber:  { bg: "bg-amber-500/15",  text: "text-amber-400",  border: "border-amber-500/30",  dot: "bg-amber-400"  },
  green:  { bg: "bg-emerald-500/15",text: "text-emerald-400",border: "border-emerald-500/30",dot: "bg-emerald-400"},
  teal:   { bg: "bg-teal-500/15",   text: "text-teal-400",   border: "border-teal-500/30",   dot: "bg-teal-400"   },
  blue:   { bg: "bg-blue-500/15",   text: "text-blue-400",   border: "border-blue-500/30",   dot: "bg-blue-400"   },
  violet: { bg: "bg-violet-500/15", text: "text-violet-400", border: "border-violet-500/30", dot: "bg-violet-400" },
  slate:  { bg: "bg-slate-500/10",  text: "text-slate-400",  border: "border-slate-500/20",  dot: "bg-slate-500"  },
};

const PHASE_META = {
  scan: { label: "SCAN", color: "text-slate-400", bar: "bg-slate-500" },
  pm:   { label: "PM 분석", color: "text-cyan-400", bar: "bg-cyan-500" },
  sa:   { label: "SA 설계", color: "text-teal-400", bar: "bg-teal-500" },
};

// 파이프라인 타입별 스텝 목록 ── 병렬 그룹은 배열로 묶음
const PIPELINE_STEPS_BY_TYPE = {
  analysis:        ["code_chunker","code_embedding","requirement_analyzer","stack_planner","stack_crawling","guardian"],
  analysis_create: ["code_chunker","code_embedding","requirement_analyzer","stack_planner","stack_crawling","guardian",
                    "sa_merge_project","component_scheduler","sa_unified_modeler",
                    ["sa_test_analysis","sa_project_structure"]],
  analysis_reverse:["code_chunker","code_embedding",
                    "sa_merge_project","component_scheduler","sa_unified_modeler",
                    ["sa_test_analysis","sa_project_structure"]],
  analysis_update: ["code_chunker","code_embedding","requirement_analyzer","stack_planner","stack_crawling","guardian",
                    "sa_merge_project","component_scheduler","sa_unified_modeler",
                    ["sa_test_analysis","sa_project_structure"]],
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

export default function PipelineProgress() {
  const { pipelineNodes, thinkingLog, pipelineStatus, pipelineError, pipelineType, isDarkMode } = useAppStore();
  const logEndRef = useRef(null);
  const elapsed = useElapsed(pipelineStatus === "running");

  const rawSteps = PIPELINE_STEPS_BY_TYPE[pipelineType] || PIPELINE_STEPS_BY_TYPE.analysis_create;

  // 완료 스텝 수 계산 (병렬 그룹 포함)
  const { totalCount, doneCount } = useMemo(() => {
    let total = 0; let done = 0;
    rawSteps.forEach(s => {
      if (Array.isArray(s)) {
        total += s.length;
        s.forEach(k => { if (pipelineNodes[k] === "done") done++; });
      } else {
        total++;
        if (pipelineNodes[s] === "done") done++;
      }
    });
    return { totalCount: total, doneCount: done };
  }, [rawSteps, pipelineNodes]);

  const progressPct = totalCount ? Math.round((doneCount / totalCount) * 100) : 0;
  const isDone = pipelineStatus === "done";
  const isError = pipelineStatus === "error";

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [thinkingLog]);

  return (
    <div className="h-full w-full flex flex-col overflow-hidden">
      {/* ── 상단 헤더 ─────────────────────────────── */}
      <div className={`shrink-0 pl-5 pr-12 py-3 flex items-center gap-4 border-b ${
        isDarkMode ? "border-white/5 bg-white/[0.02]" : "border-slate-100 bg-white/60"
      }`}>
        {/* 상태 아이콘 */}
        <div className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 ${
          isError ? "bg-red-500/15" : isDone ? "bg-emerald-500/15" : "bg-blue-500/15"
        }`}>
          {isError
            ? <AlertCircle size={16} className="text-red-400" />
            : isDone
              ? <CheckCircle2 size={16} className="text-emerald-400" />
              : <Loader2 size={16} className="text-blue-400 animate-spin" />}
        </div>

        {/* 진행바 + 퍼센트 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1.5">
            <span className={`text-[11px] font-bold uppercase tracking-wider ${
              isDarkMode ? "text-slate-400" : "text-slate-500"
            }`}>
              {isDone ? "분석 완료" : isError ? "오류 발생" : "분석 진행 중..."}
            </span>
            <div className="flex items-center gap-3">
              {pipelineStatus === "running" && (
                <span className={`flex items-center gap-1 text-[11px] font-mono ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>
                  <Clock size={10} />
                  {fmtElapsed(elapsed)}
                </span>
              )}
              <span className={`text-[11px] font-bold font-mono ${
                isDone ? "text-emerald-400" : isError ? "text-red-400" : "text-blue-400"
              }`}>
                {doneCount}/{totalCount}
              </span>
            </div>
          </div>
          <div className={`h-1.5 rounded-full overflow-hidden ${isDarkMode ? "bg-white/5" : "bg-slate-100"}`}>
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                isError ? "bg-red-500" : isDone ? "bg-emerald-500" : "bg-gradient-to-r from-blue-500 to-indigo-500"
              }`}
              style={{ width: `${isDone ? 100 : progressPct}%` }}
            />
          </div>
        </div>
      </div>

      {/* ── 본문 ─────────────────────────────────── */}
      <div className="flex-1 min-h-0 flex overflow-hidden gap-3 p-3">
        {/* 좌측: 스텝 타임라인 */}
        <div className={`w-64 shrink-0 flex flex-col rounded-xl overflow-hidden border ${
          isDarkMode ? "bg-white/[0.03] border-white/5" : "bg-white border-slate-100 shadow-sm"
        }`}>
          <div className={`px-4 py-2.5 border-b flex items-center gap-2 ${isDarkMode ? "border-white/5" : "border-slate-100"}`}>
            <Zap size={12} className="text-blue-400" />
            <span className={`text-[10px] font-black uppercase tracking-[0.2em] ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>
              Pipeline Steps
            </span>
          </div>
          <div className="flex-1 overflow-y-auto py-3 px-3 space-y-0.5">
            <StepList steps={rawSteps} pipelineNodes={pipelineNodes} isDarkMode={isDarkMode} />
            {pipelineError && (
              <div className="mt-3 p-3 bg-red-500/10 border border-red-500/25 rounded-lg">
                <p className="text-[11px] text-red-400 font-semibold mb-1 flex items-center gap-1.5">
                  <AlertCircle size={11} /> 오류
                </p>
                <p className="text-[10px] text-red-300/70 leading-relaxed">{pipelineError}</p>
              </div>
            )}
          </div>
        </div>

        {/* 우측: Thinking Log */}
        <div className={`flex-1 min-w-0 flex flex-col rounded-xl overflow-hidden border ${
          isDarkMode ? "bg-white/[0.03] border-white/5" : "bg-white border-slate-100 shadow-sm"
        }`}>
          <div className={`px-4 py-2.5 border-b flex items-center justify-between ${isDarkMode ? "border-white/5" : "border-slate-100"}`}>
            <div className="flex items-center gap-2">
              <Brain size={12} className="text-purple-400" />
              <span className={`text-[10px] font-black uppercase tracking-[0.2em] ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>
                Agent Reasoning
              </span>
            </div>
            {thinkingLog.length > 0 && (
              <span className={`text-[10px] font-bold font-mono px-1.5 py-0.5 rounded-md ${
                isDarkMode ? "bg-purple-500/10 text-purple-400" : "bg-purple-50 text-purple-500"
              }`}>
                {thinkingLog.length}
              </span>
            )}
          </div>
          <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-1.5">
            {thinkingLog.length === 0 ? (
              <EmptyLog isDarkMode={isDarkMode} />
            ) : (
              thinkingLog.map((log, idx) => (
                <ThinkingEntry key={idx} log={log} isLatest={idx === thinkingLog.length - 1} isDarkMode={isDarkMode} />
              ))
            )}
            <div ref={logEndRef} />
          </div>
        </div>
      </div>
    </div>
  );
}

// ── 스텝 타임라인 ────────────────────────────────────────
function StepList({ steps, pipelineNodes, isDarkMode }) {
  let prevPhase = null;
  const elements = [];

  steps.forEach((step, idx) => {
    const isParallelGroup = Array.isArray(step);

    if (isParallelGroup) {
      // 병렬 그룹 헤더
      const phase = STEP_META[step[0]]?.phase;
      if (phase && phase !== prevPhase) {
        elements.push(<PhaseLabel key={`phase-${phase}-${idx}`} phase={phase} />);
        prevPhase = phase;
      }
      elements.push(
        <ParallelGroup key={`pg-${idx}`} keys={step} pipelineNodes={pipelineNodes} isDarkMode={isDarkMode} />
      );
    } else {
      const meta = STEP_META[step] || { label: step, phase: "pm", color: "slate" };
      if (meta.phase !== prevPhase) {
        elements.push(<PhaseLabel key={`phase-${meta.phase}-${idx}`} phase={meta.phase} />);
        prevPhase = meta.phase;
      }
      const status = pipelineNodes[step] || "pending";
      const isLast = idx === steps.length - 1;
      elements.push(
        <StepRow
          key={step}
          label={meta.label}
          color={meta.color}
          status={status}
          showConnector={!isLast}
          isDarkMode={isDarkMode}
        />
      );
    }
  });

  return <>{elements}</>;
}

function PhaseLabel({ phase }) {
  const meta = PHASE_META[phase] || PHASE_META.pm;
  return (
    <div className={`flex items-center gap-1.5 px-1 py-1.5 mt-1`}>
      <span className={`w-1 h-1 rounded-full ${meta.bar}`} />
      <span className={`text-[9px] font-black uppercase tracking-[0.18em] ${meta.color}`}>
        {meta.label}
      </span>
    </div>
  );
}

function StepRow({ label, color, status, showConnector, isDarkMode }) {
  const c = NODE_COLORS[color] || NODE_COLORS.slate;
  return (
    <div className="flex items-stretch gap-2 pl-2">
      {/* 타임라인 선 */}
      <div className="flex flex-col items-center w-5 shrink-0">
        <StatusDot status={status} color={color} />
        {showConnector && (
          <div className={`w-[1px] flex-1 mt-0.5 ${
            status === "done" ? c.dot.replace("bg-", "bg-") + " opacity-40" : isDarkMode ? "bg-white/8" : "bg-slate-200"
          }`} />
        )}
      </div>
      {/* 라벨 */}
      <div className={`flex-1 pb-2 flex items-start`}>
        <span className={`text-[12px] font-semibold leading-tight pt-0.5 ${
          status === "pending"
            ? isDarkMode ? "text-slate-600" : "text-slate-300"
            : status === "running"
              ? c.text
              : status === "done"
                ? isDarkMode ? "text-slate-300" : "text-slate-600"
                : "text-red-400"
        }`}>
          {label}
        </span>
        {status === "running" && (
          <span className={`ml-auto shrink-0 text-[10px] font-bold ${c.text} animate-pulse`}>···</span>
        )}
      </div>
    </div>
  );
}

function ParallelGroup({ keys, pipelineNodes, isDarkMode }) {
  const allDone = keys.every(k => pipelineNodes[k] === "done");
  const anyRunning = keys.some(k => pipelineNodes[k] === "running");
  return (
    <div className="pl-2 pb-2">
      {/* fork 인디케이터 */}
      <div className="flex items-center gap-1.5 mb-1.5 pl-[18px]">
        <GitBranch size={10} className={anyRunning ? "text-blue-400" : allDone ? "text-emerald-400 opacity-50" : "text-slate-600"} />
        <span className={`text-[9px] font-bold uppercase tracking-wider ${
          anyRunning ? "text-blue-400" : allDone ? "text-slate-500" : "text-slate-600"
        }`}>parallel</span>
      </div>
      {/* 두 카드 나란히 */}
      <div className="grid grid-cols-2 gap-1.5 pl-[18px]">
        {keys.map(k => {
          const meta = STEP_META[k] || { label: k, color: "blue" };
          const c = NODE_COLORS[meta.color] || NODE_COLORS.blue;
          const status = pipelineNodes[k] || "pending";
          return (
            <div key={k} className={`rounded-lg px-2.5 py-2 border transition-all ${
              status === "running"
                ? `${c.bg} ${c.border}`
                : status === "done"
                  ? isDarkMode ? "bg-white/[0.04] border-white/5 opacity-60" : "bg-slate-50 border-slate-100 opacity-70"
                  : isDarkMode ? "bg-transparent border-white/5 opacity-35" : "bg-slate-50/50 border-slate-100 opacity-40"
            }`}>
              <div className="flex items-center gap-1.5 mb-1">
                <StatusDot status={status} color={meta.color} small />
              </div>
              <p className={`text-[10px] font-bold leading-tight ${
                status === "pending" ? isDarkMode ? "text-slate-600" : "text-slate-400"
                : status === "running" ? c.text
                : isDarkMode ? "text-slate-400" : "text-slate-500"
              }`}>{meta.label}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function StatusDot({ status, color, small = false }) {
  const c = NODE_COLORS[color] || NODE_COLORS.slate;
  const sz = small ? "w-3 h-3" : "w-4 h-4";
  if (status === "running") {
    return (
      <span className={`relative flex ${sz} shrink-0`}>
        <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${c.dot} opacity-40`} />
        <span className={`relative inline-flex rounded-full ${sz} ${c.dot}`} />
      </span>
    );
  }
  if (status === "done") {
    return <CheckCircle2 size={small ? 12 : 14} className="text-emerald-400 shrink-0" />;
  }
  if (status === "error") {
    return <AlertCircle size={small ? 12 : 14} className="text-red-400 shrink-0" />;
  }
  return (
    <span className={`${sz} rounded-full border shrink-0 ${
      color === "slate" ? "border-slate-700" : `border-${color}-800`
    } opacity-30`} />
  );
}

// ── Thinking Log 엔트리 ──────────────────────────────────
const LOG_NODE_COLORS = {
  requirement_analyzer: { bg: "bg-cyan-500/15",   text: "text-cyan-400",    short: "REQ" },
  stack_planner:        { bg: "bg-indigo-500/15",  text: "text-indigo-400",  short: "STACK" },
  stack_crawling:       { bg: "bg-amber-500/15",   text: "text-amber-400",   short: "CRAWL" },
  guardian:             { bg: "bg-green-500/15",   text: "text-emerald-400", short: "GUARD" },
  sa_merge_project:     { bg: "bg-teal-500/15",    text: "text-teal-400",    short: "MERGE" },
  component_scheduler:  { bg: "bg-teal-500/15",    text: "text-teal-400",    short: "COMP" },
  unified_modeler:      { bg: "bg-blue-500/15",    text: "text-blue-400",    short: "MODEL" },
  sa_unified_modeler:   { bg: "bg-blue-500/15",    text: "text-blue-400",    short: "MODEL" },
  sa_test_analysis:     { bg: "bg-blue-500/15",    text: "text-blue-400",    short: "TEST" },
  sa_project_structure: { bg: "bg-violet-500/15",  text: "text-violet-400",  short: "STRUCT" },
  idea_chat:            { bg: "bg-purple-500/15",  text: "text-purple-400",  short: "IDEA" },
};

const DEFAULT_LOG_COLOR = { bg: "bg-slate-500/10", text: "text-slate-400", short: "NODE" };

function ThinkingEntry({ log, isLatest, isDarkMode }) {
  const [expanded, setExpanded] = useState(false);
  const c = LOG_NODE_COLORS[log.node] || DEFAULT_LOG_COLOR;
  const text = log.text || log.thinking || "";
  const isLong = text.length > 200;

  return (
    <div className={`rounded-lg border transition-all ${
      isLatest && isDarkMode
        ? "bg-white/[0.05] border-white/8"
        : isDarkMode
          ? "bg-white/[0.025] border-white/4"
          : isLatest
            ? "bg-slate-50 border-slate-200"
            : "bg-white border-slate-100"
    }`}>
      {/* 헤더 */}
      <div className={`flex items-center gap-2 px-3 py-2 border-b ${
        isDarkMode ? "border-white/4" : "border-slate-100"
      }`}>
        <span className={`text-[9px] font-black px-1.5 py-0.5 rounded-md uppercase tracking-wider ${c.bg} ${c.text}`}>
          {c.short}
        </span>
        <span className={`text-[10px] font-mono ${isDarkMode ? "text-slate-600" : "text-slate-400"}`}>
          {log.timestamp ? new Date(log.timestamp).toLocaleTimeString("ko", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : ""}
        </span>
        {isLatest && (
          <span className="ml-auto w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse shrink-0" />
        )}
      </div>
      {/* 본문 */}
      <div
        className={`px-3 py-2.5 cursor-pointer ${isLong && !expanded ? "max-h-[72px] overflow-hidden" : ""}`}
        onClick={() => isLong && setExpanded(v => !v)}
      >
        <p className={`text-[12px] leading-relaxed whitespace-pre-wrap ${
          isDarkMode ? "text-slate-300" : "text-slate-600"
        }`}>
          {text}
        </p>
      </div>
      {isLong && (
        <button
          onClick={() => setExpanded(v => !v)}
          className={`w-full text-center text-[10px] font-bold pb-1.5 transition-colors ${
            isDarkMode ? "text-slate-600 hover:text-slate-400" : "text-slate-300 hover:text-slate-500"
          }`}
        >
          {expanded ? "▲ 접기" : "▼ 더 보기"}
        </button>
      )}
    </div>
  );
}

function EmptyLog({ isDarkMode }) {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-3 py-8">
      <div className="relative">
        <div className={`w-12 h-12 rounded-2xl flex items-center justify-center ${isDarkMode ? "bg-white/5" : "bg-slate-100"}`}>
          <Activity size={22} className={isDarkMode ? "text-slate-600" : "text-slate-300"} />
        </div>
        <span className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-blue-500/20 flex items-center justify-center">
          <Loader2 size={11} className="text-blue-400 animate-spin" />
        </span>
      </div>
      <div className="text-center">
        <p className={`text-[12px] font-bold ${isDarkMode ? "text-slate-500" : "text-slate-400"}`}>
          에이전트 추론 대기 중
        </p>
        <p className={`text-[11px] mt-0.5 ${isDarkMode ? "text-slate-600" : "text-slate-300"}`}>
          첫 번째 노드가 시작되면 로그가 표시됩니다
        </p>
      </div>
    </div>
  );
}
