import React, { useEffect, useRef } from "react";
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
  { key: "system_scan", label: "Project Scan", desc: "프로젝트 구조와 주요 소스 파일을 스캔합니다." },
];

const PM_PIPELINE_STEPS = [
  { key: "requirement_analyzer", label: "Requirement Analyzer", desc: "아이디어를 요구사항 단위로 구조화합니다." },
  { key: "stack_planner", label: "Stack Planner", desc: "요구사항에 맞는 기술 스택을 선정합니다." },
  { key: "stack_crawling", label: "Stack Crawling", desc: "부족한 기술 정보를 보강합니다." },
  { key: "guardian", label: "Guardian", desc: "선정된 스택의 정합성과 리스크를 검증합니다." },
  { key: "pm_analysis", label: "PM Analysis", desc: "PM 산출물을 통합하고 결과를 정리합니다." },
];

const SA_PIPELINE_STEPS = [
  { key: "sa_merge_project", label: "Merge Project", desc: "PM 결과와 코드 분석 결과를 통합합니다." },
  { key: "component_scheduler", label: "Component Scheduler", desc: "시스템 컴포넌트 구조를 설계합니다." },
  { key: "api_data_modeler", label: "API / Data Modeler", desc: "API와 데이터 모델을 설계합니다." },
  { key: "sa_analysis", label: "SA Analysis", desc: "아키텍처 정합성과 갭을 검토합니다." },
  { key: "sa_embedding", label: "SA Embedding", desc: "SA 산출물을 적재 가능한 형태로 정리합니다." },
];

const DEVELOP_PIPELINE_STEPS = [
  { key: "develop_main_agent", label: "Main Agent", desc: "RAG 컨텍스트를 읽고 개발 계획을 수립합니다." },
  { key: "develop_uiux_agent", label: "UI/UX Agent", desc: "UI/UX 산출물을 생성합니다." },
  { key: "develop_uiux_qa_agent", label: "UI/UX QA", desc: "UI/UX 산출물을 검토합니다." },
  { key: "develop_backend_agent", label: "Backend Agent", desc: "백엔드 산출물을 생성합니다." },
  { key: "develop_backend_qa_agent", label: "Backend QA", desc: "백엔드 산출물을 검토합니다." },
  { key: "develop_frontend_agent", label: "Frontend Agent", desc: "프런트엔드 산출물을 생성합니다." },
  { key: "develop_frontend_qa_agent", label: "Frontend QA", desc: "프런트엔드 산출물을 검토합니다." },
  { key: "develop_global_fe_sync_gate", label: "Global FE Sync", desc: "공유 UI와 프런트 동기화 이슈를 점검합니다." },
  { key: "develop_integration_qa_gate", label: "Integration QA", desc: "도메인 결과를 통합 관점에서 검증합니다." },
  { key: "develop_branch_pr_orchestrator", label: "Branch / PR", desc: "브랜치 전략과 PR 초안을 생성합니다." },
  { key: "develop_embedding", label: "Embedding", desc: "개발 산출물을 artifact RAG에 실제 적재합니다." },
  { key: "develop_loop_controller", label: "Loop Controller", desc: "재시도 여부를 판단하고 종료합니다." },
];

const PIPELINE_STEPS_BY_TYPE = {
  analysis: [...SCAN_STEPS, ...PM_PIPELINE_STEPS],
  analysis_create: [...SCAN_STEPS, ...PM_PIPELINE_STEPS, ...SA_PIPELINE_STEPS],
  analysis_reverse: [...SCAN_STEPS, ...SA_PIPELINE_STEPS],
  analysis_update: [...SCAN_STEPS, ...PM_PIPELINE_STEPS, ...SA_PIPELINE_STEPS],
  develop_plan: DEVELOP_PIPELINE_STEPS,
  idea_chat: [
    { key: "idea_chat", label: "Idea Chat", desc: "아이디어를 구체화하고 다음 분석 방향을 잡습니다." },
  ],
};

export default function PipelineProgress() {
  const { pipelineNodes, thinkingLog, pipelineError, pipelineType, isDarkMode } = useAppStore();
  const logEndRef = useRef(null);
  const steps = PIPELINE_STEPS_BY_TYPE[pipelineType] || PM_PIPELINE_STEPS;

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [thinkingLog]);

  return (
    <div className="h-full w-full flex bg-transparent text-sm overflow-hidden p-4 gap-4">
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
            <div className="mt-4 p-4 bg-red-500/10 border border-red-500/30 rounded-xl">
              <div className="flex items-center gap-2 text-[13px] text-red-400 font-bold mb-1">
                <AlertCircle size={14} />
                Pipeline Error
              </div>
              <p className="text-[12px] text-red-300/80 leading-relaxed">{pipelineError}</p>
            </div>
          )}
        </div>
      </div>

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
            <div className="flex flex-col items-center justify-center h-full space-y-4">
              <div className="relative">
                <Loader2 size={40} className="text-blue-500 animate-spin" />
                <Brain size={20} className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-purple-400" />
              </div>
              <div className="text-center">
                <p className="text-lg font-bold text-slate-300">에이전트가 작업을 준비 중입니다.</p>
                <p className="text-sm text-slate-500">실행 중인 노드의 사고 로그가 여기에 표시됩니다.</p>
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
    <div className={`flex items-start gap-4 p-4 rounded-2xl transition-all border ${statusThemes[status] || statusThemes.pending}`}>
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
