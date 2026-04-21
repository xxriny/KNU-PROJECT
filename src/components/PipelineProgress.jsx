/**
 * PipelineProgress — 파이프라인 실행 중 진행 상태 표시
 * Thinking Log 실시간 스트리밍 + 노드별 상태 표시
 */

import React, { useRef, useEffect } from "react";
import useAppStore from "../store/useAppStore";
import {
  Loader2,
  CheckCircle2,
  Circle,
  AlertCircle,
  Brain,
} from "lucide-react";

const SCAN_STEPS = [
  { key: "system_scan", label: "프로젝트 분석", desc: "소스 코드 구조 및 프레임워크 스캔" },
];

const PM_PIPELINE_STEPS = [
  { key: "requirement_analyzer", label: "요구사항 분석", desc: "사용자 아이디어를 원자 단위 요구사항으로 정밀 분석" },
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
  revision: [
    { key: "chat_revision", label: "수정 반영", desc: "기존 RTM 결과를 최소 수정으로 갱신" },
  ],
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
    <div className="h-full w-full flex bg-transparent text-sm transition-colors duration-300 overflow-hidden">
      {/* ── 좌측: 파이프라인 스텝 ──────────── */}
      <div className="w-72 shrink-0 border-r border-[var(--border)] bg-transparent flex flex-col min-h-0">
        <div className="p-4 pb-2 shrink-0">
          <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider">
            Pipeline Progress
          </h3>
        </div>
        <div className="flex-1 overflow-y-auto custom-scrollbar px-4 pb-4 space-y-2 min-h-0">
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
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
            <div className="flex items-center gap-1.5 text-sm text-red-400 mb-1">
              <AlertCircle size={12} />
              오류 발생
            </div>
            <p className="text-[12px] text-red-300/70 leading-relaxed">
              {pipelineError}
            </p>
          </div>
        )}
        </div>
      </div>

      {/* ── 우측: Thinking Log ─────────────── */}
      <div className="flex-1 min-w-0 flex flex-col bg-transparent">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--border)] shrink-0">
          <Brain size={14} className="text-purple-400" />
          <span className={`text-sm font-medium ${isDarkMode ? "text-slate-400" : "text-slate-700"}`}>
            Thinking Log
          </span>
          <span className="text-[12px] text-slate-500">
            ({thinkingLog.length} entries)
          </span>
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-3 custom-scrollbar">
          {thinkingLog.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full">
              <Loader2
                size={24}
                className="text-blue-400 animate-spin mb-3"
              />
              <p className="text-sm text-slate-500">
                AI 에이전트가 분석 중입니다...
              </p>
            </div>
          ) : (
            thinkingLog.map((log, idx) => (
              <div
                key={idx}
                className={`rounded-lg p-3 border transition-all glass-card border-[var(--border)]`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className={`px-1.5 py-0.5 rounded text-[12px] font-mono ${
                    isDarkMode ? "bg-purple-600/20 text-purple-300" : "bg-purple-50 text-purple-600 border border-purple-100"
                  }`}>
                    {log.node}
                  </span>
                  <span className="text-[12px] text-slate-500">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <p className={`text-sm leading-relaxed whitespace-pre-wrap ${isDarkMode ? "text-slate-400" : "text-slate-700"}`}>
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
    pending: <Circle size={14} className={isDarkMode ? "text-slate-600" : "text-slate-300"} />,
    running: <Loader2 size={14} className="text-blue-500 animate-spin" />,
    done: <CheckCircle2 size={14} className="text-green-500" />,
    error: <AlertCircle size={14} className="text-red-500" />,
  };

  return (
    <div
      className={`flex items-start gap-3 p-2.5 rounded-lg transition-all border ${
        status === "running"
          ? "bg-[var(--accent)]/10 border-[var(--accent)]/30 shadow-[inset_0_0_12px_rgba(56,189,248,0.1)]"
          : status === "done"
          ? "bg-[var(--green)]/10 border-[var(--green)]/20"
          : "border-transparent opacity-60"
      }`}
    >
      <div className="mt-0.5">{icons[status] || icons.pending}</div>
      <div>
        <div
          className={`text-sm font-medium ${
            status === "running"
              ? "text-[var(--accent)]"
              : status === "done"
              ? "text-[var(--green)]"
              : "text-[var(--text-secondary)]"
          }`}
        >
          {label}
        </div>
        <div className={`text-[12px] mt-0.5 text-[var(--text-muted)]`}>{desc}</div>
      </div>
    </div>
  );
}
