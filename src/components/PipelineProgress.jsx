import React, { useRef, useEffect } from "react";
import useAppStore from "../store/useAppStore";
import {
  Loader2,
  CheckCircle2,
  Circle,
  AlertCircle,
  Brain,
  Sparkles,
} from "lucide-react";

const SCAN_STEPS = [
  { key: "system_scan", label: "프로젝트 분석", desc: "소스 코드 구조 및 프레임워크 스캔" },
];

const PM_PIPELINE_STEPS = [
  { key: "requirement_analyzer", label: "요구사항 분석", desc: "아이디어를 원자 단위 요구사항으로 정밀 분석" },
  { key: "stack_planner", label: "기술 스택 전략", desc: "요구사항별 최적의 라이브러리 및 프레임워크 선정" },
  { key: "stack_crawling", label: "지능형 지식 탐색", desc: "부족한 기술 지식을 외부 레지스트리에서 자율 검색" },
  { key: "guardian", label: "기술 정합성 검증", desc: "선정된 스택의 호환성, 보안성 및 품질 최종 검토" },
  { key: "pm_analysis", label: "통합 분석 및 번들링", desc: "분석 결과 통합 및 최종 PM_BUNDLE 스펙 확정" },
];

const SA_PIPELINE_STEPS = [
  { key: "sa_merge_project",    label: "프로젝트 병합",      desc: "PM 산출물과 코드 분석 결과 통합" },
  { key: "component_scheduler", label: "컴포넌트 설계",      desc: "시스템 컴포넌트 구조 및 역할 정의" },
  { key: "api_data_modeler",    label: "API & 데이터 모델링", desc: "엔드포인트 및 DB 스키마 설계" },
  { key: "sa_analysis",         label: "아키텍처 검증 (QA)",  desc: "설계 정합성 분석 및 Gap 탐지" },
  { key: "sa_embedding",        label: "SA 결과 저장",        desc: "아키텍처 산출물 임베딩 및 영구 저장" },
];

const PIPELINE_STEPS_BY_TYPE = {
  analysis: [...SCAN_STEPS, ...PM_PIPELINE_STEPS],
  analysis_create: [...SCAN_STEPS, ...PM_PIPELINE_STEPS, ...SA_PIPELINE_STEPS],
  analysis_reverse: [...SCAN_STEPS, ...SA_PIPELINE_STEPS],
  analysis_update: [...SCAN_STEPS, ...PM_PIPELINE_STEPS, ...SA_PIPELINE_STEPS],
  idea_chat: [
    { key: "idea_chat", label: "아이디어 탐색", desc: "아이디어를 구체화하고 다음 분석 방향을 제안" },
  ],
};

export default function PipelineProgress() {
  const { pipelineNodes, thinkingLog, pipelineStatus, pipelineError, pipelineType, isDarkMode } = useAppStore();
  const logEndRef = useRef(null);
  const steps = PIPELINE_STEPS_BY_TYPE[pipelineType] || PM_PIPELINE_STEPS;

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [thinkingLog]);

  return (
    <div className="h-full w-full flex bg-transparent text-sm overflow-hidden p-4 gap-4">
      {/* ── 좌측: 파이프라인 스텝 ──────────── */}
      <div className="w-80 shrink-0 glass-panel rounded-2xl flex flex-col min-h-0 shadow-premium overflow-hidden">
        <div className="p-5 border-b border-white/5 bg-white/5">
          <h3 className="text-[12px] font-bold text-slate-500 uppercase tracking-[0.2em] flex items-center gap-2">
            <Sparkles size={14} className="text-blue-400" />
            Pipeline Engine
          </h3>
        </div>
        <div className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-2 min-h-0">
          {steps.map((step) => {
            const status = pipelineNodes[step.key] || "pending";
            return (
              <StepItem
                key={step.key}
                label={step.label}
                desc={step.desc}
                status={status}
                isDarkMode={isDarkMode}
              />
            );
          })}

          {pipelineError && (
            <div 
              className="mt-4 p-4 bg-red-500/10 border border-red-500/30 rounded-xl"
            >
              <div className="flex items-center gap-2 text-[13px] text-red-400 font-bold mb-1">
                <AlertCircle size={14} />
                오류 발생
              </div>
              <p className="text-[12px] text-red-300/80 leading-relaxed">
                {pipelineError}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ── 우측: Thinking Log ─────────────── */}
      <div className="flex-1 min-w-0 flex flex-col glass-panel rounded-2xl shadow-premium overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-white/5">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center">
              <Brain size={18} className="text-purple-400" />
            </div>
            <div>
              <span className={`text-[15px] font-bold ${isDarkMode ? "text-slate-200" : "text-slate-800"}`}>
                Thinking Log
              </span>
              <div className="text-[11px] text-slate-500 uppercase tracking-widest font-medium">
                Real-time Agent Reasoning Stream
              </div>
            </div>
          </div>
          <span className="text-[13px] font-mono text-purple-400/80 bg-purple-500/10 px-2 py-0.5 rounded-lg border border-purple-500/20">
            {thinkingLog.length} entries
          </span>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto p-6 space-y-4 custom-scrollbar">
          {thinkingLog.length === 0 ? (
            <div 
              className="flex flex-col items-center justify-center h-full space-y-4"
            >
              <div className="relative">
                <Loader2 size={40} className="text-blue-500 animate-spin" />
                <Brain size={20} className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-purple-400" />
              </div>
              <div className="text-center">
                <p className="text-lg font-bold text-slate-300">잠시만 기다려 주세요</p>
                <p className="text-sm text-slate-500">AI 에이전트가 소스 코드를 읽고 설계를 구성하는 중입니다...</p>
              </div>
            </div>
          ) : (
            thinkingLog.map((log, idx) => (
              <div
                key={idx}
                className={`group rounded-2xl p-4 border transition-all glass-card ${
                  isDarkMode ? "bg-white/5 border-white/5" : "bg-slate-50 border-slate-200 shadow-sm"
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded-lg text-[11px] font-bold uppercase tracking-wider ${
                      isDarkMode ? "bg-purple-600/20 text-purple-300" : "bg-purple-100 text-purple-600 border border-purple-200"
                    }`}>
                      {log.node}
                    </span>
                    <div className="w-1 h-1 rounded-full bg-slate-700" />
                    <span className="text-[11px] font-medium text-slate-500 font-mono">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                </div>
                <p className={`text-[14px] leading-relaxed whitespace-pre-wrap ${isDarkMode ? "text-slate-300" : "text-slate-700"}`}>
                  {log.text}
                </p>
              </div>
            ))
          )}
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  );
}

function StepItem({ label, desc, status, isDarkMode }) {
  const icons = {
    pending: <Circle size={16} className={isDarkMode ? "text-slate-700" : "text-slate-300"} />,
    running: <Loader2 size={16} className="text-blue-500 animate-spin" />,
    done: <CheckCircle2 size={16} className="text-green-500" />,
    error: <AlertCircle size={16} className="text-red-500" />,
  };

  const statusThemes = {
    running: "bg-blue-500/10 border-blue-500/30 text-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.1)]",
    done: "bg-green-500/10 border-green-500/20 text-green-500 opacity-90",
    pending: "border-transparent opacity-40",
    error: "bg-red-500/10 border-red-500/30 text-red-400"
  };

  return (
    <div
      className={`flex items-start gap-4 p-4 rounded-2xl transition-all border ${statusThemes[status] || statusThemes.pending}`}
    >
      <div className="mt-1 shrink-0">{icons[status] || icons.pending}</div>
      <div>
        <div className={`text-[14px] font-bold leading-none mb-1.5 ${status === "pending" ? "text-slate-500" : ""}`}>
          {label}
        </div>
        <div className={`text-[11px] leading-relaxed font-medium ${status === "pending" ? "text-slate-600" : "opacity-70"}`}>
          {desc}
        </div>
      </div>
    </div>
  );
}
